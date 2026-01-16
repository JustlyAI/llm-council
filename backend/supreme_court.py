"""Supreme Court deliberation system with clerk-based grouping and opinion writing."""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model
from .config import (
    SUPREME_COURT_JUSTICES,
    MODEL_POWER_RANKINGS,
    CLERK_MODEL,
)
from .council import parse_ranking_from_text, calculate_aggregate_rankings


async def stage1_collect_justice_opinions(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual opinions from all 9 Supreme Court justices.

    Args:
        user_query: The user's question/case

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    prompt = f"""You are a Justice on an AI Supreme Court. You have been presented with a case to consider.

Case/Question: {user_query}

Please provide your individual opinion on this matter. Be thorough, well-reasoned, and cite any relevant principles or considerations. Structure your response clearly."""

    messages = [{"role": "user", "content": prompt}]

    # Query all justices in parallel
    responses = await query_models_parallel(SUPREME_COURT_JUSTICES, messages)

    # Format results
    results = []
    for model, response in responses.items():
        if response is not None:
            results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each justice ranks the anonymized opinions.

    Args:
        user_query: The original case/question
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Opinion {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different judicial opinions on the following case:

Case/Question: {user_query}

Here are the opinions from different justices (anonymized):

{responses_text}

Your task:
1. Evaluate each opinion based on:
   - Legal/logical reasoning quality
   - Comprehensiveness of analysis
   - Practical applicability
   - Clarity of argumentation
2. Determine which side of the issue each opinion supports (if applicable)
3. Provide a final ranking from best to worst

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the opinions from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the opinion label (e.g., "1. Response A")

Example format:
FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all justices in parallel
    responses = await query_models_parallel(SUPREME_COURT_JUSTICES, messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return results, label_to_model


async def clerk_analyze_and_group(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Clerk analyzes opinions and groups justices into majority/minority (or consensus).

    The clerk examines the substantive positions in each opinion to determine
    groupings based on actual stance, not just ranking quality.

    Args:
        user_query: The original case/question
        stage1_results: Individual opinions
        stage2_results: Peer rankings
        aggregate_rankings: Aggregated ranking scores

    Returns:
        Dict with grouping information:
        - consensus: bool (True if all justices agree)
        - majority: List of model names in majority
        - minority: List of model names in minority (empty if consensus)
        - majority_lead: Model name of majority lead
        - minority_lead: Model name of minority lead (None if consensus)
        - clerk_analysis: The clerk's reasoning
    """
    # Build context for clerk
    opinions_text = "\n\n".join([
        f"Justice ({result['model']}):\n{result['response']}"
        for result in stage1_results
    ])

    clerk_prompt = f"""You are the Clerk of an AI Supreme Court. Your role is to analyze the justices' opinions and determine if there is a consensus or if the court is split into majority and minority positions.

Case/Question: {user_query}

JUSTICE OPINIONS:
{opinions_text}

YOUR TASK:
1. Analyze the SUBSTANTIVE POSITIONS taken by each justice (not just the quality of their reasoning)
2. Determine if there is consensus (all justices essentially agree on the outcome/position)
3. If there is no consensus, identify which justices form the majority and which form the minority based on their substantive positions

IMPORTANT: You must output your analysis in a STRICT FORMAT:

First, provide your analysis of each justice's position.

Then, output ONE of these two formats:

FOR CONSENSUS (all agree):
```
GROUPING: CONSENSUS
MAJORITY: [list ALL justice model names, comma-separated]
```

FOR SPLIT DECISION:
```
GROUPING: SPLIT
MAJORITY: [list majority justice model names, comma-separated]
MINORITY: [list minority justice model names, comma-separated]
```

The model names must be EXACTLY as shown above (e.g., "openai/gpt-5.1", "google/gemini-3-pro-preview", etc.)

Now analyze the opinions and provide the grouping:"""

    messages = [{"role": "user", "content": clerk_prompt}]

    response = await query_model(CLERK_MODEL, messages)

    if response is None:
        # Fallback: Use top 5 by ranking as majority, rest as minority
        return _fallback_grouping(stage1_results, aggregate_rankings)

    clerk_analysis = response.get('content', '')
    return _parse_clerk_grouping(clerk_analysis, stage1_results)


def _parse_clerk_grouping(
    clerk_analysis: str,
    stage1_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Parse the clerk's grouping from their analysis."""
    import re

    all_models = [r['model'] for r in stage1_results]

    # Check for consensus
    is_consensus = "GROUPING: CONSENSUS" in clerk_analysis.upper()

    majority = []
    minority = []

    # Extract MAJORITY line
    majority_match = re.search(r'MAJORITY:\s*\[([^\]]+)\]', clerk_analysis, re.IGNORECASE)
    if majority_match:
        majority_text = majority_match.group(1)
        for model in all_models:
            if model in majority_text:
                majority.append(model)

    # Extract MINORITY line
    minority_match = re.search(r'MINORITY:\s*\[([^\]]+)\]', clerk_analysis, re.IGNORECASE)
    if minority_match:
        minority_text = minority_match.group(1)
        for model in all_models:
            if model in minority_text:
                minority.append(model)

    # Validation: ensure all models are accounted for
    accounted = set(majority + minority)
    missing = [m for m in all_models if m not in accounted]

    # Add missing models to majority by default
    majority.extend(missing)

    # If consensus, all should be in majority
    if is_consensus:
        majority = all_models
        minority = []

    # Select leads based on power rankings
    majority_lead = _select_lead(majority)
    minority_lead = _select_lead(minority) if minority else None

    return {
        "consensus": is_consensus or len(minority) == 0,
        "majority": majority,
        "minority": minority,
        "majority_lead": majority_lead,
        "minority_lead": minority_lead,
        "clerk_analysis": clerk_analysis
    }


def _fallback_grouping(
    stage1_results: List[Dict[str, Any]],
    aggregate_rankings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Fallback grouping based on rankings (top 5 = majority)."""
    all_models = [r['model'] for r in stage1_results]

    # Use aggregate rankings to split
    ranked_models = [r['model'] for r in aggregate_rankings]

    # Add any models not in rankings
    for model in all_models:
        if model not in ranked_models:
            ranked_models.append(model)

    # Top 5 = majority, rest = minority
    majority = ranked_models[:5]
    minority = ranked_models[5:]

    return {
        "consensus": False,
        "majority": majority,
        "minority": minority,
        "majority_lead": _select_lead(majority),
        "minority_lead": _select_lead(minority) if minority else None,
        "clerk_analysis": "Fallback grouping: Clerk failed to respond, using ranking-based split."
    }


def _select_lead(models: List[str]) -> Optional[str]:
    """Select the most powerful model as lead from a list."""
    if not models:
        return None

    return max(models, key=lambda m: MODEL_POWER_RANKINGS.get(m, 0))


async def stage3_write_draft_opinions(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 3: Group leads write draft opinions synthesizing their group's views.

    The leads receive anonymized versions of their group members' opinions
    and must synthesize them into a cohesive draft opinion.

    Args:
        user_query: The original case/question
        stage1_results: Individual opinions
        grouping: Clerk's grouping decision

    Returns:
        Dict with draft opinions for majority (and minority if split)
    """
    results = {}

    # Get opinions by model for easy lookup
    opinions_by_model = {r['model']: r['response'] for r in stage1_results}

    # Majority draft opinion
    majority_opinions = [
        opinions_by_model[m] for m in grouping['majority']
        if m in opinions_by_model
    ]

    majority_draft = await _write_group_draft(
        user_query,
        majority_opinions,
        grouping['majority_lead'],
        is_majority=True
    )

    results['majority_draft'] = {
        'lead': grouping['majority_lead'],
        'opinion': majority_draft,
        'group_members': grouping['majority']
    }

    # Minority draft opinion (if split decision)
    if not grouping['consensus'] and grouping['minority']:
        minority_opinions = [
            opinions_by_model[m] for m in grouping['minority']
            if m in opinions_by_model
        ]

        minority_draft = await _write_group_draft(
            user_query,
            minority_opinions,
            grouping['minority_lead'],
            is_majority=False
        )

        results['minority_draft'] = {
            'lead': grouping['minority_lead'],
            'opinion': minority_draft,
            'group_members': grouping['minority']
        }

    return results


async def _write_group_draft(
    user_query: str,
    group_opinions: List[str],
    lead_model: str,
    is_majority: bool
) -> str:
    """Write a draft opinion synthesizing group members' views."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    # Anonymize the opinions
    labels = [chr(65 + i) for i in range(len(group_opinions))]
    anonymized_text = "\n\n".join([
        f"Justice {label}'s Position:\n{opinion}"
        for label, opinion in zip(labels, group_opinions)
    ])

    prompt = f"""You are the Lead Justice writing the {opinion_type} Opinion for an AI Supreme Court.

Case/Question: {user_query}

Your fellow justices in the {opinion_type.lower()} have provided their individual positions (anonymized):

{anonymized_text}

YOUR TASK:
Write a cohesive {opinion_type} Opinion that:
1. Synthesizes the key arguments and reasoning from your fellow justices
2. Presents a unified position on the case
3. Addresses the main points of contention
4. Provides clear reasoning for the {opinion_type.lower()}'s position

Write in the formal style of a Supreme Court opinion. Begin with a statement of the issue and the {opinion_type.lower()}'s position, then present the reasoning.

{opinion_type.upper()} OPINION:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead_model, messages)

    if response is None:
        return f"Error: {lead_model} failed to generate draft opinion."

    return response.get('content', '')


async def stage4_rate_draft_opinions(
    user_query: str,
    draft_opinions: Dict[str, Any],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 4: Group members rate their group's draft opinion.

    Each member provides feedback on the draft, rating its quality
    and suggesting improvements.

    Args:
        user_query: The original case/question
        draft_opinions: Draft opinions from Stage 3
        grouping: Clerk's grouping decision

    Returns:
        Dict with ratings for majority (and minority if split)
    """
    results = {}

    # Rate majority opinion
    majority_members = [m for m in grouping['majority'] if m != grouping['majority_lead']]
    if majority_members:
        majority_ratings = await _rate_group_opinion(
            user_query,
            draft_opinions['majority_draft']['opinion'],
            majority_members,
            is_majority=True
        )
        results['majority_ratings'] = majority_ratings

    # Rate minority opinion (if exists)
    if 'minority_draft' in draft_opinions and grouping['minority']:
        minority_members = [m for m in grouping['minority'] if m != grouping['minority_lead']]
        if minority_members:
            minority_ratings = await _rate_group_opinion(
                user_query,
                draft_opinions['minority_draft']['opinion'],
                minority_members,
                is_majority=False
            )
            results['minority_ratings'] = minority_ratings

    return results


async def _rate_group_opinion(
    user_query: str,
    draft_opinion: str,
    member_models: List[str],
    is_majority: bool
) -> List[Dict[str, Any]]:
    """Have group members rate their draft opinion."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    rating_prompt = f"""You are a Justice on an AI Supreme Court reviewing the draft {opinion_type} Opinion written by your Lead Justice.

Case/Question: {user_query}

DRAFT {opinion_type.upper()} OPINION:
{draft_opinion}

YOUR TASK:
Evaluate this draft opinion and provide:

1. RATING (1-10): Rate the overall quality of this opinion
2. STRENGTHS: What does this opinion do well?
3. WEAKNESSES: What could be improved?
4. SUGGESTIONS: Specific suggestions for the final version

Format your response as:
RATING: [number 1-10]
STRENGTHS: [your analysis]
WEAKNESSES: [your analysis]
SUGGESTIONS: [your suggestions]"""

    messages = [{"role": "user", "content": rating_prompt}]

    # Query all member models in parallel
    responses = await query_models_parallel(member_models, messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            content = response.get('content', '')
            rating = _extract_rating(content)
            results.append({
                "model": model,
                "feedback": content,
                "rating": rating
            })

    return results


def _extract_rating(feedback: str) -> Optional[int]:
    """Extract numeric rating from feedback."""
    import re

    match = re.search(r'RATING:\s*(\d+)', feedback, re.IGNORECASE)
    if match:
        rating = int(match.group(1))
        return min(max(rating, 1), 10)  # Clamp to 1-10

    # Fallback: look for any standalone number near start
    match = re.search(r'^.*?(\d+)/10', feedback)
    if match:
        return min(max(int(match.group(1)), 1), 10)

    return None


async def stage5_synthesize_final_opinions(
    user_query: str,
    draft_opinions: Dict[str, Any],
    ratings: Dict[str, Any],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 5: Leads synthesize final opinions incorporating peer feedback.

    Args:
        user_query: The original case/question
        draft_opinions: Draft opinions from Stage 3
        ratings: Ratings from Stage 4
        grouping: Clerk's grouping decision

    Returns:
        Dict with final opinions
    """
    results = {}

    # Final majority opinion
    majority_feedback = ratings.get('majority_ratings', [])
    majority_final = await _synthesize_final_opinion(
        user_query,
        draft_opinions['majority_draft']['opinion'],
        majority_feedback,
        grouping['majority_lead'],
        is_majority=True
    )

    results['majority_opinion'] = {
        'lead': grouping['majority_lead'],
        'opinion': majority_final,
        'group_members': grouping['majority'],
        'average_rating': _calculate_average_rating(majority_feedback)
    }

    # Final minority opinion (if exists)
    if 'minority_draft' in draft_opinions:
        minority_feedback = ratings.get('minority_ratings', [])
        minority_final = await _synthesize_final_opinion(
            user_query,
            draft_opinions['minority_draft']['opinion'],
            minority_feedback,
            grouping['minority_lead'],
            is_majority=False
        )

        results['minority_opinion'] = {
            'lead': grouping['minority_lead'],
            'opinion': minority_final,
            'group_members': grouping['minority'],
            'average_rating': _calculate_average_rating(minority_feedback)
        }

    return results


async def _synthesize_final_opinion(
    user_query: str,
    draft_opinion: str,
    feedback: List[Dict[str, Any]],
    lead_model: str,
    is_majority: bool
) -> str:
    """Synthesize final opinion incorporating peer feedback."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    # Anonymize feedback
    if feedback:
        labels = [chr(65 + i) for i in range(len(feedback))]
        feedback_text = "\n\n".join([
            f"Justice {label}'s Feedback:\n{f['feedback']}"
            for label, f in zip(labels, feedback)
        ])
    else:
        feedback_text = "No peer feedback available."

    prompt = f"""You are the Lead Justice finalizing the {opinion_type} Opinion for an AI Supreme Court.

Case/Question: {user_query}

YOUR DRAFT OPINION:
{draft_opinion}

PEER FEEDBACK (anonymized):
{feedback_text}

YOUR TASK:
Write the FINAL {opinion_type} Opinion, incorporating the valuable feedback from your fellow justices. Consider:
1. Addressing weaknesses identified in the feedback
2. Strengthening arguments where suggested
3. Maintaining the core position while improving clarity and reasoning
4. Ensuring the opinion represents the collective view of the {opinion_type.lower()}

Write the complete, polished final opinion in formal Supreme Court style.

FINAL {opinion_type.upper()} OPINION OF THE COURT:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead_model, messages)

    if response is None:
        return draft_opinion  # Fall back to draft

    return response.get('content', '')


def _calculate_average_rating(feedback: List[Dict[str, Any]]) -> Optional[float]:
    """Calculate average rating from feedback."""
    ratings = [f['rating'] for f in feedback if f.get('rating') is not None]
    if ratings:
        return round(sum(ratings) / len(ratings), 2)
    return None


async def run_supreme_court(user_query: str) -> Dict[str, Any]:
    """
    Run the complete Supreme Court deliberation process.

    Stages:
    1. Collect individual justice opinions
    2. Anonymized peer rankings
    3. Clerk groups justices (majority/minority or consensus)
    4. Leads write draft opinions
    5. Group members rate drafts
    6. Leads synthesize final opinions

    Args:
        user_query: The case/question

    Returns:
        Complete results from all stages with metadata
    """
    # Stage 1: Collect individual opinions
    stage1_results = await stage1_collect_justice_opinions(user_query)

    if not stage1_results:
        return {
            "error": "All justices failed to respond. Please try again.",
            "stage1": [],
            "stage2": [],
            "grouping": {},
            "draft_opinions": {},
            "ratings": {},
            "final_opinions": {}
        }

    # Stage 2: Collect peer rankings
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Clerk Stage: Analyze and group
    grouping = await clerk_analyze_and_group(
        user_query, stage1_results, stage2_results, aggregate_rankings
    )

    # Stage 3: Write draft opinions
    draft_opinions = await stage3_write_draft_opinions(
        user_query, stage1_results, grouping
    )

    # Stage 4: Rate draft opinions
    ratings = await stage4_rate_draft_opinions(
        user_query, draft_opinions, grouping
    )

    # Stage 5: Synthesize final opinions
    final_opinions = await stage5_synthesize_final_opinions(
        user_query, draft_opinions, ratings, grouping
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "grouping": grouping,
        "draft_opinions": draft_opinions,
        "ratings": ratings,
        "final_opinions": final_opinions,
        "metadata": {
            "label_to_model": label_to_model,
            "aggregate_rankings": aggregate_rankings,
            "consensus": grouping['consensus']
        }
    }

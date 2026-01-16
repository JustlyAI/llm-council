"""Supreme Court deliberation system with clerk-based grouping and opinion writing.

Flow:
1. Stage 1: Collect individual justice opinions from all 9 models
2. Clerk Stage: Analyze opinions and group justices into majority/minority (or consensus)
3. Stage 2: Within-group peer ranking (justices rate only their group's opinions)
4. Stage 3: Leads synthesize final opinions from group feedback
5. Stage 4: Majority opinion completed
6. Stage 5: Dissenting opinion completed (if split decision)
"""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model
from .config import (
    SUPREME_COURT_JUSTICES,
    MODEL_POWER_RANKINGS,
    CLERK_MODEL,
)


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


async def clerk_analyze_and_group(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Clerk Stage: Analyze opinions and group justices into majority/minority (or consensus).

    The clerk examines the substantive positions in each opinion to determine
    groupings based on actual stance, not ranking quality.

    Args:
        user_query: The original case/question
        stage1_results: Individual opinions from Stage 1

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
        # Fallback: Simple majority split
        return _fallback_grouping(stage1_results)

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


def _fallback_grouping(stage1_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback grouping: simple 5-4 split."""
    all_models = [r['model'] for r in stage1_results]

    # Simple split: first 5 = majority, rest = minority
    majority = all_models[:5]
    minority = all_models[5:]

    return {
        "consensus": False,
        "majority": majority,
        "minority": minority,
        "majority_lead": _select_lead(majority),
        "minority_lead": _select_lead(minority) if minority else None,
        "clerk_analysis": "Fallback grouping: Clerk failed to respond, using default split."
    }


def _select_lead(models: List[str]) -> Optional[str]:
    """Select the most powerful model as lead from a list."""
    if not models:
        return None

    return max(models, key=lambda m: MODEL_POWER_RANKINGS.get(m, 0))


def _parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Opinion A")
            numbered_matches = re.findall(r'\d+\.\s*Opinion [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Opinion [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Opinion X" patterns in order
            matches = re.findall(r'Opinion [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Opinion X" patterns in order
    matches = re.findall(r'Opinion [A-Z]', ranking_text)
    return matches


async def stage2_within_group_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 2: Within-group peer ranking.

    Each justice evaluates only the opinions from justices in their own group.

    Args:
        user_query: The original case/question
        stage1_results: Individual opinions from Stage 1
        grouping: Clerk's grouping decision

    Returns:
        Dict with rankings for majority and minority groups
    """
    results = {}

    # Get opinions by model for easy lookup
    opinions_by_model = {r['model']: r['response'] for r in stage1_results}

    # Majority group rankings
    majority_rankings = await _rank_within_group(
        user_query,
        grouping['majority'],
        opinions_by_model,
        is_majority=True
    )
    results['majority_rankings'] = majority_rankings

    # Minority group rankings (if split decision)
    if not grouping['consensus'] and grouping['minority']:
        minority_rankings = await _rank_within_group(
            user_query,
            grouping['minority'],
            opinions_by_model,
            is_majority=False
        )
        results['minority_rankings'] = minority_rankings

    return results


async def _rank_within_group(
    user_query: str,
    group_members: List[str],
    opinions_by_model: Dict[str, str],
    is_majority: bool
) -> Dict[str, Any]:
    """Have group members rank opinions within their group."""
    group_type = "majority" if is_majority else "minority"

    # Create anonymized labels for group opinions
    labels = [chr(65 + i) for i in range(len(group_members))]  # A, B, C, ...

    label_to_model = {
        f"Opinion {label}": model
        for label, model in zip(labels, group_members)
    }

    # Build the opinions text
    opinions_text = "\n\n".join([
        f"Opinion {label}:\n{opinions_by_model.get(model, 'No opinion available')}"
        for label, model in zip(labels, group_members)
    ])

    ranking_prompt = f"""You are a Justice on the {group_type} side of an AI Supreme Court. You are evaluating the opinions of your fellow {group_type} justices.

Case/Question: {user_query}

Here are the opinions from your fellow {group_type} justices (anonymized):

{opinions_text}

Your task:
1. Evaluate each opinion based on:
   - Quality of reasoning and argumentation
   - Comprehensiveness of analysis
   - Persuasiveness and clarity
   - Alignment with the {group_type} position
2. Provide a final ranking from best to worst

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the opinions from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the opinion label (e.g., "1. Opinion A")

Example format:
FINAL RANKING:
1. Opinion C
2. Opinion A
3. Opinion B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all group members in parallel
    responses = await query_models_parallel(group_members, messages)

    rankings = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = _parse_ranking_from_text(full_text)
            rankings.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return {
        "rankings": rankings,
        "label_to_model": label_to_model
    }


async def stage3_synthesize_opinions(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: Dict[str, Any],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 3: Leads synthesize final opinions incorporating group peer feedback.

    Args:
        user_query: The original case/question
        stage1_results: Individual opinions from Stage 1
        stage2_results: Within-group rankings from Stage 2
        grouping: Clerk's grouping decision

    Returns:
        Dict with synthesized opinions (ready for Stage 4 & 5 completion)
    """
    results = {}

    # Get opinions by model for easy lookup
    opinions_by_model = {r['model']: r['response'] for r in stage1_results}

    # Majority opinion synthesis
    majority_opinion = await _synthesize_group_opinion(
        user_query,
        grouping['majority'],
        opinions_by_model,
        stage2_results.get('majority_rankings', {}),
        grouping['majority_lead'],
        is_majority=True
    )
    results['majority'] = majority_opinion

    # Minority opinion synthesis (if split decision)
    if not grouping['consensus'] and grouping['minority']:
        minority_opinion = await _synthesize_group_opinion(
            user_query,
            grouping['minority'],
            opinions_by_model,
            stage2_results.get('minority_rankings', {}),
            grouping['minority_lead'],
            is_majority=False
        )
        results['minority'] = minority_opinion

    return results


async def _synthesize_group_opinion(
    user_query: str,
    group_members: List[str],
    opinions_by_model: Dict[str, str],
    group_rankings: Dict[str, Any],
    lead_model: str,
    is_majority: bool
) -> Dict[str, Any]:
    """Synthesize a group's opinion based on individual opinions and peer rankings."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    # Anonymize the group opinions
    labels = [chr(65 + i) for i in range(len(group_members))]
    anonymized_opinions = "\n\n".join([
        f"Justice {label}'s Opinion:\n{opinions_by_model.get(model, 'No opinion')}"
        for label, model in zip(labels, group_members)
    ])

    # Summarize the peer rankings
    rankings_summary = ""
    if group_rankings and 'rankings' in group_rankings:
        rankings_summary = "\n\nPEER FEEDBACK SUMMARY:\n"
        for rank_data in group_rankings['rankings']:
            rankings_summary += f"\n{rank_data.get('model', 'Unknown')} ranked:\n{rank_data.get('ranking', 'No ranking')[:500]}...\n"

    prompt = f"""You are the Lead Justice writing the {opinion_type} Opinion for an AI Supreme Court.

Case/Question: {user_query}

Your fellow {opinion_type.lower()} justices have provided their individual opinions (anonymized):

{anonymized_opinions}

{rankings_summary}

YOUR TASK:
Write a comprehensive {opinion_type} Opinion that:
1. Synthesizes the strongest arguments from your fellow justices
2. Addresses weaknesses identified in the peer feedback
3. Presents a unified, well-reasoned position
4. Uses formal Supreme Court opinion style

Begin with "The {opinion_type.lower()} holds that..." and present the complete opinion.

{opinion_type.upper()} OPINION:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead_model, messages)

    if response is None:
        return {
            "lead": lead_model,
            "opinion": f"Error: {lead_model} failed to generate opinion.",
            "group_members": group_members,
            "status": "error"
        }

    return {
        "lead": lead_model,
        "opinion": response.get('content', ''),
        "group_members": group_members,
        "status": "completed"
    }


async def stage4_complete_majority_opinion(
    synthesized_opinions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 4: Finalize and return the majority opinion.

    Args:
        synthesized_opinions: Results from Stage 3

    Returns:
        Completed majority opinion
    """
    majority = synthesized_opinions.get('majority', {})

    return {
        "lead": majority.get('lead'),
        "opinion": majority.get('opinion', ''),
        "group_members": majority.get('group_members', []),
        "status": "completed"
    }


async def stage5_complete_dissent_opinion(
    synthesized_opinions: Dict[str, Any],
    is_consensus: bool
) -> Optional[Dict[str, Any]]:
    """
    Stage 5: Finalize and return the dissenting opinion (if split decision).

    Args:
        synthesized_opinions: Results from Stage 3
        is_consensus: Whether this is a unanimous decision

    Returns:
        Completed dissenting opinion, or None if consensus
    """
    if is_consensus:
        return None

    minority = synthesized_opinions.get('minority', {})

    if not minority:
        return None

    return {
        "lead": minority.get('lead'),
        "opinion": minority.get('opinion', ''),
        "group_members": minority.get('group_members', []),
        "status": "completed"
    }


async def run_supreme_court(user_query: str) -> Dict[str, Any]:
    """
    Run the complete Supreme Court deliberation process.

    Flow:
    1. Stage 1: Collect individual justice opinions
    2. Clerk Stage: Analyze and group justices
    3. Stage 2: Within-group peer rankings
    4. Stage 3: Leads synthesize opinions
    5. Stage 4: Majority opinion completed
    6. Stage 5: Dissenting opinion completed (if split)

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
            "grouping": {},
            "stage2": {},
            "stage3": {},
            "majority_opinion": {},
            "dissent_opinion": None
        }

    # Clerk Stage: Analyze and group
    grouping = await clerk_analyze_and_group(user_query, stage1_results)

    # Stage 2: Within-group peer rankings
    stage2_results = await stage2_within_group_rankings(
        user_query, stage1_results, grouping
    )

    # Stage 3: Leads synthesize opinions
    stage3_results = await stage3_synthesize_opinions(
        user_query, stage1_results, stage2_results, grouping
    )

    # Stage 4: Complete majority opinion
    majority_opinion = await stage4_complete_majority_opinion(stage3_results)

    # Stage 5: Complete dissenting opinion
    dissent_opinion = await stage5_complete_dissent_opinion(
        stage3_results, grouping['consensus']
    )

    return {
        "stage1": stage1_results,
        "grouping": grouping,
        "stage2": stage2_results,
        "stage3": stage3_results,
        "majority_opinion": majority_opinion,
        "dissent_opinion": dissent_opinion,
        "metadata": {
            "consensus": grouping['consensus'],
            "majority_count": len(grouping['majority']),
            "minority_count": len(grouping.get('minority', []))
        }
    }

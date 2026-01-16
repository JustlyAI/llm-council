"""Supreme Court deliberation system with reconsideration and opinion feedback.

Flow:
1. Stage 1: Initial positions from all 9 justices
2. Stage 2: Reconsideration - each justice reads all 8 anonymized positions, decides MAINTAIN or CHANGE
3. Clerk Stage: Groups justices based on final positions
4. Stage 3: Majority opinion - lead writes draft, members give feedback, lead finalizes
5. Stage 4: Majority opinion released
6. Stage 5: Dissent - minority lead sees majority opinion, writes draft, members give feedback, lead finalizes
"""

from typing import List, Dict, Any, Optional
from .openrouter import query_models_parallel, query_model
from .config import (
    SUPREME_COURT_JUSTICES,
    MODEL_POWER_RANKINGS,
    CLERK_MODEL,
)


async def stage1_initial_positions(user_query: str) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect initial positions from all 9 justices.

    These are brief position statements, not full opinions.
    """
    prompt = f"""You are a Justice on an AI Supreme Court. You have been presented with a case.

Case/Question: {user_query}

Provide your INITIAL POSITION on this matter. This should be:
1. A clear statement of your position (for/against/nuanced stance)
2. Your key reasoning (2-3 main points)
3. Keep it concise - this is your initial take, not a full opinion

Format:
POSITION: [Your stance]
REASONING:
- [Point 1]
- [Point 2]
- [Point 3 if needed]"""

    messages = [{"role": "user", "content": prompt}]
    responses = await query_models_parallel(SUPREME_COURT_JUSTICES, messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            results.append({
                "model": model,
                "position": response.get('content', '')
            })

    return results


async def stage2_reconsideration(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Stage 2: Each justice reads all 8 other positions and decides to MAINTAIN or CHANGE.
    """
    results = []

    for justice in stage1_results:
        current_model = justice['model']

        # Build anonymized list of OTHER justices' positions
        other_positions = []
        labels = []
        label_idx = 0

        for other in stage1_results:
            if other['model'] != current_model:
                label = chr(65 + label_idx)  # A, B, C, ...
                labels.append(label)
                other_positions.append(f"Justice {label}:\n{other['position']}")
                label_idx += 1

        positions_text = "\n\n".join(other_positions)

        prompt = f"""You are a Justice on an AI Supreme Court reconsidering your position after reading your colleagues' views.

Case/Question: {user_query}

YOUR INITIAL POSITION:
{justice['position']}

YOUR COLLEAGUES' POSITIONS (anonymized):

{positions_text}

After reading all positions, you must decide:
1. Do any arguments change your view?
2. Will you MAINTAIN your position or CHANGE it?

Respond in this EXACT format:
DECISION: [MAINTAIN or CHANGE]
FINAL_POSITION: [Your position after deliberation - restate if maintaining, or state new position if changing]
REASONING: [Brief explanation of why you maintained or changed]"""

        messages = [{"role": "user", "content": prompt}]
        response = await query_model(current_model, messages)

        if response is not None:
            content = response.get('content', '')
            decision = _parse_decision(content)
            results.append({
                "model": current_model,
                "initial_position": justice['position'],
                "reconsideration": content,
                "decision": decision,
                "changed": decision == "CHANGE"
            })

    return results


def _parse_decision(text: str) -> str:
    """Parse MAINTAIN or CHANGE from reconsideration response."""
    import re
    match = re.search(r'DECISION:\s*(MAINTAIN|CHANGE)', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # Default to MAINTAIN if not clear
    return "MAINTAIN"


async def clerk_group_justices(
    user_query: str,
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Clerk Stage: Group justices into majority/minority based on final positions.
    """
    positions_text = "\n\n".join([
        f"Justice ({r['model']}):\n{r['reconsideration']}"
        for r in stage2_results
    ])

    clerk_prompt = f"""You are the Clerk of an AI Supreme Court. After deliberation, the justices have stated their final positions. Your job is to group them.

Case/Question: {user_query}

FINAL POSITIONS AFTER DELIBERATION:
{positions_text}

YOUR TASK:
1. Identify the substantive position each justice holds
2. Group justices into MAJORITY (the larger group) and MINORITY (the smaller group)
3. If all justices agree, mark it as CONSENSUS

Output format:
GROUPING: [CONSENSUS or SPLIT]
MAJORITY: [comma-separated list of model names exactly as shown]
MINORITY: [comma-separated list of model names, or empty if consensus]

Example:
GROUPING: SPLIT
MAJORITY: openai/gpt-5.1, google/gemini-3-pro-preview, anthropic/claude-sonnet-4.5, x-ai/grok-4, meta-llama/llama-4-maverick
MINORITY: mistralai/mistral-large-2411, deepseek/deepseek-chat-v3-0324, qwen/qwen-max, ai21/jamba-1.6-large"""

    messages = [{"role": "user", "content": clerk_prompt}]
    response = await query_model(CLERK_MODEL, messages)

    if response is None:
        return _fallback_grouping(stage2_results)

    return _parse_clerk_grouping(response.get('content', ''), stage2_results)


def _parse_clerk_grouping(clerk_text: str, stage2_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse clerk's grouping decision."""
    import re

    all_models = [r['model'] for r in stage2_results]
    is_consensus = "GROUPING: CONSENSUS" in clerk_text.upper()

    majority = []
    minority = []

    # Extract MAJORITY
    maj_match = re.search(r'MAJORITY:\s*([^\n]+)', clerk_text, re.IGNORECASE)
    if maj_match:
        maj_text = maj_match.group(1)
        for model in all_models:
            if model in maj_text:
                majority.append(model)

    # Extract MINORITY
    min_match = re.search(r'MINORITY:\s*([^\n]+)', clerk_text, re.IGNORECASE)
    if min_match:
        min_text = min_match.group(1)
        for model in all_models:
            if model in min_text:
                minority.append(model)

    # Handle unassigned models
    assigned = set(majority + minority)
    unassigned = [m for m in all_models if m not in assigned]
    majority.extend(unassigned)

    if is_consensus:
        majority = all_models
        minority = []

    # Select leads
    majority_lead = _select_lead(majority)
    minority_lead = _select_lead(minority) if minority else None

    return {
        "consensus": is_consensus or len(minority) == 0,
        "majority": majority,
        "minority": minority,
        "majority_lead": majority_lead,
        "minority_lead": minority_lead,
        "clerk_analysis": clerk_text
    }


def _fallback_grouping(stage2_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback: 5-4 split."""
    all_models = [r['model'] for r in stage2_results]
    majority = all_models[:5]
    minority = all_models[5:]

    return {
        "consensus": False,
        "majority": majority,
        "minority": minority,
        "majority_lead": _select_lead(majority),
        "minority_lead": _select_lead(minority),
        "clerk_analysis": "Fallback grouping used."
    }


def _select_lead(models: List[str]) -> Optional[str]:
    """Select most powerful model as lead."""
    if not models:
        return None
    return max(models, key=lambda m: MODEL_POWER_RANKINGS.get(m, 0))


async def stage3_majority_opinion(
    user_query: str,
    stage2_results: List[Dict[str, Any]],
    grouping: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Stage 3: Majority lead writes draft, members give feedback, lead finalizes.
    """
    majority_models = grouping['majority']
    lead = grouping['majority_lead']
    other_members = [m for m in majority_models if m != lead]

    # Get positions for majority members
    positions_by_model = {r['model']: r['reconsideration'] for r in stage2_results}

    # Step 1: Lead writes draft opinion
    draft = await _write_draft_opinion(
        user_query, majority_models, positions_by_model, lead, is_majority=True
    )

    # Step 2: Other members give feedback
    feedback = await _collect_feedback(
        user_query, draft, other_members, is_majority=True
    )

    # Step 3: Lead finalizes based on feedback
    final_opinion = await _finalize_opinion(
        user_query, draft, feedback, lead, is_majority=True
    )

    return {
        "lead": lead,
        "members": majority_models,
        "draft": draft,
        "feedback": feedback,
        "final_opinion": final_opinion
    }


async def stage4_release_majority(stage3_result: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 4: Package and release majority opinion."""
    return {
        "lead": stage3_result['lead'],
        "members": stage3_result['members'],
        "opinion": stage3_result['final_opinion'],
        "status": "released"
    }


async def stage5_dissent_opinion(
    user_query: str,
    stage2_results: List[Dict[str, Any]],
    grouping: Dict[str, Any],
    majority_opinion: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Stage 5: Minority writes dissent after seeing majority opinion.
    """
    if grouping['consensus'] or not grouping['minority']:
        return None

    minority_models = grouping['minority']
    lead = grouping['minority_lead']
    other_members = [m for m in minority_models if m != lead]

    positions_by_model = {r['model']: r['reconsideration'] for r in stage2_results}

    # Step 1: Lead writes draft dissent (can see majority opinion)
    draft = await _write_dissent_draft(
        user_query, minority_models, positions_by_model, lead,
        majority_opinion['opinion']
    )

    # Step 2: Other dissenters give feedback
    feedback = []
    if other_members:
        feedback = await _collect_feedback(
            user_query, draft, other_members, is_majority=False,
            majority_opinion=majority_opinion['opinion']
        )

    # Step 3: Lead finalizes dissent
    final_dissent = await _finalize_dissent(
        user_query, draft, feedback, lead, majority_opinion['opinion']
    )

    return {
        "lead": lead,
        "members": minority_models,
        "draft": draft,
        "feedback": feedback,
        "final_opinion": final_dissent,
        "status": "released"
    }


async def _write_draft_opinion(
    user_query: str,
    group_members: List[str],
    positions_by_model: Dict[str, str],
    lead: str,
    is_majority: bool
) -> str:
    """Lead writes initial draft opinion."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    # Anonymize group positions
    labels = [chr(65 + i) for i in range(len(group_members))]
    positions_text = "\n\n".join([
        f"Justice {label}'s Position:\n{positions_by_model.get(model, 'N/A')}"
        for label, model in zip(labels, group_members)
    ])

    prompt = f"""You are the Lead Justice writing the {opinion_type} Opinion for an AI Supreme Court.

Case/Question: {user_query}

Your {opinion_type.lower()} colleagues' positions (anonymized):

{positions_text}

Write a comprehensive DRAFT {opinion_type} Opinion that:
1. States the {opinion_type.lower()}'s holding clearly
2. Synthesizes the strongest arguments from your colleagues
3. Provides thorough legal/logical reasoning
4. Uses formal Supreme Court opinion style

Begin with "The {opinion_type.lower()} holds that..."

DRAFT {opinion_type.upper()} OPINION:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead, messages)

    return response.get('content', '') if response else "Error generating draft."


async def _write_dissent_draft(
    user_query: str,
    group_members: List[str],
    positions_by_model: Dict[str, str],
    lead: str,
    majority_opinion: str
) -> str:
    """Lead writes dissent draft after seeing majority opinion."""
    labels = [chr(65 + i) for i in range(len(group_members))]
    positions_text = "\n\n".join([
        f"Justice {label}'s Position:\n{positions_by_model.get(model, 'N/A')}"
        for label, model in zip(labels, group_members)
    ])

    prompt = f"""You are the Lead Justice writing the DISSENTING Opinion for an AI Supreme Court.

Case/Question: {user_query}

THE MAJORITY OPINION (which you are dissenting from):
{majority_opinion}

Your fellow dissenters' positions (anonymized):

{positions_text}

Write a comprehensive DRAFT Dissenting Opinion that:
1. Clearly states where and why you disagree with the majority
2. Responds directly to the majority's key arguments
3. Synthesizes the strongest arguments from your fellow dissenters
4. Presents your alternative reasoning
5. Uses formal Supreme Court dissent style

Begin with "I respectfully dissent..." or similar.

DRAFT DISSENTING OPINION:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead, messages)

    return response.get('content', '') if response else "Error generating dissent draft."


async def _collect_feedback(
    user_query: str,
    draft: str,
    members: List[str],
    is_majority: bool,
    majority_opinion: str = None
) -> List[Dict[str, Any]]:
    """Collect feedback from group members on draft."""
    if not members:
        return []

    opinion_type = "Majority" if is_majority else "Dissenting"

    context = ""
    if not is_majority and majority_opinion:
        context = f"\n\nTHE MAJORITY OPINION (for reference):\n{majority_opinion}\n"

    prompt = f"""You are a Justice reviewing the DRAFT {opinion_type} Opinion written by your Lead Justice.

Case/Question: {user_query}
{context}
DRAFT {opinion_type.upper()} OPINION:
{draft}

Provide constructive feedback:
1. STRENGTHS: What does this draft do well?
2. SUGGESTIONS: What could be improved or added?
3. CONCERNS: Any arguments that need strengthening or errors to fix?

Keep feedback concise and actionable."""

    messages = [{"role": "user", "content": prompt}]
    responses = await query_models_parallel(members, messages)

    feedback = []
    for model, response in responses.items():
        if response:
            feedback.append({
                "model": model,
                "feedback": response.get('content', '')
            })

    return feedback


async def _finalize_opinion(
    user_query: str,
    draft: str,
    feedback: List[Dict[str, Any]],
    lead: str,
    is_majority: bool
) -> str:
    """Lead finalizes opinion based on feedback."""
    opinion_type = "Majority" if is_majority else "Dissenting"

    if feedback:
        feedback_text = "\n\n".join([
            f"Feedback from colleague:\n{f['feedback']}"
            for f in feedback
        ])
    else:
        feedback_text = "No additional feedback received."

    prompt = f"""You are the Lead Justice finalizing the {opinion_type} Opinion.

Case/Question: {user_query}

YOUR DRAFT:
{draft}

FEEDBACK FROM YOUR COLLEAGUES:
{feedback_text}

Now write the FINAL {opinion_type} Opinion:
1. Incorporate valuable suggestions from feedback
2. Address any concerns raised
3. Strengthen arguments where needed
4. Polish the language and structure
5. This is the official opinion of the court

FINAL {opinion_type.upper()} OPINION OF THE COURT:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead, messages)

    return response.get('content', draft) if response else draft


async def _finalize_dissent(
    user_query: str,
    draft: str,
    feedback: List[Dict[str, Any]],
    lead: str,
    majority_opinion: str
) -> str:
    """Lead finalizes dissent based on feedback."""
    if feedback:
        feedback_text = "\n\n".join([
            f"Feedback from colleague:\n{f['feedback']}"
            for f in feedback
        ])
    else:
        feedback_text = "No additional feedback received."

    prompt = f"""You are the Lead Justice finalizing the Dissenting Opinion.

Case/Question: {user_query}

THE MAJORITY OPINION:
{majority_opinion}

YOUR DRAFT DISSENT:
{draft}

FEEDBACK FROM YOUR FELLOW DISSENTERS:
{feedback_text}

Now write the FINAL Dissenting Opinion:
1. Incorporate valuable suggestions from feedback
2. Ensure all key majority arguments are addressed
3. Strengthen your counter-arguments
4. Polish the language and structure
5. This is your final, official dissent

FINAL DISSENTING OPINION:"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(lead, messages)

    return response.get('content', draft) if response else draft


async def run_supreme_court(user_query: str) -> Dict[str, Any]:
    """
    Run the complete Supreme Court deliberation.

    Flow:
    1. Stage 1: Initial positions
    2. Stage 2: Reconsideration after reading others
    3. Clerk: Group into majority/minority
    4. Stage 3: Majority draft → feedback → finalize
    5. Stage 4: Release majority opinion
    6. Stage 5: Dissent sees majority → draft → feedback → finalize
    """
    # Stage 1
    stage1_results = await stage1_initial_positions(user_query)
    if not stage1_results:
        return {"error": "All justices failed to respond."}

    # Stage 2
    stage2_results = await stage2_reconsideration(user_query, stage1_results)

    # Clerk grouping
    grouping = await clerk_group_justices(user_query, stage2_results)

    # Stage 3: Majority opinion process
    stage3_result = await stage3_majority_opinion(
        user_query, stage2_results, grouping
    )

    # Stage 4: Release majority
    majority_opinion = await stage4_release_majority(stage3_result)

    # Stage 5: Dissent (if split)
    dissent_opinion = await stage5_dissent_opinion(
        user_query, stage2_results, grouping, majority_opinion
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "grouping": grouping,
        "majority_process": stage3_result,
        "majority_opinion": majority_opinion,
        "dissent_opinion": dissent_opinion,
        "metadata": {
            "consensus": grouping['consensus'],
            "majority_count": len(grouping['majority']),
            "minority_count": len(grouping.get('minority', [])),
            "votes_changed": sum(1 for r in stage2_results if r.get('changed', False))
        }
    }

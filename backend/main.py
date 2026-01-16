"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .supreme_court import (
    run_supreme_court,
    stage1_collect_justice_opinions,
    clerk_analyze_and_group,
    stage2_within_group_rankings,
    stage3_synthesize_opinions,
    stage4_complete_majority_opinion,
    stage5_complete_dissent_opinion,
)

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ===== Supreme Court Endpoints =====

@app.post("/api/conversations/{conversation_id}/supreme-court")
async def send_supreme_court_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the Supreme Court deliberation process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the Supreme Court process
    result = await run_supreme_court(request.content)

    # Store as a special supreme court message
    storage.add_supreme_court_message(conversation_id, result)

    return result


@app.post("/api/conversations/{conversation_id}/supreme-court/stream")
async def send_supreme_court_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the Supreme Court deliberation process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect justice opinions
            yield f"data: {json.dumps({'type': 'sc_stage1_start', 'message': 'Collecting justice opinions...'})}\n\n"
            stage1_results = await stage1_collect_justice_opinions(request.content)
            yield f"data: {json.dumps({'type': 'sc_stage1_complete', 'data': stage1_results})}\n\n"

            # Clerk Stage: Analyze and group justices
            yield f"data: {json.dumps({'type': 'sc_clerk_start', 'message': 'Clerk analyzing and grouping justices...'})}\n\n"
            grouping = await clerk_analyze_and_group(request.content, stage1_results)
            yield f"data: {json.dumps({'type': 'sc_clerk_complete', 'data': grouping})}\n\n"

            # Stage 2: Within-group peer rankings
            yield f"data: {json.dumps({'type': 'sc_stage2_start', 'message': 'Within-group peer rankings...'})}\n\n"
            stage2_results = await stage2_within_group_rankings(request.content, stage1_results, grouping)
            yield f"data: {json.dumps({'type': 'sc_stage2_complete', 'data': stage2_results})}\n\n"

            # Stage 3: Leads synthesize opinions
            yield f"data: {json.dumps({'type': 'sc_stage3_start', 'message': 'Leads synthesizing opinions from peer feedback...'})}\n\n"
            stage3_results = await stage3_synthesize_opinions(request.content, stage1_results, stage2_results, grouping)
            yield f"data: {json.dumps({'type': 'sc_stage3_complete', 'data': stage3_results})}\n\n"

            # Stage 4: Majority opinion completed
            yield f"data: {json.dumps({'type': 'sc_stage4_start', 'message': 'Completing majority opinion...'})}\n\n"
            majority_opinion = await stage4_complete_majority_opinion(stage3_results)
            yield f"data: {json.dumps({'type': 'sc_stage4_complete', 'data': majority_opinion})}\n\n"

            # Stage 5: Dissenting opinion completed (if split)
            yield f"data: {json.dumps({'type': 'sc_stage5_start', 'message': 'Completing dissenting opinion...'})}\n\n"
            dissent_opinion = await stage5_complete_dissent_opinion(stage3_results, grouping['consensus'])
            yield f"data: {json.dumps({'type': 'sc_stage5_complete', 'data': dissent_opinion})}\n\n"

            # Wait for title generation
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Build complete result for storage
            result = {
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

            # Save complete message
            storage.add_supreme_court_message(conversation_id, result)

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

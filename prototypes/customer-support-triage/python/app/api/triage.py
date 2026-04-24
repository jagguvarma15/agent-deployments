"""Triage and conversation route handlers."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.classifier import classify_intent
from app.agent.specialists import run_specialist
from app.db.models import Conversation, Message
from app.db.session import get_session
from app.models.schemas import (
    ConversationOut,
    MessageOut,
    TriageRequest,
    TriageResponse,
)
from app.settings import settings

logger = structlog.get_logger()

router = APIRouter()


@router.post("/triage", response_model=TriageResponse)
async def triage(
    request: TriageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Classify intent, route to specialist, return resolution."""
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id, user_id=request.user_id)

    # Create conversation
    conversation = Conversation(user_id=request.user_id)
    session.add(conversation)

    # Store user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    session.add(user_msg)

    # Classify intent
    log.info("classifying_intent")
    classification = await classify_intent(request.message)
    log.info("intent_classified", intent=classification.intent, confidence=classification.confidence)

    user_msg.intent = classification.intent.value

    # Check escalation threshold
    if classification.confidence < settings.escalation_threshold:
        log.info("escalating", reason="low_confidence", confidence=classification.confidence)
        conversation.escalated = True
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=(
                "I'm not fully confident in my assessment. "
                "Let me connect you with a human agent who can better assist you."
            ),
            intent=classification.intent.value,
        )
        session.add(assistant_msg)
        await session.commit()

        return TriageResponse(
            conversation_id=conversation.id,
            intent=classification.intent.value,
            specialist_response="Escalated to human agent due to low classification confidence.",
            escalated=True,
            trace_id=trace_id,
        )

    # Route to specialist
    log.info("routing_to_specialist", intent=classification.intent)
    response_text, tool_calls = await run_specialist(classification.intent, request.message)
    log.info("specialist_responded", tool_calls_count=len(tool_calls))

    # Store assistant response
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        intent=classification.intent.value,
        tool_calls_json=tool_calls if tool_calls else None,
    )
    session.add(assistant_msg)

    conversation.resolved_at = datetime.now(UTC)
    await session.commit()

    return TriageResponse(
        conversation_id=conversation.id,
        intent=classification.intent.value,
        specialist_response=response_text,
        escalated=False,
        trace_id=trace_id,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Fetch a conversation with its messages."""
    result = await session.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationOut(
        id=conversation.id,
        user_id=conversation.user_id,
        created_at=conversation.created_at.isoformat(),
        resolved_at=conversation.resolved_at.isoformat() if conversation.resolved_at else None,
        escalated=conversation.escalated,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                intent=m.intent,
                tool_calls=m.tool_calls_json,
                created_at=m.created_at.isoformat(),
            )
            for m in conversation.messages
        ],
    )

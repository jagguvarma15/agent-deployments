"""Request/response schemas and domain types."""

from enum import Enum

from pydantic import BaseModel


class Intent(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"


class ClassificationResult(BaseModel):
    intent: Intent
    confidence: float
    reasoning: str


class TriageRequest(BaseModel):
    message: str
    user_id: str


class TriageResponse(BaseModel):
    conversation_id: str
    intent: str
    specialist_response: str
    escalated: bool
    trace_id: str


class ConversationOut(BaseModel):
    id: str
    user_id: str
    created_at: str
    resolved_at: str | None
    escalated: bool
    messages: list["MessageOut"]


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None
    tool_calls: list[dict] | None
    created_at: str

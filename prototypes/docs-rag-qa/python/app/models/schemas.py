"""Pydantic models for request/response validation."""

from pydantic import BaseModel


class DocumentIngestRequest(BaseModel):
    content: str
    title: str
    metadata: dict | None = None


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunk_count: int
    status: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class Citation(BaseModel):
    chunk_id: str
    document_title: str
    text: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str

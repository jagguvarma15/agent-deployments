"""Request/response schemas for research-assistant."""

from pydantic import BaseModel


class ResearchRequest(BaseModel):
    question: str
    max_steps: int = 5


class Source(BaseModel):
    title: str
    url: str
    excerpt: str


class ResearchStep(BaseModel):
    step: int
    action: str
    content: str


class ResearchResult(BaseModel):
    id: str
    question: str
    steps: list[ResearchStep]
    answer: str
    sources: list[Source]
    trace_id: str


class ResearchStatus(BaseModel):
    id: str
    status: str
    steps_completed: int

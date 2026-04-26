"""SQLAlchemy models for research sessions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Research(Base):
    __tablename__ = "researches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    question = Column(Text, nullable=False)
    status = Column(String, default="pending")
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    steps = relationship("ResearchStepModel", back_populates="research", order_by="ResearchStepModel.step_number")


class ResearchStepModel(Base):
    __tablename__ = "research_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    research_id = Column(String, ForeignKey("researches.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    research = relationship("Research", back_populates="steps")

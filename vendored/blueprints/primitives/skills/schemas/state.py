"""Canonical Pydantic v2 state schema for the Skills pattern.

Recipes that bundle skills (e.g. claude-code-subagent, research-assistant)
reference these names so frameworks can ground the skill registry, the
trigger matcher's intermediate state, and per-turn skill selection against a
shared shape. Self-contained — no cross-pattern imports.

See ``../design.md`` for the prose definition of each field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SkillRegistryEntry(BaseModel):
    """One entry in the in-memory skill registry, built at boot from SKILL.md."""

    id: str = Field(description="Kebab-case identifier, unique within the registry.")
    name: str = Field(description="Human-readable label.")
    version: str = Field(description="Semver; bumped when behavior changes.")
    description: str = Field(description="One-line purpose; the LLM judge reads this.")
    triggers: list[str] = Field(
        default_factory=list,
        description="Lowercase keywords or phrases used by Stage 1 keyword matching.",
    )
    when_to_use: str | None = Field(
        default=None,
        description="Optional activation hint complementing description for Stage 2.",
    )
    body_path: str = Field(
        description="Filesystem path to the full SKILL.md; loaded on demand.",
    )
    scripts_dir: str | None = Field(
        default=None,
        description="Path to helper scripts the skill body references, if any.",
    )


class SkillSelection(BaseModel):
    """One skill the matcher chose to activate for the current turn."""

    skill_id: str = Field(description="Identifier of the registry entry that fired.")
    activated_via: Literal["stage1_only", "stage2_judge", "explicit"] = Field(
        description=(
            "How the skill came to be selected: pure keyword match, LLM judge pick, or explicit caller override."
        ),
    )
    body_tokens: int | None = Field(
        default=None,
        description="Tokens consumed by the injected skill body; populated after load.",
    )


class SkillsState(BaseModel):
    """Per-turn state the skill subsystem carries through the agent loop.

    Tracks the user message, the registry size visible after grants are applied,
    Stage 1 candidates, and the final Stage 2 selection. Recipes can consult
    this state for trace emission and trajectory eval.
    """

    user_message: str = Field(description="The current user turn's message body.")
    registry_size: int = Field(
        default=0,
        ge=0,
        description="Number of skills available after grant-policy filtering.",
    )
    candidates: list[str] = Field(
        default_factory=list,
        description="Skill ids returned by the Stage 1 keyword matcher.",
    )
    selected: list[SkillSelection] = Field(
        default_factory=list,
        description="Final picks loaded into the agent's context for this turn.",
    )
    judge_model: str | None = Field(
        default=None,
        description="Model id used for Stage 2 judgment, if any.",
    )

    @property
    def selected_ids(self) -> list[str]:
        return [s.skill_id for s in self.selected]

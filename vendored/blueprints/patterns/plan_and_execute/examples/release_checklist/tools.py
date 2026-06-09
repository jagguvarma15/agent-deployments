"""Mock adapters for the release-checklist overlay.

Three external services the executor calls:

- :class:`CIAdapter` wraps ``GET https://ci.example.com/builds/{version}``;
  the mock returns a hand-curated table keyed by version, raising
  :class:`LookupError` for unknown versions so the executor can mark a
  build step as ``failed`` rather than crashing.
- :class:`SmokeRunner` wraps ``POST https://smoke.example.com/run``; the
  mock honours per-version + per-step "failure scenarios" in a small table
  so the walkthrough can exercise both the happy and replan paths.
- :class:`DeployAdapter` wraps ``POST https://deploy.example.com/release``;
  the mock just records the call. :class:`Verifier` wraps a downstream
  health check (``GET https://verify.example.com/healthz``) and returns
  ``ok`` / ``degraded`` / ``down``.

Real adapters swap the bodies; call signatures stay constant so the
:func:`run_release` orchestrator is unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .schemas import ReleaseEnv, ReleaseStepKind

log = logging.getLogger(__name__)


# ── Canned data ──────────────────────────────────────────────────────────────


_BUILDS: dict[str, dict[str, str]] = {
    "1.4.2": {"sha": "sha:abc123", "artifact": "registry/web:1.4.2", "status": "green"},
    "1.4.3": {"sha": "sha:def456", "artifact": "registry/web:1.4.3", "status": "green"},
    "1.5.0": {"sha": "sha:beef99", "artifact": "registry/web:1.5.0", "status": "green"},
}

# Versions whose smoke fails on a specific step kind. The replanner inserts
# a `fix` step before re-running the failing step. After the fix step, the
# smoke run for the same kind is treated as successful.
_SMOKE_FAILURES: dict[tuple[str, ReleaseStepKind], str] = {
    ("1.4.3", ReleaseStepKind.smoke): "missing_migration",
}

# Versions whose verify fails terminally — the saga aborts and the
# replanner returns `abort`. Used in the unrecoverable-failure walkthrough.
_VERIFY_TERMINAL: dict[str, str] = {
    "1.5.0": "downstream_db_unreachable",
}


# ── Adapters ────────────────────────────────────────────────────────────────


@dataclass
class CIAdapter:
    """Read-only build catalog."""

    def fetch_build(self, version: str) -> dict[str, str]:
        if version not in _BUILDS:
            raise LookupError(f"No build for {version}")
        return dict(_BUILDS[version])


@dataclass
class SmokeRunner:
    """Runs the smoke suite. Mock honours canned failure scenarios."""

    fix_applied: set[str] = field(default_factory=set)

    def run(self, version: str, target_service: str) -> dict[str, str]:
        key = (version, ReleaseStepKind.smoke)
        if key in _SMOKE_FAILURES and target_service not in self.fix_applied:
            return {
                "status": "fail",
                "reason": _SMOKE_FAILURES[key],
                "service": target_service,
            }
        return {"status": "ok", "service": target_service}

    def record_fix(self, target_service: str) -> None:
        self.fix_applied.add(target_service)


@dataclass
class DeployAdapter:
    """Records the deploy call so the verifier has something to check."""

    deployed: list[tuple[str, str, ReleaseEnv]] = field(default_factory=list)

    def deploy(self, version: str, target_service: str, env: ReleaseEnv) -> dict[str, str]:
        self.deployed.append((version, target_service, env))
        return {"status": "ok", "deployment_id": f"dep_{version}_{target_service}_{env.value}"}


@dataclass
class Verifier:
    """Health probe with canned terminal-failure scenarios."""

    def check_health(self, version: str, target_service: str) -> dict[str, str]:
        if version in _VERIFY_TERMINAL:
            return {
                "status": "down",
                "reason": _VERIFY_TERMINAL[version],
                "service": target_service,
            }
        return {"status": "ok", "service": target_service}

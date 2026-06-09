"""End-to-end walkthrough tests for the ops-crew overlay.

Runs offline — triage / executor / writer are deterministic stubs in
``main``. Real production swaps each for an ``anthropic`` Agent call.

Run:
    uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v

Or as a script:
    uv run --with pydantic python test_walkthrough.py
"""

from __future__ import annotations

from .main import handle_incident
from .schemas import Severity


def test_api_latency_incident_hits_db_pool_runbook() -> None:
    report = handle_incident("inc_001")
    assert report.incident_id == "inc_001"
    assert report.severity == Severity.sev2
    assert "rb_db_pool_exhaustion" in report.summary
    assert report.slack_channel == "#incident-inc_001"
    # Three steps in the runbook → three timeline entries above the headers (raised + triage).
    assert any("3 steps, succeeded" in line for line in report.timeline)


def test_auth_500_incident_hits_auth_runbook() -> None:
    report = handle_incident("inc_002")
    assert report.severity == Severity.sev3
    assert "rb_auth_500" in report.summary
    # sev3 → per-incident channel, not the global sev1 firehose.
    assert report.slack_channel.startswith("#incident-")


def test_unknown_incident_id_raises() -> None:
    """Hand-rolled `pytest.raises` so the file runs in plain-script mode too."""
    try:
        handle_incident("inc_does_not_exist")
    except LookupError:
        return
    raise AssertionError("expected LookupError for unknown incident id")


def _run_all() -> None:
    """Smoke entry point — run every test as a plain function."""
    test_api_latency_incident_hits_db_pool_runbook()
    print("PASS test_api_latency_incident_hits_db_pool_runbook")
    test_auth_500_incident_hits_auth_runbook()
    print("PASS test_auth_500_incident_hits_auth_runbook")
    test_unknown_incident_id_raises()
    print("PASS test_unknown_incident_id_raises")
    print("All walkthrough cases passed.")


if __name__ == "__main__":
    _run_all()

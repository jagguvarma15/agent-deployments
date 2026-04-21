"""Tests for agent_common.logs module."""

import structlog

from agent_common.logs import configure


def test_configure_does_not_raise():
    configure("test-service", env="development", log_level="DEBUG")
    logger = structlog.get_logger()
    assert logger is not None


def test_configure_production_mode():
    configure("test-service", env="production", log_level="INFO")
    logger = structlog.get_logger()
    assert logger is not None

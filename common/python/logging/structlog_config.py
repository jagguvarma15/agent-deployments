"""Structured logging configuration using structlog."""

import logging
import sys

import structlog


def configure(
    service_name: str,
    *,
    env: str = "development",
    log_level: str = "INFO",
) -> None:
    """Configure structlog for the application.

    In production (env != "development"), outputs JSON.
    In development, outputs colored, human-readable logs.

    Args:
        service_name: Name of the service (appears in every log line).
        env: Environment name ("development", "staging", "production").
        log_level: Logging level string.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env == "development":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.EventRenamer("msg"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping()[log_level.upper()]),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bind service name to all loggers
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name, env=env)

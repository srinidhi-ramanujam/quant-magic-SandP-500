"""
Telemetry and logging infrastructure for the financial analysis system.

Provides structured logging, request tracking, component timing, and performance metrics.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from src.config import get_config


@dataclass
class RequestContext:
    """Context for a single request, tracks timing and metadata."""

    request_id: str
    question: str
    start_time: float = field(default_factory=time.time)
    component_timings: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_timing(self, component: str, duration: float):
        """Add timing for a component."""
        self.component_timings[component] = duration

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the request context."""
        self.metadata[key] = value

    def elapsed(self) -> float:
        """Get total elapsed time since request start."""
        return time.time() - self.start_time


@dataclass
class TelemetryReport:
    """Summary telemetry report for a request."""

    request_id: str
    question: str
    total_time_seconds: float
    component_timings: Dict[str, float]
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "question": self.question,
            "total_time_seconds": round(self.total_time_seconds, 4),
            "component_timings": {
                k: round(v, 4) for k, v in self.component_timings.items()
            },
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logging(log_level: Optional[str] = None) -> logging.Logger:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR). If None, reads from config.

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    config = get_config()
    level = log_level or config.log_level

    # Create logger
    logger = logging.getLogger("quant_magic")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler with formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))

    # Structured log format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the global logger instance, creating it if necessary."""
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger


def create_request_context(question: str) -> RequestContext:
    """
    Create a new request context with unique ID.

    Args:
        question: The user's question

    Returns:
        New RequestContext instance
    """
    request_id = str(uuid.uuid4())[:8]
    logger = get_logger()
    logger.info(f"[{request_id}] New request: {question[:100]}")

    return RequestContext(request_id=request_id, question=question)


@contextmanager
def log_component_timing(context: RequestContext, component_name: str):
    """
    Context manager to track component execution time.

    Usage:
        with log_component_timing(context, "entity_extraction"):
            # component code here
            pass

    Args:
        context: Request context to update
        component_name: Name of the component being timed
    """
    logger = get_logger()
    start_time = time.time()

    logger.debug(f"[{context.request_id}] Starting {component_name}")

    try:
        yield
    finally:
        duration = time.time() - start_time
        context.add_timing(component_name, duration)
        logger.debug(
            f"[{context.request_id}] Completed {component_name} in {duration:.4f}s"
        )


def log_llm_call(
    context: RequestContext,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_estimate: Optional[float] = None,
):
    """
    Log an LLM API call with token usage and cost.

    Args:
        context: Request context
        model: Model name/deployment
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        cost_estimate: Estimated cost in USD (optional)
    """
    logger = get_logger()

    total_tokens = prompt_tokens + completion_tokens

    log_msg = (
        f"[{context.request_id}] LLM call - "
        f"model={model}, "
        f"tokens={total_tokens} "
        f"(prompt={prompt_tokens}, completion={completion_tokens})"
    )

    if cost_estimate:
        log_msg += f", cost=${cost_estimate:.6f}"

    logger.info(log_msg)

    # Store in context metadata
    if "llm_calls" not in context.metadata:
        context.metadata["llm_calls"] = []

    context.metadata["llm_calls"].append(
        {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_estimate": cost_estimate,
        }
    )


def log_error(
    context: RequestContext, error: Exception, component: Optional[str] = None
):
    """
    Log an error with full context.

    Args:
        context: Request context
        error: Exception that occurred
        component: Component where error occurred (optional)
    """
    logger = get_logger()

    component_info = f" in {component}" if component else ""
    logger.error(
        f"[{context.request_id}] Error{component_info}: {type(error).__name__}: {str(error)}",
        exc_info=True,
    )

    context.add_metadata("error", str(error))
    context.add_metadata("error_type", type(error).__name__)
    if component:
        context.add_metadata("error_component", component)


def generate_telemetry_report(
    context: RequestContext, success: bool = True, error: Optional[str] = None
) -> TelemetryReport:
    """
    Generate a telemetry report from a request context.

    Args:
        context: Request context
        success: Whether the request was successful
        error: Error message if request failed

    Returns:
        TelemetryReport instance
    """
    logger = get_logger()

    report = TelemetryReport(
        request_id=context.request_id,
        question=context.question,
        total_time_seconds=context.elapsed(),
        component_timings=context.component_timings.copy(),
        success=success,
        error=error,
        metadata=context.metadata.copy(),
    )

    # Log summary
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"[{context.request_id}] Request {status} in {report.total_time_seconds:.4f}s "
        f"(components: {len(context.component_timings)})"
    )

    # Log component breakdown if debug enabled
    if logger.isEnabledFor(logging.DEBUG):
        for component, duration in context.component_timings.items():
            pct = (
                (duration / report.total_time_seconds * 100)
                if report.total_time_seconds > 0
                else 0
            )
            logger.debug(f"  - {component}: {duration:.4f}s ({pct:.1f}%)")

    return report


def check_telemetry_overhead(context: RequestContext) -> float:
    """
    Calculate telemetry overhead as percentage of total execution time.

    Args:
        context: Request context

    Returns:
        Overhead percentage (0-100)
    """
    total_time = context.elapsed()
    component_time = sum(context.component_timings.values())

    if total_time == 0:
        return 0.0

    overhead = total_time - component_time
    overhead_pct = (overhead / total_time) * 100

    return max(0.0, overhead_pct)


# Initialize logging on module import if telemetry is enabled
config = get_config()
if config.enable_telemetry:
    setup_logging()

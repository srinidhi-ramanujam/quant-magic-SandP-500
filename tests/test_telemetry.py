"""
Tests for telemetry and logging infrastructure.
"""

import logging
import time

from src.telemetry import (
    setup_logging,
    create_request_context,
    log_component_timing,
    generate_telemetry_report,
    check_telemetry_overhead,
)


def test_setup_logging():
    """Test that logging setup works correctly."""
    logger = setup_logging("INFO")

    assert logger is not None
    assert logger.name == "quant_magic"
    assert logger.level == logging.INFO
    assert len(logger.handlers) > 0


def test_create_request_context():
    """Test creating a request context."""
    question = "What is Apple's CIK?"
    context = create_request_context(question)

    assert context.request_id is not None
    assert len(context.request_id) == 8  # UUID shortened to 8 chars
    assert context.question == question
    assert context.start_time > 0
    assert context.elapsed() >= 0


def test_log_component_timing():
    """Test component timing tracking."""
    context = create_request_context("Test question")

    # Simulate component execution
    with log_component_timing(context, "test_component"):
        time.sleep(0.01)  # Sleep for 10ms

    # Check timing was recorded
    assert "test_component" in context.component_timings
    assert context.component_timings["test_component"] >= 0.01
    assert context.component_timings["test_component"] < 0.1  # Should be quick


def test_generate_telemetry_report():
    """Test generating a telemetry report."""
    context = create_request_context("Test question")

    # Add some timings
    context.add_timing("component1", 0.05)
    context.add_timing("component2", 0.03)

    # Generate report
    report = generate_telemetry_report(context, success=True)

    assert report.request_id == context.request_id
    assert report.question == "Test question"
    assert report.success is True
    assert report.error is None
    assert len(report.component_timings) == 2
    assert "component1" in report.component_timings
    assert "component2" in report.component_timings

    # Test to_dict serialization
    report_dict = report.to_dict()
    assert isinstance(report_dict, dict)
    assert "request_id" in report_dict
    assert "total_time_seconds" in report_dict


def test_error_tracking():
    """Test error tracking in telemetry."""
    context = create_request_context("Test question with error")

    # Add metadata
    context.add_metadata("test_key", "test_value")

    # Generate error report
    report = generate_telemetry_report(
        context, success=False, error="Test error message"
    )

    assert report.success is False
    assert report.error == "Test error message"
    assert context.metadata.get("test_key") == "test_value"


def test_telemetry_overhead():
    """Test telemetry overhead calculation."""
    context = create_request_context("Overhead test")

    # Add some component timings
    context.add_timing("comp1", 0.05)
    context.add_timing("comp2", 0.03)

    # Wait a bit to accumulate total time
    time.sleep(0.01)

    # Calculate overhead
    overhead = check_telemetry_overhead(context)

    # Overhead should be positive but small
    assert overhead >= 0
    assert overhead < 50  # Should be less than 50% overhead

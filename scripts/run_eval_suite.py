#!/usr/bin/env python3
"""
Batch runner for evaluation question suites with workbook logging.

Usage examples:
  python scripts/run_eval_suite.py --suite simple
  python scripts/run_eval_suite.py --suite simple --suite medium --suite time-series
  python scripts/run_eval_suite.py --question "How many companies are in the Energy sector?" --expected "51"

The script appends each run to evaluation/EVAL_WORKBOOK.csv. Create the directory
with `mkdir -p evaluation/logs` (or any preferred location) before running if you
intend to redirect stdout separately.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli import FinancialCLI


EVAL_WORKBOOK = Path("evaluation/EVAL_WORKBOOK.csv")
EVALUATION_FILES: Dict[str, str] = {
    "simple": "evaluation/questions/simple_lineitem.json",
    "medium": "evaluation/questions/medium_analysis.json",
    "time-series": "evaluation/questions/time_series_analysis.json",
}
FIELDNAMES = [
    "Testrun_ID",
    "Timestamp",
    "Tier",
    "Question",
    "SQL_template",
    "SQL_generated",
    "Answer_received",
    "Answer_expected",
    "Quality",
    "Confidence",
    "Generation_method",
    "LLM_calls",
    "Total_latency_s",
    "Entity_extraction_s",
    "SQL_generation_s",
    "Query_execution_s",
    "Response_formatting_s",
]


def load_questions(suite: str) -> List[Dict]:
    """Load evaluation questions for a suite."""
    path = Path(EVALUATION_FILES[suite])
    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation file not found for suite '{suite}': {path}"
        )
    data = json.loads(path.read_text())
    return data.get("questions", [])


def next_run_id(csv_path: Path) -> str:
    """Compute the next run identifier based on the workbook."""
    if not csv_path.exists():
        return "RUN_001"

    last_id: Optional[str] = None
    with csv_path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            last_id = row.get("Testrun_ID") or last_id

    if not last_id:
        return "RUN_001"

    try:
        prefix, number = last_id.split("_")
        return f"{prefix}_{int(number) + 1:03d}"
    except Exception:  # pragma: no cover - defensive
        return "RUN_001"


def format_timestamp(dt: datetime) -> str:
    """Format timestamp as '06 Nov 2025, 1300 hours'."""
    return dt.strftime("%d %b %Y, %H00 hours")


def extract_numeric(text: str) -> Optional[float]:
    """Extract the first numeric value from a string."""
    if not text:
        return None
    cleaned = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def compute_quality(expected: Optional[Dict], answer: str) -> str:
    """
    Return a quality score (1-5) comparing expected vs answer.
    5 = match within tolerance/exact, 3 = near miss, 1 = mismatch, '' = not evaluated.
    """
    if not expected or "value" not in expected:
        return ""

    expected_value = expected.get("value")
    expected_type = (expected.get("type") or "").lower()
    answer = answer or ""

    if expected_type in {"numeric", "percentage", "statistical_value"}:
        try:
            expected_num = float(str(expected_value).replace(",", ""))
        except ValueError:
            return ""

        actual_num = extract_numeric(answer)
        if actual_num is None:
            return "1"

        tolerance = expected.get("tolerance", {}) or {}
        abs_tol = tolerance.get("absolute")
        rel_tol = tolerance.get("relative") or tolerance.get("percentage")
        if abs_tol is not None and abs(actual_num - expected_num) <= abs_tol:
            return "5"
        if rel_tol is not None and expected_num != 0:
            rel_tol = rel_tol / 100 if rel_tol > 1 else rel_tol
            if abs(actual_num - expected_num) / abs(expected_num) <= rel_tol:
                return "5"
        # near miss bands: within 2x tolerance -> 3
        band_abs = abs_tol * 2 if abs_tol is not None else None
        band_rel = rel_tol * 2 if rel_tol is not None else None
        if band_abs is not None and abs(actual_num - expected_num) <= band_abs:
            return "3"
        if band_rel is not None and expected_num != 0:
            if abs(actual_num - expected_num) / abs(expected_num) <= band_rel:
                return "3"
        return "1"

    # Text comparison
    expected_str = str(expected_value).strip().lower()
    if not expected_str:
        return ""

    answer_lower = answer.strip().lower()
    if expected_str in answer_lower:
        return "5"

    for alt in expected.get("alternatives", []) or []:
        if str(alt).strip().lower() in answer_lower:
            return "5"

    # fuzzy fallback
    from difflib import SequenceMatcher

    ratio = SequenceMatcher(None, expected_str, answer_lower).ratio()
    if ratio >= 0.85:
        return "4"
    if ratio >= 0.6:
        return "3"

    return "1"


def expected_to_string(expected: Optional[Dict]) -> str:
    if not expected:
        return ""
    try:
        return json.dumps(expected)
    except Exception:
        return str(expected)


def ensure_header(csv_path: Path) -> None:
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()


def log_entry(csv_path: Path, row: Dict[str, str]) -> None:
    ensure_header(csv_path)
    with csv_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writerow(row)


def run_suite(
    cli: FinancialCLI,
    suite: str,
    questions: Iterable[Dict],
    run_id: str,
    timestamp: str,
    emit_json: bool,
) -> None:
    for item in questions:
        service_result = cli.query_service.run(item["question"], debug_mode=True)
        response = service_result.response
        response_dict = response.to_dict()

        metadata = response_dict.get("metadata", {})
        debug_info = response_dict.get("debug_info", {})

        template_id = metadata.get("template_id") or debug_info.get("metadata", {}).get(
            "template_id"
        )
        sql_generated = debug_info.get("sql_executed") or metadata.get("generated_sql")

        expected = item.get("expected_answer")
        answer = response_dict.get("answer", "")
        quality = compute_quality(expected, answer)

        row = {
            "Testrun_ID": run_id,
            "Timestamp": timestamp,
            "Tier": suite,
            "Question": item["question"],
            "SQL_template": template_id or "",
            "SQL_generated": sql_generated or "",
            "Answer_received": answer,
            "Answer_expected": expected_to_string(expected),
            "Quality": quality,
            "Confidence": f"{response_dict.get('confidence', 0):.3f}",
            "Generation_method": metadata.get("generation_method", ""),
            "LLM_calls": str(metadata.get("llm_calls")),
            "Total_latency_s": f"{metadata.get('total_time_seconds', 0):.4f}",
            "Entity_extraction_s": f"{metadata.get('component_timings', {}).get('entity_extraction', 0):.4f}",
            "SQL_generation_s": f"{metadata.get('component_timings', {}).get('sql_generation', 0):.4f}",
            "Query_execution_s": f"{metadata.get('component_timings', {}).get('query_execution', 0):.4f}",
            "Response_formatting_s": f"{metadata.get('component_timings', {}).get('response_formatting', 0):.4f}",
        }
        log_entry(EVAL_WORKBOOK, row)

        if emit_json:
            record = {
                "suite": suite,
                "id": item.get("id"),
                "question": item["question"],
                "expected_answer": expected,
                "response": response_dict,
                "quality": quality,
            }
            print(json.dumps(record, ensure_ascii=False))


def run_custom_questions(
    cli: FinancialCLI,
    questions: Sequence[str],
    expected_values: Optional[Sequence[str]],
    run_id: str,
    timestamp: str,
    emit_json: bool,
) -> None:
    expected_values = expected_values or []
    if expected_values and len(expected_values) != len(questions):
        raise ValueError(
            "Number of --expected values must match number of --question entries."
        )

    for idx, question in enumerate(questions):
        expected_value = expected_values[idx] if idx < len(expected_values) else None
        expected = {"value": expected_value, "type": "text"} if expected_value else None

        response = cli.process_question(question, debug_mode=True)
        response_dict = response.to_dict()
        metadata = response_dict.get("metadata", {})
        debug_info = response_dict.get("debug_info", {})

        template_id = metadata.get("template_id") or debug_info.get("metadata", {}).get(
            "template_id"
        )
        sql_generated = debug_info.get("sql_executed") or metadata.get("generated_sql")
        answer = response_dict.get("answer", "")
        quality = compute_quality(expected, answer)

        row = {
            "Testrun_ID": run_id,
            "Timestamp": timestamp,
            "Tier": "custom",
            "Question": question,
            "SQL_template": template_id or "",
            "SQL_generated": sql_generated or "",
            "Answer_received": answer,
            "Answer_expected": expected_to_string(expected),
            "Quality": quality,
        }
        log_entry(EVAL_WORKBOOK, row)

        if emit_json:
            record = {
                "suite": "custom",
                "question": question,
                "expected_answer": expected,
                "response": response_dict,
                "quality": quality,
            }
            print(json.dumps(record, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run evaluation question suites and log results to EVAL_WORKBOOK.csv"
    )
    parser.add_argument(
        "--suite",
        action="append",
        choices=list(EVALUATION_FILES.keys()),
        help="One or more suites to run (default: simple)",
    )
    parser.add_argument(
        "--connectivity",
        action="store_true",
        help="Include a connectivity smoke question before suites.",
    )
    parser.add_argument(
        "--question",
        action="append",
        help="Custom question to run (can be specified multiple times).",
    )
    parser.add_argument(
        "--expected",
        action="append",
        help="Expected answer for the corresponding --question (optional).",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Suppress JSON output (only logs to CSV).",
    )
    args = parser.parse_args()

    suites = args.suite or []
    custom_questions = args.question or []

    if not suites and not custom_questions and not args.connectivity:
        suites = ["simple"]

    run_id = next_run_id(EVAL_WORKBOOK)
    timestamp = format_timestamp(datetime.now())
    emit_json = not args.no_json

    cli = FinancialCLI()

    try:
        if args.connectivity:
            response = cli.process_question(
                "How many S&P 500 companies are in the Information Technology sector?",
                debug_mode=True,
            )
            response_dict = response.to_dict()
            metadata = response_dict.get("metadata", {})
            debug_info = response_dict.get("debug_info", {})

            row = {
                "Testrun_ID": run_id,
                "Timestamp": timestamp,
                "Tier": "connectivity",
                "Question": "How many S&P 500 companies are in the Information Technology sector?",
                "SQL_template": metadata.get("template_id", ""),
                "SQL_generated": debug_info.get("sql_executed")
                or metadata.get("generated_sql", ""),
                "Answer_received": response_dict.get("answer", ""),
                "Answer_expected": "",
                "Quality": "",
            }
            log_entry(EVAL_WORKBOOK, row)
            if emit_json:
                print(
                    json.dumps(
                        {"suite": "connectivity", "response": response_dict},
                        ensure_ascii=False,
                    )
                )

        for suite in suites:
            questions = load_questions(suite)
            run_suite(cli, suite, questions, run_id, timestamp, emit_json)

        if custom_questions:
            run_custom_questions(
                cli,
                custom_questions,
                args.expected,
                run_id,
                timestamp,
                emit_json,
            )

    finally:
        cli.close()


if __name__ == "__main__":
    main()

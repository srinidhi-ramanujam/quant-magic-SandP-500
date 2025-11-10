#!/usr/bin/env python3
"""
Export template metadata from query_intelligence.parquet into JSON.

The generated JSON acts as the single editable source for template
intent definitions that feed the vector store.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PARQUET_PATH = ROOT / "data" / "parquet" / "query_intelligence.parquet"
OUTPUT_PATH = ROOT / "data" / "template_intents.json"


def load_templates() -> pd.DataFrame:
    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"Template parquet not found: {PARQUET_PATH}. "
            "Ensure data/parquet is available before exporting."
        )
    return pd.read_parquet(PARQUET_PATH)


def normalize_parameters(raw_params) -> list[str]:
    if isinstance(raw_params, list):
        return raw_params
    if isinstance(raw_params, str):
        try:
            parsed = json.loads(raw_params)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    return []


def build_entries(df: pd.DataFrame) -> list[dict]:
    entries: list[dict] = []
    for _, row in df.iterrows():
        template_id = row["template_id"]
        intent_text = (
            row.get("description")
            or row.get("name")
            or row.get("intent_category")
            or row.get("natural_language_pattern")
            or ""
        )
        pattern = row.get("natural_language_pattern") or ""
        example_questions = []

        if isinstance(row.get("example_questions"), list):
            example_questions = row["example_questions"]
        elif pattern:
            example_questions = [pattern]

        entry = {
            "template_id": template_id,
            "intent_text": intent_text.strip(),
            "pattern": pattern.strip(),
            "example_questions": example_questions,
            "metadata": {
                "parameters": normalize_parameters(row.get("parameters")),
                "intent_category": row.get("intent_category"),
            },
        }
        entries.append(entry)
    return entries


def main() -> None:
    df = load_templates()
    entries = build_entries(df)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(entries, indent=2))
    print(f"Wrote {len(entries)} template intent entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

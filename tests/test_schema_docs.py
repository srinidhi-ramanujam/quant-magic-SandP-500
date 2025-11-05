"""
Tests for schema documentation utilities.
"""

import pytest

from src import schema_docs


def test_list_tables_returns_known_tables():
    tables = schema_docs.list_tables()
    assert tables == ["companies", "sub", "num", "tag", "pre"]


def test_get_table_spec_contains_columns():
    spec = schema_docs.get_table_spec("companies")
    assert spec.name == "companies"
    assert any(col.name == "cik" for col in spec.columns)
    assert spec.primary_keys == ["cik"]


def test_render_schema_markdown_contains_join_guidance():
    markdown = schema_docs.render_schema_markdown()
    assert "Join Guidance" in markdown
    assert "companies" in markdown
    assert "num` records do **not** include `cik`" in markdown


def test_schema_for_prompt_matches_renderer():
    assert schema_docs.schema_for_prompt() == schema_docs.render_schema_markdown()

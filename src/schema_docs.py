"""
Schema documentation helpers for the financial analysis platform.

This module exposes structured metadata about the DuckDB views we register in
`QueryEngine`.  It is designed to support LLM prompts as well as human
developers when reasoning about joins and commonly used metrics.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ColumnSpec:
    """Simple column definition for schema annotations."""

    name: str
    description: str


@dataclass(frozen=True)
class TableSpec:
    """Declarative table description used by prompt builders."""

    name: str
    description: str
    columns: List[ColumnSpec]
    primary_keys: List[str] = field(default_factory=list)
    sample_filters: List[str] = field(default_factory=list)


_TABLES: Dict[str, TableSpec] = {
    "companies": TableSpec(
        name="companies",
        description="S&P 500 reference data with sector and incorporation details.",
        columns=[
            ColumnSpec("cik", "Unique SEC issuer identifier (10 digit string)."),
            ColumnSpec("name", "Canonical company name (uppercase)."),
            ColumnSpec("sic", "SIC industry code (nullable)."),
            ColumnSpec("countryinc", "Country of incorporation."),
            ColumnSpec("gics_sector", "GICS sector classification."),
        ],
        primary_keys=["cik"],
        sample_filters=[
            "gics_sector = 'Information Technology'",
            "name LIKE '%APPLE%'",
        ],
    ),
    "sub": TableSpec(
        name="sub",
        description="SEC submission metadata for 10-K/10-Q filings.",
        columns=[
            ColumnSpec("adsh", "Accession number for the filing."),
            ColumnSpec("cik", "Issuer CIK for the filing."),
            ColumnSpec("form", "SEC form type (10-K, 10-Q, etc.)."),
            ColumnSpec("period", "Reporting period end date (TIMESTAMP)."),
            ColumnSpec("fy", "Fiscal year (integer)."),
            ColumnSpec("fp", "Fiscal period (FY, Q1, Q2, Q3, Q4)."),
            ColumnSpec("stprba", "Headquarters state / province."),
            ColumnSpec("countryba", "Headquarters country."),
            ColumnSpec("stprinc", "Incorporation state / province."),
            ColumnSpec("filed", "Date filing was submitted."),
        ],
        primary_keys=["adsh"],
        sample_filters=[
            "form = '10-K'",
            "fy >= 2020",
        ],
    ),
    "num": TableSpec(
        name="num",
        description="Numeric XBRL facts (financial metrics).",
        columns=[
            ColumnSpec("adsh", "Accession number linking to `sub`."),
            ColumnSpec("tag", "XBRL concept name (e.g. Revenues)."),
            ColumnSpec("version", "Taxonomy version for the tag."),
            ColumnSpec("ddate", "Date the fact applies to."),
            ColumnSpec("qtrs", "Number of quarters represented (0 = annual)."),
            ColumnSpec("uom", "Unit of measure."),
            ColumnSpec("value", "Numeric value (DOUBLE)."),
            ColumnSpec("footnote", "Associated footnote if present."),
        ],
        primary_keys=["adsh", "tag", "ddate", "qtrs"],
        sample_filters=[
            "tag IN ('Revenues', 'NetIncomeLoss')",
            "qtrs IN (0, 1)",
        ],
    ),
    "tag": TableSpec(
        name="tag",
        description="XBRL taxonomy metadata describing available tags.",
        columns=[
            ColumnSpec("tag", "Canonical tag name."),
            ColumnSpec("version", "Taxonomy version."),
            ColumnSpec("datatype", "Underlying data type."),
            ColumnSpec("abstract", "Whether this tag is abstract (Y/N)."),
            ColumnSpec("description", "Long-form tag description (if present)."),
        ],
        primary_keys=["tag", "version"],
    ),
    "pre": TableSpec(
        name="pre",
        description="Presentation linkbase for statements (line ordering).",
        columns=[
            ColumnSpec("adsh", "Accession number."),
            ColumnSpec("stmt", "Statement identifier (e.g. BS, IS, CF)."),
            ColumnSpec("line", "Line number within the statement."),
            ColumnSpec("tag", "Tag used on the statement line."),
            ColumnSpec("plabel", "Presentation label."),
        ],
        primary_keys=["adsh", "stmt", "line"],
    ),
}


JOIN_GUIDANCE = """
- `companies` ↔ `sub`: join on `companies.cik = sub.cik`
- `sub` ↔ `num`: join on `sub.adsh = num.adsh`
- `sub` ↔ `pre`: join on `sub.adsh = pre.adsh`
- `num` records do **not** include `cik`; you must join through `sub`
- When you need a CIK in results, select `sub.cik` (or join to `companies`) — never reference `num.cik`
- For annual values use `num.qtrs = 0`; for quarterly values use `num.qtrs = 1`
"""

COMMON_METRIC_TAGS: Dict[str, List[str]] = {
    "revenue": ["Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "assets": ["Assets"],
    "equity": ["StockholdersEquity"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "debt": ["LongTermDebt", "DebtCurrent"],
    "operating_income": ["OperatingIncomeLoss"],
    "cash_flow_operating": ["NetCashProvidedByUsedInOperatingActivities"],
}


def list_tables() -> List[str]:
    """Return the ordered list of table names we expose."""
    return list(_TABLES.keys())


def get_table_spec(name: str) -> TableSpec:
    """Fetch a table specification by name (case-sensitive)."""
    return _TABLES[name]


def render_table_spec(table: TableSpec) -> str:
    """Render a single table spec as markdown bullet list."""
    column_lines = "\n".join(
        f"    - `{col.name}` – {col.description}" for col in table.columns
    )
    pk = ", ".join(table.primary_keys) if table.primary_keys else "n/a"
    sample_filters = (
        "\n".join(
            f"    - `{filter_example}`" for filter_example in table.sample_filters
        )
        if table.sample_filters
        else ""
    )
    sample_block = (
        f"\n  Sample filters:\n{sample_filters}\n" if sample_filters else "\n"
    )
    return (
        f"- **{table.name}**: {table.description}\n"
        f"  Primary keys: {pk}\n"
        f"  Columns:\n{column_lines}"
        f"{sample_block}"
    )


def render_schema_markdown() -> str:
    """Return a prompt-friendly markdown summary of the core schema."""
    sections = [render_table_spec(spec) for spec in _TABLES.values()]
    metric_lines = [
        f"- **{friendly}**: {', '.join(tags)}"
        for friendly, tags in COMMON_METRIC_TAGS.items()
    ]
    return (
        "### Core Tables\n"
        + "\n".join(sections)
        + "\n### Join Guidance\n"
        + JOIN_GUIDANCE.strip()
        + "\n\n### Common Metric Tags\n"
        + "\n".join(metric_lines)
    )


def schema_for_prompt() -> str:
    """Convenience alias used by prompt builders."""
    return render_schema_markdown()


__all__ = [
    "ColumnSpec",
    "TableSpec",
    "COMMON_METRIC_TAGS",
    "JOIN_GUIDANCE",
    "get_table_spec",
    "list_tables",
    "render_schema_markdown",
    "schema_for_prompt",
]

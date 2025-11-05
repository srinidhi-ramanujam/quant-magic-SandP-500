"""
Regression checks against the DuckDB-backed company dataset.

Ensures we can surface canonical company metadata across sectors and that
financial metrics remain populated for marquee issuers.
"""

from src.query_engine import QueryEngine


def test_top_ten_companies_per_sector_have_core_fields():
    """Verify each sector exposes up to ten companies with populated metadata."""
    qe = QueryEngine()
    try:
        counts = qe.execute(
            """
            SELECT gics_sector, COUNT(DISTINCT cik) AS company_count
            FROM companies
            WHERE gics_sector IS NOT NULL
            GROUP BY gics_sector
            """
        )

        ranked = qe.execute(
            """
            WITH base AS (
                SELECT
                    gics_sector,
                    cik,
                    name,
                    countryinc,
                    ROW_NUMBER() OVER (
                        PARTITION BY gics_sector, cik
                        ORDER BY countryinc DESC NULLS LAST, name
                    ) AS rn
                FROM companies
                WHERE gics_sector IS NOT NULL
                  AND cik IS NOT NULL
            ),
            ranked_companies AS (
                SELECT
                    gics_sector,
                    name,
                    cik,
                    countryinc,
                    ROW_NUMBER() OVER (
                        PARTITION BY gics_sector
                        ORDER BY name
                    ) AS sector_rank
                FROM base
                WHERE rn = 1
            )
            SELECT gics_sector, name, cik, countryinc
            FROM ranked_companies
            WHERE sector_rank <= 10
            ORDER BY gics_sector, sector_rank
            """
        )
    finally:
        qe.close()

    assert not ranked.empty

    counts_map = counts.set_index("gics_sector")["company_count"].to_dict()
    expected_total = sum(min(10, int(count)) for count in counts_map.values())
    assert len(ranked) == expected_total

    for sector, total in counts_map.items():
        sector_slice = ranked[ranked["gics_sector"] == sector]
        assert len(sector_slice) == min(10, int(total))
        assert sector_slice["name"].notna().all()
        assert sector_slice["cik"].notna().all()

        # countryinc can be null for some cross-border listings but should not be blank everywhere
        assert sector_slice["countryinc"].notna().any()


def test_flagship_companies_have_revenue_facts():
    """Confirm that key companies retain annual revenue facts in the metrics table."""
    qe = QueryEngine()
    try:
        revenue_df = qe.execute(
            """
            SELECT c.name, COUNT(*) AS fact_rows
            FROM num n
            JOIN sub s ON s.adsh = n.adsh
            JOIN companies c ON c.cik = s.cik
            WHERE n.tag IN ('Revenues', 'SalesRevenueNet')
              AND c.name IN (
                'MERCK & CO., INC.',
                'AT&T INC.',
                'LOCKHEED MARTIN CORP',
                'CATERPILLAR INC',
                'AMERICAN ELECTRIC POWER CO INC'
              )
            GROUP BY c.name
            """
        )
    finally:
        qe.close()

    expected_names = {
        "MERCK & CO., INC.",
        "AT&T INC.",
        "LOCKHEED MARTIN CORP",
        "CATERPILLAR INC",
        "AMERICAN ELECTRIC POWER CO INC",
    }

    assert set(revenue_df["name"]) == expected_names
    assert (revenue_df["fact_rows"] > 0).all()


def test_flagship_companies_have_net_income_and_assets():
    """Ensure marquee issuers expose both net income and assets metrics."""
    companies = (
        "MERCK & CO., INC.",
        "AT&T INC.",
        "LOCKHEED MARTIN CORP",
        "AMERICAN ELECTRIC POWER CO INC",
        "PROCTER & GAMBLE CO",
    )

    qe = QueryEngine()
    try:
        metrics_df = qe.execute(
            f"""
            SELECT
                c.name,
                SUM(CASE WHEN n.tag = 'NetIncomeLoss' THEN 1 ELSE 0 END) AS net_income_rows,
                SUM(CASE WHEN n.tag = 'Assets' THEN 1 ELSE 0 END) AS asset_rows
            FROM num n
            JOIN sub s ON s.adsh = n.adsh
            JOIN companies c ON c.cik = s.cik
            WHERE n.tag IN ('NetIncomeLoss', 'Assets')
              AND c.name IN ({','.join(f"'{name}'" for name in companies)})
            GROUP BY c.name
            """
        )
    finally:
        qe.close()

    assert set(metrics_df["name"]) == set(companies)
    assert (metrics_df["net_income_rows"] > 0).all()
    assert (metrics_df["asset_rows"] > 0).all()

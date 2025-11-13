WITH sector_companies AS (
    SELECT
        cik,
        name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest AS (
    SELECT * FROM filings WHERE rn = 1
),
ratios AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(CASE WHEN n.tag = 'AssetsCurrent' THEN n.value END) / NULLIF(MAX(CASE WHEN n.tag = 'LiabilitiesCurrent' THEN n.value END), 0) AS current_ratio
    FROM latest lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN ('AssetsCurrent', 'LiabilitiesCurrent')
    GROUP BY lf.cik, lf.fiscal_year
),
pivoted AS (
    SELECT
        sc.canonical_name,
        ANY_VALUE(sc.name) AS display_name,
        ROUND(MAX(CASE WHEN fiscal_year = {start_year} THEN current_ratio END), 2) AS ratio_start,
        ROUND(MAX(CASE WHEN fiscal_year = {end_year} THEN current_ratio END), 2) AS ratio_end
    FROM ratios r
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
    HAVING COUNT(DISTINCT fiscal_year) >= 2
)
SELECT
    display_name AS name,
    ratio_start AS ratio_{start_year},
    ratio_end AS ratio_{end_year},
    ROUND(ratio_end - ratio_start, 2) AS improvement
FROM pivoted
WHERE ratio_start IS NOT NULL
  AND ratio_end IS NOT NULL
ORDER BY improvement DESC, name
LIMIT {limit};

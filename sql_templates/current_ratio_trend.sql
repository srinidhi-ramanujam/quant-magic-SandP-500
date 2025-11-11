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
      AND s.fy BETWEEN 2019 AND 2023
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
        ROUND(MAX(CASE WHEN fiscal_year = 2019 THEN current_ratio END), 2) AS ratio_2019,
        ROUND(MAX(CASE WHEN fiscal_year = 2020 THEN current_ratio END), 2) AS ratio_2020,
        ROUND(MAX(CASE WHEN fiscal_year = 2021 THEN current_ratio END), 2) AS ratio_2021,
        ROUND(MAX(CASE WHEN fiscal_year = 2022 THEN current_ratio END), 2) AS ratio_2022,
        ROUND(MAX(CASE WHEN fiscal_year = 2023 THEN current_ratio END), 2) AS ratio_2023
    FROM ratios r
    JOIN sector_companies sc USING (cik)
    GROUP BY sc.canonical_name
    HAVING COUNT(DISTINCT fiscal_year) = 5
)
SELECT
    display_name AS name,
    ratio_2019,
    ratio_2020,
    ratio_2021,
    ratio_2022,
    ratio_2023,
    ROUND(ratio_2023 - ratio_2019, 2) AS improvement
FROM pivoted
WHERE ratio_2019 IS NOT NULL
  AND ratio_2023 IS NOT NULL
ORDER BY improvement DESC, name
LIMIT 10;

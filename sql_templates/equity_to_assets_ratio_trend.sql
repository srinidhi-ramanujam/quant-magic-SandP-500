WITH sector_companies AS (
    SELECT
        cik,
        name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(name)), '[^A-Z0-9]', '', 'g') AS canonical_name
    FROM companies
    WHERE (UPPER('{sector}') = 'ALL' OR LOWER(gics_sector) LIKE LOWER('%{sector}%'))
),
ranked_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM ranked_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                ) THEN n.value
            END
        ) AS equity,
        MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) AS assets
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        'Assets'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
ratios AS (
    SELECT
        sc.canonical_name,
        sc.display_name,
        av.fiscal_year,
        CASE
            WHEN av.assets IS NULL OR av.assets = 0 THEN NULL
            WHEN av.equity IS NULL THEN NULL
            ELSE av.equity / av.assets
        END AS equity_to_assets_ratio
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
pivoted AS (
    SELECT
        canonical_name,
        ANY_VALUE(display_name) AS name,
        MAX(CASE WHEN fiscal_year = {start_year} THEN equity_to_assets_ratio END) AS ratio_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN equity_to_assets_ratio END) AS ratio_end
    FROM ratios
    GROUP BY canonical_name
    HAVING COUNT(
        DISTINCT CASE
            WHEN fiscal_year IN ({start_year}, {end_year}) THEN fiscal_year
        END
    ) = 2
       AND MIN(ratio_start) IS NOT NULL
       AND MIN(ratio_end) IS NOT NULL
)
SELECT
    name,
    ROUND(ratio_start * 100, 2) AS ratio_{start_year}_pct,
    ROUND(ratio_end * 100, 2) AS ratio_{end_year}_pct,
    ROUND((ratio_end - ratio_start) * 100, 2) AS change_pp
FROM pivoted
ORDER BY change_pp DESC, name
LIMIT {limit};

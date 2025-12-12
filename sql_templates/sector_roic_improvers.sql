WITH sector_companies AS (
    SELECT cik, name AS company
    FROM companies
    WHERE '{sector}' = 'ALL' OR UPPER(gics_sector) LIKE UPPER('%{sector}%')
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        s.filed,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN sector_companies sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT * FROM annual_filings WHERE rn = 1
),
annual_values AS (
    SELECT
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'OperatingIncomeLoss',
                    'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
                ) THEN n.value
            END
        ) AS operating_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Assets',
                    'AssetsCurrent'
                ) THEN n.value
            END
        ) AS assets,
        MAX(
            CASE
                WHEN n.tag IN (
                    'CashAndCashEquivalentsAtCarryingValue',
                    'CashCashEquivalentsAndShortTermInvestments'
                ) THEN n.value
            END
        ) AS cash
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'OperatingIncomeLoss',
        'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments',
        'Assets',
        'AssetsCurrent',
        'CashAndCashEquivalentsAtCarryingValue',
        'CashCashEquivalentsAndShortTermInvestments'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
roic_series AS (
    SELECT
        sc.company,
        av.fiscal_year,
        av.operating_income,
        av.assets,
        av.cash,
        CASE
            WHEN av.assets IS NULL OR av.assets = 0 THEN NULL
            ELSE av.operating_income / NULLIF(av.assets - COALESCE(av.cash, 0), 0)
        END AS roic
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
    WHERE av.assets IS NOT NULL
),
paired AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        MAX(CASE WHEN fiscal_year = {start_year} THEN roic END) AS roic_start,
        MAX(CASE WHEN fiscal_year = {end_year} THEN roic END) AS roic_end,
        AVG(roic) AS avg_roic
    FROM roic_series
    GROUP BY company
    HAVING year_count >= {min_years}
       AND roic_start IS NOT NULL
       AND roic_end IS NOT NULL
),
scored AS (
    SELECT
        company,
        year_count,
        roic_start,
        roic_end,
        avg_roic,
        (roic_end - roic_start) AS roic_change
    FROM paired
)
SELECT
    company,
    year_count,
    ROUND(roic_start * 100, 2) AS roic_start_pct,
    ROUND(roic_end * 100, 2) AS roic_end_pct,
    ROUND(roic_change * 100, 2) AS roic_change_pp,
    ROUND(avg_roic * 100, 2) AS avg_roic_pct
FROM scored
ORDER BY roic_change DESC, roic_end DESC
LIMIT {limit};


WITH sector_companies AS (
    SELECT
        c.cik,
        c.name AS display_name,
        REGEXP_REPLACE(UPPER(TRIM(c.name)), '[^A-Z0-9]', '', 'g') AS canonical_name,
        ROW_NUMBER() OVER (PARTITION BY c.cik ORDER BY c.name) AS rn
    FROM companies c
    WHERE {use_sector_filter} = 0
       OR (UPPER('{sector}') = 'ALL' OR LOWER(c.gics_sector) LIKE LOWER('%{sector}%'))
),
company_seed AS (
    SELECT cik, display_name, canonical_name
    FROM sector_companies
    WHERE rn = 1
),
annual_filings AS (
    SELECT
        s.adsh,
        s.cik,
        CAST(s.fy AS INTEGER) AS fiscal_year,
        s.period,
        ROW_NUMBER() OVER (PARTITION BY s.cik, s.fy ORDER BY s.filed DESC) AS rn
    FROM sub s
    JOIN company_seed sc USING (cik)
    WHERE s.form IN ('10-K', '10-K/A', '20-F')
      AND s.fy BETWEEN {start_year} AND {end_year}
),
latest_filings AS (
    SELECT adsh, cik, fiscal_year, period
    FROM annual_filings
    WHERE rn = 1
),
annual_values AS (
    SELECT
        sc.display_name AS company,
        sc.canonical_name,
        lf.cik,
        lf.fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'NetIncomeLoss',
                    'NetIncomeLossAvailableToCommonStockholdersBasic',
                    'NetIncomeLossAvailableToCommonStockholdersDiluted',
                    'ProfitLoss'
                )
                THEN n.value
            END
        ) AS net_income,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                )
                THEN n.value
            END
        ) AS equity
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    JOIN company_seed sc USING (cik)
    WHERE n.tag IN (
        'NetIncomeLoss',
        'NetIncomeLossAvailableToCommonStockholdersBasic',
        'NetIncomeLossAvailableToCommonStockholdersDiluted',
        'ProfitLoss',
        'StockholdersEquity',
        'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY sc.display_name, sc.canonical_name, lf.cik, lf.fiscal_year
),
roe_values AS (
    SELECT
        company,
        canonical_name,
        fiscal_year,
        CASE
            WHEN net_income IS NULL OR equity IS NULL THEN NULL
            WHEN ABS(equity) < {min_equity} OR equity = 0 THEN NULL
            ELSE LEAST(
                {max_roe_pct},
                GREATEST(
                    -{max_roe_pct},
                    (net_income / NULLIF(equity, 0)) * 100
                )
            )
        END AS roe_pct
    FROM annual_values
),
filtered_years AS (
    SELECT *
    FROM roe_values
    WHERE fiscal_year BETWEEN {start_year} AND {end_year}
      AND roe_pct IS NOT NULL
),
streak_index AS (
    SELECT
        *,
        CASE WHEN roe_pct >= {roe_threshold} THEN 1 ELSE 0 END AS above_threshold,
        CASE
            WHEN roe_pct >= {roe_threshold} THEN fiscal_year - ROW_NUMBER() OVER (
                PARTITION BY canonical_name, CASE WHEN roe_pct >= {roe_threshold} THEN 1 ELSE 0 END
                ORDER BY fiscal_year
            )
            ELSE NULL
        END AS streak_group
    FROM filtered_years
),
consecutive_runs AS (
    SELECT
        canonical_name,
        COUNT(*) AS streak_length,
        MIN(fiscal_year) AS streak_start_year,
        MAX(fiscal_year) AS streak_end_year
    FROM streak_index
    WHERE above_threshold = 1
    GROUP BY canonical_name, streak_group
),
longest_streak AS (
    SELECT
        canonical_name,
        streak_length,
        streak_start_year,
        streak_end_year,
        ROW_NUMBER() OVER (
            PARTITION BY canonical_name
            ORDER BY streak_length DESC, streak_end_year DESC
        ) AS streak_rank
    FROM consecutive_runs
),
company_longest AS (
    SELECT
        canonical_name,
        streak_length AS max_consecutive_years,
        streak_start_year,
        streak_end_year
    FROM longest_streak
    WHERE streak_rank = 1
),
roe_summary AS (
    SELECT
        canonical_name,
        ANY_VALUE(company) AS company,
        COUNT(*) AS years_reported,
        COUNT(*) FILTER (WHERE above_threshold = 1) AS years_above_threshold,
        ROUND(AVG(roe_pct) FILTER (WHERE above_threshold = 1), 2) AS avg_roe_pct,
        ROUND(
            COALESCE(
                STDDEV_SAMP(roe_pct) FILTER (WHERE above_threshold = 1),
                0
            ),
            2
        ) AS roe_volatility_pct,
        ROUND(MIN(roe_pct) FILTER (WHERE above_threshold = 1), 2) AS min_streak_roe_pct,
        ROUND(MAX(roe_pct) FILTER (WHERE above_threshold = 1), 2) AS max_streak_roe_pct,
        MIN(fiscal_year) AS first_year,
        MAX(fiscal_year) AS last_year
    FROM streak_index
    GROUP BY canonical_name
),
latest_values AS (
    SELECT
        canonical_name,
        CAST(fiscal_year AS INTEGER) AS fiscal_year,
        roe_pct,
        ROW_NUMBER() OVER (
            PARTITION BY canonical_name
            ORDER BY fiscal_year DESC
        ) AS rn
    FROM filtered_years
),
latest_per_company AS (
    SELECT
        canonical_name,
        fiscal_year AS latest_year_reported,
        ROUND(roe_pct, 2) AS latest_year_roe_pct
    FROM latest_values
    WHERE rn = 1
),
finalized AS (
    SELECT
        rs.company AS name,
        rs.canonical_name,
        rs.years_reported,
        rs.years_above_threshold,
        COALESCE(cl.max_consecutive_years, 0) AS max_consecutive_years,
        cl.streak_start_year,
        cl.streak_end_year,
        rs.avg_roe_pct,
        rs.roe_volatility_pct,
        rs.min_streak_roe_pct,
        rs.max_streak_roe_pct,
        rs.first_year,
        rs.last_year,
        lp.latest_year_reported,
        lp.latest_year_roe_pct
    FROM roe_summary rs
    LEFT JOIN company_longest cl USING (canonical_name)
    LEFT JOIN latest_per_company lp USING (canonical_name)
)
SELECT
    name,
    max_consecutive_years AS consecutive_years,
    years_above_threshold,
    years_reported,
    streak_start_year,
    streak_end_year,
    first_year,
    last_year,
    avg_roe_pct,
    roe_volatility_pct,
    min_streak_roe_pct,
    max_streak_roe_pct,
    latest_year_reported,
    latest_year_roe_pct
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY canonical_name
            ORDER BY
                max_consecutive_years DESC,
                avg_roe_pct DESC,
                roe_volatility_pct ASC,
                name
        ) AS name_rank
    FROM finalized
    WHERE max_consecutive_years >= {min_consecutive_years}
      AND years_above_threshold >= {min_consecutive_years}
      AND years_reported >= {min_years_reported}
      AND avg_roe_pct IS NOT NULL
)
WHERE name_rank = 1
ORDER BY
    consecutive_years DESC,
    avg_roe_pct DESC,
    roe_volatility_pct ASC,
    name
LIMIT {limit};

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
                    'NetCashProvidedByUsedInOperatingActivities',
                    'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'
                ) THEN n.value
            END
        ) AS cfo,
        MAX(
            CASE
                WHEN n.tag IN (
                    'PaymentsToAcquirePropertyPlantAndEquipment',
                    'PurchaseOfPropertyPlantAndEquipment',
                    'PaymentsToAcquireProductiveAssets',
                    'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets'
                ) THEN n.value
            END
        ) AS capex,
        MAX(
            CASE
                WHEN n.tag IN (
                    'Revenues',
                    'RevenueFromContractWithCustomerExcludingAssessedTax',
                    'SalesRevenueNet'
                ) THEN n.value
            END
        ) AS revenue
        ,
        MAX(
            CASE
                WHEN n.tag IN (
                    'OperatingIncomeLoss',
                    'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
                ) THEN n.value
            END
        ) AS operating_income
    FROM latest_filings lf
    JOIN num n ON n.adsh = lf.adsh AND n.ddate = lf.period
    WHERE n.tag IN (
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PurchaseOfPropertyPlantAndEquipment',
        'PaymentsToAcquireProductiveAssets',
        'PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets',
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'OperatingIncomeLoss',
        'OperatingIncomeLossAfterIncomeFromEquityMethodInvestments'
    )
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
    GROUP BY lf.cik, lf.fiscal_year
),
fcf_series AS (
    SELECT
        sc.company,
        av.fiscal_year,
        av.revenue,
        av.cfo,
        av.capex,
        CASE
            WHEN av.revenue IS NULL OR av.revenue < {min_revenue} THEN NULL
            WHEN av.cfo IS NULL OR av.capex IS NULL THEN NULL
            ELSE av.cfo - ABS(av.capex)
        END AS free_cash_flow
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
),
margin_series AS (
    SELECT
        sc.company,
        av.fiscal_year,
        CASE
            WHEN av.revenue IS NULL OR av.revenue = 0 THEN NULL
            ELSE av.operating_income / av.revenue
        END AS operating_margin
    FROM annual_values av
    JOIN sector_companies sc USING (cik)
    WHERE av.revenue IS NOT NULL
),
aggregated AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        AVG(free_cash_flow) AS avg_fcf,
        STDDEV_SAMP(free_cash_flow) AS fcf_volatility
    FROM fcf_series
    WHERE free_cash_flow IS NOT NULL
    GROUP BY company
    HAVING year_count >= {min_years}
),
margin_aggregated AS (
    SELECT
        company,
        COUNT(*) AS year_count,
        AVG(operating_margin) AS avg_margin,
        STDDEV_SAMP(operating_margin) AS margin_volatility
    FROM margin_series
    WHERE operating_margin IS NOT NULL
    GROUP BY company
),
scored AS (
    SELECT
        company,
        year_count,
        avg_fcf,
        fcf_volatility,
        CASE
            WHEN avg_fcf = 0 THEN NULL
            ELSE fcf_volatility / NULLIF(avg_fcf, 0)
        END AS coefficient_of_variation
    FROM aggregated
),
joined AS (
    SELECT
        f.company,
        f.year_count,
        f.avg_fcf,
        f.fcf_volatility,
        f.coefficient_of_variation,
        m.avg_margin,
        m.margin_volatility,
        CASE
            WHEN m.avg_margin = 0 THEN NULL
            ELSE m.margin_volatility / NULLIF(m.avg_margin, 0)
        END AS margin_volatility_ratio
    FROM scored f
    LEFT JOIN margin_aggregated m USING (company)
)
SELECT
    company,
    year_count,
    ROUND(avg_fcf / 1000000000.0, 2) AS avg_fcf_billions,
    ROUND(fcf_volatility / 1000000000.0, 2) AS fcf_volatility_billions,
    ROUND(coefficient_of_variation, 3) AS fcf_volatility_ratio,
    ROUND(avg_margin * 100, 2) AS avg_operating_margin_pct,
    ROUND(COALESCE(margin_volatility, 0) * 100, 2) AS operating_margin_volatility_pp,
    ROUND(margin_volatility_ratio, 3) AS operating_margin_volatility_ratio
FROM joined
WHERE coefficient_of_variation IS NOT NULL
ORDER BY coefficient_of_variation ASC, operating_margin_volatility_ratio ASC, avg_fcf DESC
LIMIT {limit};


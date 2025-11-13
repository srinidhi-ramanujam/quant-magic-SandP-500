WITH annual_balances AS (
    SELECT
        s.cik,
        s.fy AS fiscal_year,
        MAX(
            CASE
                WHEN n.tag IN (
                    'StockholdersEquity',
                    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
                )
                THEN n.value
            END
        ) AS equity,
        MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) AS assets
    FROM sub s
    JOIN num n ON n.adsh = s.adsh AND n.ddate = s.period
    WHERE s.form IN ('10-K','10-K/A')
      AND s.fy BETWEEN {start_year} AND {end_year}
      AND COALESCE(TRIM(n.segments), '') = ''
      AND COALESCE(TRIM(n.coreg), '') = ''
      -- Optional company filter (list of CIKs)
      -- AND s.cik IN ({company_list})
    GROUP BY s.cik, s.fy
)
SELECT
    ab.cik,
    ab.fiscal_year,
    ab.equity,
    ab.assets,
    CASE WHEN ab.assets <> 0 THEN ab.equity / ab.assets ELSE NULL END AS equity_to_assets_ratio
FROM annual_balances ab
JOIN companies c ON c.cik = ab.cik
WHERE 1 = 1
  -- Optional sector filter
  -- AND c.gics_sector = '{sector_filter}'
  -- Optional geography filter
  -- AND c.countryinc = '{jurisdiction_filter}'
ORDER BY ab.cik, ab.fiscal_year;


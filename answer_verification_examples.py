#!/usr/bin/env python3
"""
Answer verification examples for medium-tier questions.
Demonstrates the verification approach for 3 sample questions.
"""

import sys
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from src.query_engine import QueryEngine


class AnswerVerifier:
    """Verifies expected answers against actual data."""
    
    def __init__(self):
        self.qe = QueryEngine()
    
    def verify_ma_004(self) -> Dict[str, Any]:
        """
        MA_004: What percentage of companies in each sector have a current ratio above 2.0?
        Expected: "No sectors meet the >50% criteria. Highest percentages: Information Technology (39.0%), Materials (34.8%), Real Estate (25.0%)"
        """
        print("\n" + "="*80)
        print("MA_004: Current Ratio Threshold Analysis")
        print("="*80)
        
        # Query to calculate current ratio by sector
        sql = """
        WITH latest_data AS (
            SELECT 
                c.name,
                c.gics_sector,
                MAX(CASE WHEN n.tag = 'AssetsCurrent' THEN n.value END) as current_assets,
                MAX(CASE WHEN n.tag = 'LiabilitiesCurrent' THEN n.value END) as current_liabilities,
                MAX(n.ddate) as latest_date
            FROM companies c
            JOIN num n ON c.cik = n.cik
            WHERE n.qtrs = 0  -- Annual data
              AND n.ddate >= '2023-01-01'
              AND n.tag IN ('AssetsCurrent', 'LiabilitiesCurrent')
              AND c.gics_sector IS NOT NULL
            GROUP BY c.name, c.gics_sector, n.adsh
            HAVING MAX(CASE WHEN n.tag = 'AssetsCurrent' THEN n.value END) IS NOT NULL
               AND MAX(CASE WHEN n.tag = 'LiabilitiesCurrent' THEN n.value END) IS NOT NULL
        ),
        ratios AS (
            SELECT 
                name,
                gics_sector,
                current_assets,
                current_liabilities,
                CASE 
                    WHEN current_liabilities > 0 THEN current_assets::FLOAT / current_liabilities 
                    ELSE NULL 
                END as current_ratio
            FROM latest_data
        ),
        sector_stats AS (
            SELECT 
                gics_sector,
                COUNT(*) as total_companies,
                SUM(CASE WHEN current_ratio > 2.0 THEN 1 ELSE 0 END) as above_threshold,
                ROUND(100.0 * SUM(CASE WHEN current_ratio > 2.0 THEN 1 ELSE 0 END) / COUNT(*), 1) as percentage
            FROM ratios
            WHERE current_ratio IS NOT NULL
            GROUP BY gics_sector
        )
        SELECT *
        FROM sector_stats
        ORDER BY percentage DESC
        """
        
        try:
            result = self.qe.execute(sql)
            print("\nActual Results:")
            print(result.to_string())
            
            # Check expected answer
            top_3 = result.head(3)
            meets_50_pct = result[result['percentage'] >= 50.0]
            
            # Build top 3 string
            top_3_str = ', '.join([
                "{} ({:.1f}%)".format(row['gics_sector'], row['percentage']) 
                for _, row in top_3.iterrows()
            ])
            
            verification = {
                "question_id": "MA_004",
                "expected": "No sectors meet >50% criteria. Top 3: IT (39.0%), Materials (34.8%), Real Estate (25.0%)",
                "actual_top_3": top_3.to_dict('records'),
                "sectors_above_50_pct": len(meets_50_pct),
                "passes": len(meets_50_pct) == 0,  # Should be 0 sectors above 50%
                "notes": f"Top 3 sectors: {top_3_str}"
            }
            
            return verification
            
        except Exception as e:
            return {
                "question_id": "MA_004",
                "error": str(e),
                "passes": False,
                "notes": "Query failed - needs refinement"
            }
    
    def verify_ma_030(self) -> Dict[str, Any]:
        """
        MA_030: Compare cash conversion cycle efficiency between Retail and Technology sectors.
        Expected: "Retail sector demonstrates superior working capital management with median CCC of -18.5 days vs Technology's 8.2 days"
        """
        print("\n" + "="*80)
        print("MA_030: Cash Conversion Cycle Comparison")
        print("="*80)
        
        # For CCC, we need: Days Sales Outstanding + Days Inventory Outstanding - Days Payable Outstanding
        # DSO = (Accounts Receivable / Revenue) * 365
        # DIO = (Inventory / Cost of Revenue) * 365
        # DPO = (Accounts Payable / Cost of Revenue) * 365
        
        sql = """
        WITH latest_data AS (
            SELECT 
                c.name,
                c.gics_sector,
                MAX(CASE WHEN n.tag = 'AccountsReceivableNetCurrent' THEN n.value END) as ar,
                MAX(CASE WHEN n.tag = 'InventoryNet' THEN n.value END) as inventory,
                MAX(CASE WHEN n.tag = 'AccountsPayableCurrent' THEN n.value END) as ap,
                MAX(CASE WHEN n.tag = 'Revenues' THEN n.value END) as revenue,
                MAX(CASE WHEN n.tag = 'CostOfRevenue' THEN n.value END) as cost_of_revenue
            FROM companies c
            JOIN num n ON c.cik = n.cik
            WHERE n.qtrs = 0  -- Annual data
              AND n.ddate >= '2023-01-01'
              AND n.tag IN ('AccountsReceivableNetCurrent', 'InventoryNet', 'AccountsPayableCurrent', 'Revenues', 'CostOfRevenue')
              AND c.gics_sector IN ('Consumer Discretionary', 'Information Technology')
            GROUP BY c.name, c.gics_sector, n.adsh
        ),
        calculated_ccc AS (
            SELECT 
                gics_sector,
                name,
                CASE WHEN revenue > 0 THEN (ar::FLOAT / revenue) * 365 ELSE 0 END as dso,
                CASE WHEN cost_of_revenue > 0 THEN (COALESCE(inventory, 0)::FLOAT / cost_of_revenue) * 365 ELSE 0 END as dio,
                CASE WHEN cost_of_revenue > 0 THEN (COALESCE(ap, 0)::FLOAT / cost_of_revenue) * 365 ELSE 0 END as dpo,
                (CASE WHEN revenue > 0 THEN (ar::FLOAT / revenue) * 365 ELSE 0 END +
                 CASE WHEN cost_of_revenue > 0 THEN (COALESCE(inventory, 0)::FLOAT / cost_of_revenue) * 365 ELSE 0 END -
                 CASE WHEN cost_of_revenue > 0 THEN (COALESCE(ap, 0)::FLOAT / cost_of_revenue) * 365 ELSE 0 END) as ccc
            FROM latest_data
            WHERE revenue > 0
        )
        SELECT 
            gics_sector,
            ROUND(MEDIAN(ccc), 1) as median_ccc,
            ROUND(AVG(ccc), 1) as avg_ccc,
            COUNT(*) as company_count
        FROM calculated_ccc
        GROUP BY gics_sector
        ORDER BY median_ccc
        """
        
        try:
            result = self.qe.execute(sql)
            print("\nActual Results:")
            print(result.to_string())
            
            verification = {
                "question_id": "MA_030",
                "expected": "Retail: -18.5 days, Technology: 8.2 days (26.8-day difference)",
                "actual": result.to_dict('records'),
                "passes": "NEEDS_REVIEW",
                "notes": "Compare actual median CCC values with expected"
            }
            
            return verification
            
        except Exception as e:
            return {
                "question_id": "MA_030",
                "error": str(e),
                "passes": False,
                "notes": "Query failed - XBRL tags may need adjustment"
            }
    
    def verify_ma_019(self) -> Dict[str, Any]:
        """
        MA_019: Analyze earnings quality by comparing operating cash flow to net income ratios across sectors.
        Expected: "Utilities/Energy shows highest earnings quality with 1.889 median OCF/NI ratio"
        """
        print("\n" + "="*80)
        print("MA_019: Earnings Quality Analysis (OCF/NI Ratio)")
        print("="*80)
        
        sql = """
        WITH latest_data AS (
            SELECT 
                c.name,
                c.gics_sector,
                MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) as ocf,
                MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) as net_income
            FROM companies c
            JOIN num n ON c.cik = n.cik
            WHERE n.qtrs = 0  -- Annual data
              AND n.ddate >= '2023-01-01'
              AND n.tag IN ('NetCashProvidedByUsedInOperatingActivities', 'NetIncomeLoss')
              AND c.gics_sector IS NOT NULL
            GROUP BY c.name, c.gics_sector, n.adsh
            HAVING MAX(CASE WHEN n.tag = 'NetCashProvidedByUsedInOperatingActivities' THEN n.value END) IS NOT NULL
               AND MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) IS NOT NULL
        ),
        ratios AS (
            SELECT 
                gics_sector,
                name,
                ocf,
                net_income,
                CASE 
                    WHEN net_income > 0 THEN ocf::FLOAT / net_income
                    ELSE NULL
                END as ocf_ni_ratio
            FROM latest_data
        )
        SELECT 
            gics_sector,
            ROUND(MEDIAN(ocf_ni_ratio), 3) as median_ocf_ni,
            ROUND(AVG(ocf_ni_ratio), 3) as avg_ocf_ni,
            COUNT(*) as company_count
        FROM ratios
        WHERE ocf_ni_ratio IS NOT NULL
          AND ocf_ni_ratio > 0  -- Exclude negative ratios
          AND ocf_ni_ratio < 10  -- Exclude extreme outliers
        GROUP BY gics_sector
        ORDER BY median_ocf_ni DESC
        """
        
        try:
            result = self.qe.execute(sql)
            print("\nActual Results:")
            print(result.to_string())
            
            top_sector = result.iloc[0] if len(result) > 0 else None
            
            verification = {
                "question_id": "MA_019",
                "expected": "Utilities/Energy: 1.889 median OCF/NI ratio",
                "actual_top": f"{top_sector['gics_sector']}: {top_sector['median_ocf_ni']}" if top_sector else "No data",
                "all_results": result.to_dict('records'),
                "passes": "NEEDS_REVIEW",
                "notes": "Check if top sector matches expected and ratio is within tolerance"
            }
            
            return verification
            
        except Exception as e:
            return {
                "question_id": "MA_019",
                "error": str(e),
                "passes": False,
                "notes": "Query failed - XBRL tags may need adjustment"
            }
    
    def run_all_verifications(self):
        """Run all verification examples."""
        print("\n" + "="*80)
        print("ANSWER VERIFICATION - EXAMPLE DEMONSTRATIONS")
        print("="*80)
        print("\nVerifying 3 sample questions to demonstrate the approach:")
        print("1. MA_004 - Current ratio threshold analysis")
        print("2. MA_030 - Cash conversion cycle comparison")
        print("3. MA_019 - Earnings quality analysis")
        print("="*80)
        
        results = []
        
        # Verify MA_004
        results.append(self.verify_ma_004())
        
        # Verify MA_030
        results.append(self.verify_ma_030())
        
        # Verify MA_019
        results.append(self.verify_ma_019())
        
        # Summary
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        for r in results:
            status = "✅ PASS" if r.get('passes') == True else ("❌ FAIL" if r.get('passes') == False else "⚠️  NEEDS_REVIEW")
            print(f"{status} - {r['question_id']}: {r.get('notes', 'See details above')}")
        
        print("\n" + "="*80)
        print("Next Steps:")
        print("1. Review the SQL queries above for accuracy")
        print("2. Refine XBRL tag mappings as needed")
        print("3. Apply this approach to all 27 passing questions")
        print("4. Document any answer corrections needed")
        print("="*80)
    
    def close(self):
        """Clean up resources."""
        self.qe.close()


def main():
    """Main entry point."""
    verifier = AnswerVerifier()
    try:
        verifier.run_all_verifications()
    finally:
        verifier.close()


if __name__ == "__main__":
    main()


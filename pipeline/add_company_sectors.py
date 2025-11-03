"""
Add GICS sector information to companies.

This script reads the comprehensive S&P 500 company list and creates
a companies_with_sectors.parquet file that includes sector classifications.

Usage:
    python -m pipeline.add_company_sectors
"""

import logging
from pathlib import Path
import pandas as pd


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_sectors():
    """Add sector information to company data."""
    project_root = Path(__file__).parent.parent
    
    # Input files
    companies_csv = project_root / "data" / "raw" / "comprehensive_companies.csv"
    sub_parquet = project_root / "data" / "parquet" / "sub.parquet"
    
    # Output file
    output_file = project_root / "data" / "parquet" / "companies_with_sectors.parquet"
    
    logger.info("Adding GICS sector information...")
    
    # Read company list with sectors
    if not companies_csv.exists():
        logger.error(f"Company list not found: {companies_csv}")
        logger.info("Creating basic companies file from submissions...")
        
        # Fallback: Create companies from submission data
        df_sub = pd.read_parquet(sub_parquet)
        df_companies = df_sub[['cik', 'name', 'countryinc']].drop_duplicates('cik')
        df_companies['gics_sector'] = 'Other'  # Default sector
        
    else:
        logger.info(f"Reading: {companies_csv}")
        df_sectors = pd.read_csv(companies_csv)
        
        # Read submission data for all companies
        logger.info(f"Reading: {sub_parquet}")
        df_sub = pd.read_parquet(sub_parquet)
        
        # Get unique companies from submissions
        df_companies = df_sub[['cik', 'name', 'countryinc']].drop_duplicates('cik')
        
        # Merge with sector information
        logger.info("Merging sector data...")
        df_companies = df_companies.merge(
            df_sectors[['cik', 'gics_sector']], 
            on='cik', 
            how='left'
        )
        
        # Fill missing sectors
        df_companies['gics_sector'] = df_companies['gics_sector'].fillna('Other')
    
    # Save to parquet
    logger.info(f"Writing: {output_file}")
    df_companies.to_parquet(output_file, index=False)
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("Summary:")
    logger.info(f"  Total companies: {len(df_companies):,}")
    logger.info(f"  Sectors: {df_companies['gics_sector'].nunique()}")
    logger.info("\nCompanies by sector:")
    for sector, count in df_companies['gics_sector'].value_counts().items():
        logger.info(f"  {sector}: {count}")
    
    logger.info("="*70)
    logger.info(f"✅ companies_with_sectors.parquet created!\n")


if __name__ == "__main__":
    add_sectors()


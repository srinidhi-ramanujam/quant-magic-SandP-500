"""
Process new quarterly SEC EDGAR data.

This script handles adding new quarterly data to the existing dataset.

Usage:
    # Download new quarter from SEC EDGAR (example for 2025Q3)
    wget https://www.sec.gov/files/dera/data/financial-statement-data-sets/2025q3.zip
    
    # Extract to data/raw/quarterly/2025q3/
    unzip 2025q3.zip -d data/raw/quarterly/2025q3/
    
    # Run this script to merge with existing data
    python -m pipeline.update_quarterly_data --quarter 2025q3
"""

import argparse
import logging
from pathlib import Path
from typing import List
import pandas as pd


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuarterlyDataUpdater:
    """Update dataset with new quarterly data."""
    
    def __init__(self, project_root: Path = None):
        """Initialize updater."""
        self.project_root = project_root or Path(__file__).parent.parent
        self.raw_dir = self.project_root / "data" / "raw"
        self.quarterly_dir = self.raw_dir / "quarterly"
        self.parquet_dir = self.project_root / "data" / "parquet"
    
    def process_quarter(self, quarter: str):
        """
        Process a new quarter of data.
        
        Args:
            quarter: Quarter identifier (e.g., '2025q3')
        """
        quarter_path = self.quarterly_dir / quarter
        
        if not quarter_path.exists():
            logger.error(f"Quarter directory not found: {quarter_path}")
            logger.info("Expected structure:")
            logger.info(f"  {quarter_path}/")
            logger.info(f"    ├── num.txt")
            logger.info(f"    ├── sub.txt")
            logger.info(f"    ├── tag.txt")
            logger.info(f"    └── pre.txt")
            return
        
        logger.info(f"Processing quarter: {quarter}")
        logger.info(f"  Source: {quarter_path}")
        
        # Process each table
        tables = ['num', 'sub', 'tag', 'pre']
        
        for table in tables:
            self._merge_table(quarter_path, table)
        
        logger.info(f"✅ Quarter {quarter} merged successfully!")
    
    def _merge_table(self, quarter_path: Path, table: str):
        """Merge new data into existing table."""
        # Paths
        new_data_file = quarter_path / f"{table}.txt"
        existing_parquet = self.parquet_dir / f"{table}.parquet"
        backup_file = self.parquet_dir / f"{table}.parquet.backup"
        
        if not new_data_file.exists():
            logger.warning(f"  Skipping {table} - file not found")
            return
        
        logger.info(f"  Processing {table}...")
        
        # Backup existing data
        if existing_parquet.exists():
            logger.info(f"    Creating backup...")
            import shutil
            shutil.copy2(existing_parquet, backup_file)
        
        # Read new data
        logger.info(f"    Reading new data from {new_data_file.name}...")
        df_new = pd.read_csv(new_data_file, sep='\t', low_memory=False)
        logger.info(f"      New rows: {len(df_new):,}")
        
        # Read existing data
        if existing_parquet.exists():
            logger.info(f"    Reading existing data...")
            df_existing = pd.read_parquet(existing_parquet)
            logger.info(f"      Existing rows: {len(df_existing):,}")
            
            # Merge (remove duplicates based on key columns)
            logger.info(f"    Merging data...")
            if table == 'num':
                # num: unique by (adsh, tag, version, ddate, qtrs)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(
                    subset=['adsh', 'tag', 'version', 'ddate', 'qtrs'],
                    keep='last'  # Keep most recent
                )
            elif table == 'sub':
                # sub: unique by adsh
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['adsh'], keep='last')
            elif table == 'tag':
                # tag: unique by (tag, version)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['tag', 'version'], keep='last')
            elif table == 'pre':
                # pre: unique by (adsh, report, line)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['adsh', 'report', 'line'], keep='last')
            else:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            
            logger.info(f"      Combined rows: {len(df_combined):,}")
        else:
            df_combined = df_new
            logger.info(f"      No existing data - using new data only")
        
        # Write updated parquet
        logger.info(f"    Writing updated parquet...")
        df_combined.to_parquet(existing_parquet, compression='snappy', index=False)
        
        logger.info(f"    ✅ {table} updated")
    
    def list_quarters(self):
        """List available quarters to process."""
        if not self.quarterly_dir.exists():
            logger.info(f"No quarterly directory found: {self.quarterly_dir}")
            return []
        
        quarters = [d.name for d in self.quarterly_dir.iterdir() if d.is_dir()]
        return sorted(quarters)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Update dataset with new quarterly data')
    parser.add_argument('--quarter', help='Quarter to process (e.g., 2025q3)')
    parser.add_argument('--list', action='store_true', help='List available quarters')
    
    args = parser.parse_args()
    
    updater = QuarterlyDataUpdater()
    
    if args.list:
        quarters = updater.list_quarters()
        if quarters:
            logger.info("Available quarters:")
            for q in quarters:
                logger.info(f"  - {q}")
        else:
            logger.info("No quarters found in data/raw/quarterly/")
    elif args.quarter:
        updater.process_quarter(args.quarter)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


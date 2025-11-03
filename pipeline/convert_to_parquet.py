"""
Convert SEC EDGAR TSV files to Parquet format.

This script converts the raw TSV files from SEC EDGAR into optimized Parquet files
for fast analytics with DuckDB.

Usage:
    python -m pipeline.convert_to_parquet
    
Input:  data/raw/*.txt (TSV files)
Output: data/parquet/*.parquet (optimized Parquet files)
"""

import logging
from pathlib import Path
from typing import Dict
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Data type specifications for each table (optimized for memory)
DTYPE_SPECS = {
    'num': {
        'adsh': 'string',
        'tag': 'string', 
        'version': 'string',
        'ddate': 'string',
        'qtrs': 'int8',
        'uom': 'category',
        'value': 'float64',
        'footnote': 'string',
        'segments': 'string',
        'coreg': 'string'
    },
    'sub': {
        'adsh': 'string',
        'cik': 'string',
        'name': 'string',
        'sic': 'float64',
        'countryba': 'category',
        'stprba': 'category',
        'cityba': 'string',
        'zipba': 'string',
        'bas1': 'string',
        'bas2': 'string',
        'baph': 'string',
        'countryma': 'category',
        'stprma': 'category',
        'cityma': 'string',
        'zipma': 'string',
        'mas1': 'string',
        'mas2': 'string',
        'countryinc': 'category',
        'stprinc': 'category',
        'ein': 'string',
        'former': 'string',
        'changed': 'float64',
        'afs': 'category',
        'wksi': 'int8',
        'fye': 'float64',
        'form': 'category',
        'period': 'string',
        'fy': 'float64',
        'fp': 'category',
        'filed': 'string',
        'accepted': 'string',
        'prevrpt': 'int8',
        'detail': 'int8',
        'instance': 'string',
        'nciks': 'int8',
        'aciks': 'string'
    },
    'tag': {
        'tag': 'string',
        'version': 'category',
        'custom': 'int8',
        'abstract': 'int8',
        'datatype': 'category',
        'iord': 'category',
        'crdr': 'category',
        'tlabel': 'string',
        'doc': 'string'
    },
    'pre': {
        'adsh': 'string',
        'report': 'int8',
        'line': 'int16',
        'stmt': 'string',
        'inpth': 'int8',
        'rfile': 'string',
        'tag': 'string',
        'version': 'string',
        'plabel': 'string'
    }
}


class ParquetConverter:
    """Convert TSV files to Parquet format."""
    
    def __init__(self, raw_dir: Path = None, output_dir: Path = None):
        """
        Initialize converter.
        
        Args:
            raw_dir: Directory containing raw TSV files (default: data/raw/)
            output_dir: Directory for output Parquet files (default: data/parquet/)
        """
        self.project_root = Path(__file__).parent.parent
        self.raw_dir = raw_dir or self.project_root / "data" / "raw"
        self.output_dir = output_dir or self.project_root / "data" / "parquet"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Raw data directory: {self.raw_dir}")
        logger.info(f"Output directory: {self.output_dir}")
    
    def convert_file(self, table_name: str, chunk_size: int = 100000):
        """
        Convert a TSV file to Parquet format.
        
        Args:
            table_name: Name of table (num, sub, tag, pre)
            chunk_size: Number of rows per chunk for large files
        """
        input_file = self.raw_dir / f"{table_name}.txt"
        output_file = self.output_dir / f"{table_name}.parquet"
        
        if not input_file.exists():
            logger.warning(f"Input file not found: {input_file}")
            return
        
        logger.info(f"Converting {table_name}...")
        logger.info(f"  Input: {input_file}")
        logger.info(f"  Output: {output_file}")
        
        try:
            # Get dtype spec for this table
            dtype_spec = DTYPE_SPECS.get(table_name, {})
            
            # Read TSV in chunks (for large files)
            chunks = []
            total_rows = 0
            
            for chunk in pd.read_csv(
                input_file,
                sep='\t',
                dtype=dtype_spec,
                chunksize=chunk_size,
                low_memory=False,
                on_bad_lines='warn'
            ):
                chunks.append(chunk)
                total_rows += len(chunk)
                logger.info(f"  Processed {total_rows:,} rows...")
            
            # Combine all chunks
            logger.info("  Combining chunks...")
            df = pd.concat(chunks, ignore_index=True)
            
            logger.info(f"  Total rows: {len(df):,}")
            logger.info(f"  Columns: {len(df.columns)}")
            logger.info(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
            
            # Write to Parquet with compression
            logger.info("  Writing Parquet file...")
            df.to_parquet(
                output_file,
                compression='snappy',  # Fast compression
                index=False,
                engine='pyarrow'
            )
            
            # Show output file size
            output_size = output_file.stat().st_size / 1024**2
            logger.info(f"  Output size: {output_size:.1f} MB")
            logger.info(f"✅ {table_name} conversion complete\n")
            
        except Exception as e:
            logger.error(f"❌ Error converting {table_name}: {e}")
            raise
    
    def convert_all(self):
        """Convert all TSV files to Parquet."""
        tables = ['num', 'sub', 'tag', 'pre']
        
        logger.info("="*70)
        logger.info("SEC EDGAR TSV to Parquet Conversion")
        logger.info("="*70 + "\n")
        
        for table in tables:
            self.convert_file(table)
        
        logger.info("="*70)
        logger.info("Conversion Complete!")
        logger.info("="*70)
        logger.info(f"\nParquet files created in: {self.output_dir}")


def main():
    """Main function."""
    converter = ParquetConverter()
    converter.convert_all()


if __name__ == "__main__":
    main()


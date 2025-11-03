"""
Query Engine - DuckDB wrapper for financial data queries.

This is the data layer - keep it simple and focused.
"""

import logging
from typing import Optional, List, Dict, Any

import duckdb
import pandas as pd

from src.config import get_config, get_parquet_path


logger = logging.getLogger(__name__)


class QueryEngine:
    """
    Simple DuckDB query engine for parquet files.

    Responsibilities:
    - Connect to DuckDB
    - Register parquet files as tables
    - Execute SQL queries
    - Return pandas DataFrames

    NOT responsible for:
    - SQL generation (that's sql_generator.py)
    - Response formatting (that's response_formatter.py)
    - Entity extraction (that's entity_extractor.py)
    """

    def __init__(self):
        """Initialize DuckDB connection and register tables."""
        self.config = get_config()
        self.conn = None
        self._connect()
        self._register_tables()

    def _connect(self):
        """Create DuckDB connection with optimized settings."""
        try:
            self.conn = duckdb.connect(":memory:")

            # Configure for optimal performance
            self.conn.execute(f"SET memory_limit='{self.config.duckdb_memory_limit}'")
            self.conn.execute(f"SET threads={self.config.duckdb_threads}")
            self.conn.execute("SET enable_progress_bar=false")

            logger.info("DuckDB connection established")

        except Exception as e:
            logger.error(f"Failed to connect to DuckDB: {e}")
            raise

    def _register_tables(self):
        """Register parquet files as DuckDB tables."""
        # Core tables
        tables = {
            "num": "num.parquet",  # Financial metrics
            "sub": "sub.parquet",  # Submissions
            "tag": "tag.parquet",  # XBRL tags
            "companies": "companies_with_sectors.parquet",  # Company info
        }

        for table_name, filename in tables.items():
            parquet_path = get_parquet_path(filename)

            if parquet_path.exists():
                try:
                    self.conn.execute(
                        f"""
                        CREATE OR REPLACE VIEW {table_name} AS 
                        SELECT * FROM read_parquet('{parquet_path}')
                    """
                    )
                    logger.info(f"Registered table: {table_name}")
                except Exception as e:
                    logger.warning(f"Failed to register {table_name}: {e}")
            else:
                logger.warning(f"Parquet file not found: {parquet_path}")

    def execute(self, sql: str) -> pd.DataFrame:
        """
        Execute SQL query and return results as pandas DataFrame.

        Args:
            sql: SQL query string

        Returns:
            pandas DataFrame with query results

        Raises:
            Exception: If query fails
        """
        try:
            logger.debug(f"Executing SQL: {sql[:100]}...")
            result = self.conn.execute(sql).fetchdf()
            logger.info(f"Query returned {len(result)} rows")
            return result

        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.error(f"SQL: {sql}")
            raise

    def count_companies(self) -> int:
        """Get total number of companies (for testing)."""
        result = self.execute("SELECT COUNT(DISTINCT cik) as cnt FROM companies")
        return int(result.iloc[0]["cnt"])

    def list_sectors(self) -> List[str]:
        """Get list of all sectors (for testing)."""
        result = self.execute(
            """
            SELECT DISTINCT gics_sector 
            FROM companies 
            WHERE gics_sector IS NOT NULL
            ORDER BY gics_sector
        """
        )
        return result["gics_sector"].tolist()

    def get_company_info(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Get company information by name.

        Args:
            company_name: Company name (partial match supported)

        Returns:
            Dict with company info or None if not found
        """
        sql = f"""
        SELECT cik, name, gics_sector, countryinc
        FROM companies
        WHERE UPPER(name) LIKE UPPER('%{company_name}%')
        LIMIT 1
        """

        result = self.execute(sql)

        if result.empty:
            return None

        return result.iloc[0].to_dict()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("DuckDB connection closed")


# Convenience function for quick queries
def quick_query(sql: str) -> pd.DataFrame:
    """Execute a quick SQL query without managing connection."""
    qe = QueryEngine()
    try:
        return qe.execute(sql)
    finally:
        qe.close()

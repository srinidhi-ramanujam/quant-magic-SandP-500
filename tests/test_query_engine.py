"""
Tests for the query engine.

These tests verify the data layer works correctly.
"""

import pytest
from src.query_engine import QueryEngine


def test_query_engine_initialization():
    """Test that query engine initializes successfully."""
    qe = QueryEngine()
    assert qe.conn is not None
    qe.close()


def test_count_companies():
    """Test counting total companies."""
    qe = QueryEngine()
    count = qe.count_companies()

    # We know we have 764 companies
    assert count > 500, f"Expected >500 companies, got {count}"
    assert count < 1000, f"Expected <1000 companies, got {count}"

    qe.close()


def test_list_sectors():
    """Test listing all sectors."""
    qe = QueryEngine()
    sectors = qe.list_sectors()

    # Should have multiple sectors
    assert len(sectors) > 5, f"Expected >5 sectors, got {len(sectors)}"

    # Should include major sectors
    sector_names = [s.lower() for s in sectors if s]
    assert any("technology" in s for s in sector_names)
    assert any("health" in s for s in sector_names)

    qe.close()


def test_get_company_info():
    """Test getting company information."""
    qe = QueryEngine()

    # Test finding Apple
    apple = qe.get_company_info("Apple")
    assert apple is not None
    assert "cik" in apple
    assert "name" in apple
    assert "APPLE" in apple["name"].upper()

    # Test finding Microsoft
    msft = qe.get_company_info("Microsoft")
    assert msft is not None
    assert "MICROSOFT" in msft["name"].upper()

    qe.close()


def test_simple_query():
    """Test executing a simple SQL query."""
    qe = QueryEngine()

    sql = """
    SELECT COUNT(*) as cnt 
    FROM companies 
    WHERE gics_sector = 'Information Technology'
    """

    result = qe.execute(sql)

    assert len(result) == 1
    assert result.iloc[0]["cnt"] > 0

    qe.close()


def test_company_sector_join():
    """Test joining companies with financial data."""
    qe = QueryEngine()

    sql = """
    SELECT c.name, c.gics_sector, COUNT(DISTINCT s.adsh) as filing_count
    FROM companies c
    LEFT JOIN sub s ON c.cik = s.cik
    WHERE c.name LIKE '%APPLE%'
    GROUP BY c.name, c.gics_sector
    """

    result = qe.execute(sql)

    assert len(result) > 0
    assert result.iloc[0]["filing_count"] > 0

    qe.close()


def test_pre_table_registered():
    """Ensure the presentation linkbase view is available."""
    qe = QueryEngine()
    result = qe.execute("SELECT COUNT(*) AS cnt FROM pre")
    assert len(result) == 1
    assert result.iloc[0]["cnt"] >= 0
    qe.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

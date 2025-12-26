"""Tests for SEC filing processor."""

import json
import pytest
from datetime import date
from pathlib import Path

from sources.sec_edgar.processor import FilingProcessor

from .conftest import (
    MockFiling,
    MockFilingItem,
    MockXBRL,
    MockStatements,
    MockStatement,
    create_apple_filing,
)


class TestFilingProcessor:
    """Tests for FilingProcessor class."""

    def test_process_creates_directories(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that processing creates the expected directory structure."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True

        # Check directories exist
        filing_dir = temp_dir / "AAPL" / mock_filing.accession_number
        assert filing_dir.exists()
        assert (filing_dir / "items").exists()
        assert (filing_dir / "statements").exists()

    def test_process_saves_filing_metadata(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that filing metadata JSON is saved correctly."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True
        filing_json = temp_dir / "AAPL" / mock_filing.accession_number / "filing.json"
        assert filing_json.exists()

        # Verify JSON content
        with open(filing_json) as f:
            data = json.load(f)
        assert data["accession_number"] == "0000320193-24-000123"
        assert data["form"] == "10-K"
        assert data["cik"] == 320193
        assert data["company"] == "Apple Inc."

    def test_process_extracts_items(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that filing items are extracted correctly."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True

        items_dir = temp_dir / "AAPL" / mock_filing.accession_number / "items"
        item_1 = items_dir / "item_1.txt"
        item_7 = items_dir / "item_7.txt"

        assert item_1.exists()
        assert item_7.exists()
        assert item_1.read_text() == "Business description content..."
        assert item_7.read_text() == "Management discussion and analysis..."

    def test_process_extracts_statements(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that XBRL statements are extracted correctly."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True

        statements_dir = temp_dir / "AAPL" / mock_filing.accession_number / "statements"
        balance_sheet = statements_dir / "BalanceSheet.md"
        income_stmt = statements_dir / "IncomeStatement.md"

        assert balance_sheet.exists()
        assert income_stmt.exists()
        assert "Cash" in balance_sheet.read_text()
        assert "Revenue" in income_stmt.read_text()

    def test_process_saves_html_and_text(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that HTML and text content are saved."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True

        filing_dir = temp_dir / "AAPL" / mock_filing.accession_number
        html_files = list(filing_dir.glob("*.html"))
        txt_files = list(filing_dir.glob("*.txt"))

        assert len(html_files) == 1
        assert len(txt_files) == 1
        assert "Filing content" in html_files[0].read_text()
        assert "Plain text" in txt_files[0].read_text()

    def test_process_handles_amended_form(self, processor: FilingProcessor, temp_dir: Path):
        """Test that amended forms (e.g., 10-K/A) are handled correctly."""
        filing = create_apple_filing(
            accession_number="0000320193-24-000124",
            form="10-K/A",
            filing_date=date(2024, 11, 15),
            with_html=True,
            with_text=True,
        )
        result = processor.process(filing, "AAPL")

        assert result.success is True

        # Check that the filename uses underscore instead of slash
        filing_dir = temp_dir / "AAPL" / filing.accession_number
        html_files = list(filing_dir.glob("*.html"))
        assert len(html_files) == 1
        assert "10-K_A" in html_files[0].name

    def test_process_replaces_existing_directory(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that processing replaces existing directory atomically."""
        # First process
        result1 = processor.process(mock_filing, "AAPL")
        assert result1.success is True

        # Add a marker file to the existing directory
        filing_dir = temp_dir / "AAPL" / mock_filing.accession_number
        marker_file = filing_dir / "marker.txt"
        marker_file.write_text("original")

        # Second process should replace the directory
        result2 = processor.process(mock_filing, "AAPL")
        assert result2.success is True

        # Marker file should be gone (directory was replaced)
        assert not marker_file.exists()

    def test_process_handles_no_items(self, processor: FilingProcessor):
        """Test processing a filing with no items."""
        filing = create_apple_filing(accession_number="0000320193-24-000125")
        result = processor.process(filing, "AAPL")

        assert result.success is True

    def test_process_handles_no_xbrl(self, processor: FilingProcessor):
        """Test processing a filing with no XBRL data."""
        filing = create_apple_filing(accession_number="0000320193-24-000126")
        result = processor.process(filing, "AAPL")

        assert result.success is True


class TestFilingProcessorEdgeCases:
    """Edge case tests for FilingProcessor."""

    def test_process_with_empty_item_content(self, processor: FilingProcessor, temp_dir: Path):
        """Test handling of items with empty content."""
        filing = MockFiling(
            accession_number="0000320193-24-000127",
            form="10-K",
            filing_date=date(2024, 11, 1),
            cik=320193,
            company="Apple Inc.",
            _obj=MockFilingItem(
                items=["item_1", "item_2"],
                content={
                    "item_1": "Has content",
                    "item_2": "",  # Empty content
                },
            ),
        )
        result = processor.process(filing, "AAPL")

        assert result.success is True
        # item_1 should be saved, item_2 should be skipped
        items_dir = temp_dir / "AAPL" / filing.accession_number / "items"
        assert (items_dir / "item_1.txt").exists()
        assert not (items_dir / "item_2.txt").exists()

    def test_process_with_missing_item(self, processor: FilingProcessor, temp_dir: Path):
        """Test handling of items that return None."""
        filing = MockFiling(
            accession_number="0000320193-24-000128",
            form="10-K",
            filing_date=date(2024, 11, 1),
            cik=320193,
            company="Apple Inc.",
            _obj=MockFilingItem(
                items=["item_1", "item_missing"],
                content={
                    "item_1": "Has content",
                    # item_missing not in content dict, will return None
                },
            ),
        )
        result = processor.process(filing, "AAPL")

        assert result.success is True
        items_dir = temp_dir / "AAPL" / filing.accession_number / "items"
        assert (items_dir / "item_1.txt").exists()
        assert not (items_dir / "item_missing.txt").exists()

    def test_process_with_statement_by_index(self, processor: FilingProcessor, temp_dir: Path):
        """Test processing statements that only have index (no definition/role)."""
        filing = MockFiling(
            accession_number="0000320193-24-000129",
            form="10-K",
            filing_date=date(2024, 11, 1),
            cik=320193,
            company="Apple Inc.",
            _xbrl=MockXBRL(
                statements=MockStatements(
                    statements=[
                        {},  # No definition or role
                    ],
                    _statement_content={
                        "Statement0": MockStatement("| Data | Value |\n|---|---|\n| X | 1 |"),
                    },
                )
            ),
        )
        result = processor.process(filing, "AAPL")

        assert result.success is True
        statements_dir = temp_dir / "AAPL" / filing.accession_number / "statements"
        assert (statements_dir / "Statement0.md").exists()

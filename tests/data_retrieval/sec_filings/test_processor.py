"""Tests for SEC filing processor."""

import json
import pytest
from datetime import date
from pathlib import Path

from data_retrieval.sec_filings.processor import FilingProcessor

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
        assert result.output is not None

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
        assert result.items_processed == 2

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
        assert result.statements_processed == 2

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
        assert result.output is not None
        assert result.output.html_path is not None
        assert result.output.text_path is not None

        assert result.output.html_path.exists()
        assert result.output.text_path.exists()
        assert "Filing content" in result.output.html_path.read_text()
        assert "Plain text" in result.output.text_path.read_text()

    def test_process_handles_amended_form(self, processor: FilingProcessor):
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
        assert result.output is not None

        # Check that the filename uses underscore instead of slash
        assert result.output.html_path is not None
        assert "10-K_A" in result.output.html_path.name

    def test_process_skips_existing_files(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that existing files are not overwritten by default."""
        # First process
        result1 = processor.process(mock_filing, "AAPL")
        assert result1.success is True

        # Modify a file
        items_dir = temp_dir / "AAPL" / mock_filing.accession_number / "items"
        item_1 = items_dir / "item_1.txt"
        item_1.write_text("Modified content")

        # Second process (should skip)
        result2 = processor.process(mock_filing, "AAPL", replace_existing=False)
        assert result2.success is True

        # Content should still be modified
        assert item_1.read_text() == "Modified content"

    def test_process_replaces_existing_files(
        self, processor: FilingProcessor, mock_filing: MockFiling, temp_dir: Path
    ):
        """Test that existing files are replaced when replace_existing=True."""
        # First process
        result1 = processor.process(mock_filing, "AAPL")
        assert result1.success is True

        # Modify a file
        items_dir = temp_dir / "AAPL" / mock_filing.accession_number / "items"
        item_1 = items_dir / "item_1.txt"
        item_1.write_text("Modified content")

        # Second process with replace
        result2 = processor.process(mock_filing, "AAPL", replace_existing=True)
        assert result2.success is True

        # Content should be original again
        assert item_1.read_text() == "Business description content..."

    def test_process_handles_no_items(self, processor: FilingProcessor):
        """Test processing a filing with no items."""
        filing = create_apple_filing(accession_number="0000320193-24-000125")
        result = processor.process(filing, "AAPL")

        assert result.success is True
        assert result.items_processed == 0

    def test_process_handles_no_xbrl(self, processor: FilingProcessor):
        """Test processing a filing with no XBRL data."""
        filing = create_apple_filing(accession_number="0000320193-24-000126")
        result = processor.process(filing, "AAPL")

        assert result.success is True
        assert result.statements_processed == 0

    def test_process_deterministic_output(
        self, processor: FilingProcessor, mock_filing: MockFiling
    ):
        """Test that processing produces deterministic output structure."""
        result = processor.process(mock_filing, "AAPL")

        assert result.success is True
        assert result.output is not None

        # Convert to dict and verify structure
        output_dict = result.output.to_dict()

        # Verify all expected keys are present
        expected_keys = {
            "accession_number",
            "form_type",
            "filing_date",
            "company_name",
            "cik",
            "filing_dir",
            "items_dir",
            "statements_dir",
            "filing_json_path",
            "html_path",
            "text_path",
            "items",
            "statements",
        }
        assert set(output_dict.keys()) == expected_keys

        # Verify items structure
        for item in output_dict["items"]:
            assert "item_name" in item
            assert "file_path" in item
            assert "content_length" in item
            assert "success" in item

        # Verify statements structure
        for stmt in output_dict["statements"]:
            assert "statement_name" in stmt
            assert "file_path" in stmt
            assert "content_length" in stmt
            assert "success" in stmt

    def test_process_result_serialization(
        self, processor: FilingProcessor, mock_filing: MockFiling
    ):
        """Test that ProcessingResult can be serialized to JSON."""
        result = processor.process(mock_filing, "AAPL")

        # Should be able to serialize to JSON without errors
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)
        assert json_str is not None

        # Should be able to deserialize back
        loaded = json.loads(json_str)
        assert loaded["success"] is True
        assert loaded["items_processed"] == 2
        assert loaded["statements_processed"] == 2


class TestFilingProcessorEdgeCases:
    """Edge case tests for FilingProcessor."""

    def test_process_with_empty_item_content(self, processor: FilingProcessor):
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
        # item_2 should fail due to empty content
        assert result.items_processed == 1
        assert "item_2" in result.failed_items

    def test_process_with_missing_item(self, processor: FilingProcessor):
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
        assert result.items_processed == 1
        assert "item_missing" in result.failed_items

    def test_process_with_statement_by_index(self, processor: FilingProcessor):
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
        assert result.statements_processed == 1

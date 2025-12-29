"""Tests for SEC filing downloader."""

import os
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from sources.sec_edgar.downloader import FilingDownloader


class TestFilingDownloaderInit:
    """Tests for FilingDownloader initialization."""

    def test_raises_without_edgar_identity(self, temp_dir: Path, monkeypatch):
        """Test that missing EDGAR_IDENTITY raises ValueError."""
        monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

        with pytest.raises(ValueError, match="EDGAR_IDENTITY"):
            FilingDownloader(temp_dir)


def create_mock_company_and_filing(
    accession_number: str = "0000320193-24-000123",
    form: str = "10-K",
    filing_date: date = date(2024, 11, 1),
    with_full_filing: bool = False,
) -> tuple[Mock, Mock, Mock]:
    """
    Create mock Company and Filing objects for testing.

    Returns:
        Tuple of (mock_company, mock_filing, mock_filings_collection)
    """
    mock_company = Mock()
    mock_company.name = "Apple Inc."

    mock_filing = Mock()
    mock_filing.accession_number = accession_number
    mock_filing.form = form
    mock_filing.filing_date = filing_date

    if with_full_filing:
        mock_filing.cik = 320193
        mock_filing.company = "Apple Inc."
        mock_filing.to_dict.return_value = {
            "accession_number": accession_number,
            "form": form,
            "filing_date": filing_date.isoformat(),
            "cik": 320193,
            "company": "Apple Inc.",
        }
        mock_filing.obj.return_value = None
        mock_filing.xbrl.return_value = None
        mock_filing.html.return_value = "<html>Test</html>"
        mock_filing.text.return_value = "Test text"

    # Create a mock filings collection that supports len() and iteration
    mock_filings = Mock()
    mock_filings.__len__ = Mock(return_value=1)
    mock_filings.__iter__ = Mock(return_value=iter([mock_filing]))
    mock_filings.head.return_value = mock_filings
    mock_company.get_filings.return_value = mock_filings

    return mock_company, mock_filing, mock_filings


class TestFilingDownloader:
    """Tests for FilingDownloader class."""

    def test_get_local_filings_empty_dir(self, downloader: FilingDownloader):
        """Test get_local_filings with non-existent directory."""
        result = downloader.get_local_filings("AAPL")
        assert result == set()

    def test_get_local_filings_with_existing(
        self, downloader: FilingDownloader, temp_dir: Path
    ):
        """Test get_local_filings with existing filing directories."""
        # Create some filing directories
        company_dir = temp_dir / "AAPL"
        company_dir.mkdir(parents=True)
        (company_dir / "0000320193-24-000123").mkdir()
        (company_dir / "0000320193-24-000124").mkdir()
        (company_dir / ".hidden").mkdir()  # Should be ignored

        result = downloader.get_local_filings("AAPL")
        assert result == {"0000320193-24-000123", "0000320193-24-000124"}

    def test_get_local_filings_ignores_files(
        self, downloader: FilingDownloader, temp_dir: Path
    ):
        """Test that get_local_filings ignores regular files."""
        company_dir = temp_dir / "AAPL"
        company_dir.mkdir(parents=True)
        (company_dir / "0000320193-24-000123").mkdir()
        (company_dir / "some_file.txt").touch()  # Should be ignored

        result = downloader.get_local_filings("AAPL")
        assert result == {"0000320193-24-000123"}

    @patch("sources.sec_edgar.downloader.Company")
    def test_download_filings_skips_existing(
        self, mock_company_class: Mock, downloader: FilingDownloader, temp_dir: Path
    ):
        """Test that existing filings are skipped."""
        # Create existing filing directory
        company_dir = temp_dir / "AAPL"
        company_dir.mkdir(parents=True)
        (company_dir / "0000320193-24-000123").mkdir()

        mock_company, _, _ = create_mock_company_and_filing()
        mock_company_class.return_value = mock_company

        # Download (should skip)
        results = downloader.download_filings("AAPL", limit=1)

        # No results since filing was skipped
        assert len(results) == 0

    @patch("sources.sec_edgar.downloader.Company")
    def test_download_filings_processes_new(
        self, mock_company_class: Mock, downloader: FilingDownloader
    ):
        """Test that new filings are processed."""
        mock_company, _, _ = create_mock_company_and_filing(with_full_filing=True)
        mock_company_class.return_value = mock_company

        # Download
        results = downloader.download_filings("AAPL", limit=1)

        assert len(results) == 1
        assert results[0].success is True

    @patch("sources.sec_edgar.downloader.Company")
    def test_download_filings_with_replace(
        self, mock_company_class: Mock, downloader: FilingDownloader, temp_dir: Path
    ):
        """Test that replace_existing forces reprocessing."""
        # Create existing filing directory
        company_dir = temp_dir / "AAPL"
        company_dir.mkdir(parents=True)
        (company_dir / "0000320193-24-000123").mkdir()

        mock_company, _, _ = create_mock_company_and_filing(with_full_filing=True)
        mock_company_class.return_value = mock_company

        # Download with replace_existing=True
        results = downloader.download_filings("AAPL", limit=1, replace_existing=True)

        # Should process despite existing directory
        assert len(results) == 1
        assert results[0].success is True

    def test_ticker_normalized_to_uppercase(self, temp_dir: Path):
        """Test that ticker symbols are normalized to uppercase."""
        downloader = FilingDownloader(temp_dir, verbose=False)

        # Create directory with uppercase ticker
        company_dir = temp_dir / "AAPL"
        company_dir.mkdir(parents=True)
        (company_dir / "0000320193-24-000123").mkdir()

        # Query with lowercase should still find it
        result = downloader.get_local_filings("AAPL")
        assert "0000320193-24-000123" in result


class TestFilingDownloaderIntegration:
    """Integration tests that verify the downloader works with the processor."""

    def test_processor_integration(self, temp_dir: Path):
        """Test that the downloader correctly integrates with the processor."""
        downloader = FilingDownloader(temp_dir, verbose=False)

        # Verify processor is created with correct base_dir
        assert downloader.processor.base_dir == temp_dir

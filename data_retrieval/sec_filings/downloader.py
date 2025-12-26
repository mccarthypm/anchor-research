"""
SEC filing downloader using edgartools.

This module provides functionality to download SEC filings for companies
and coordinate with the processor for extraction.
"""

from pathlib import Path
from typing import Iterator

from edgar import Company, set_identity

from data_retrieval.sec_filings.processor import FilingProcessor
from data_retrieval.sec_filings.models import ProcessingResult


class FilingDownloader:
    """
    Downloads and processes SEC filings for companies.

    This class coordinates:
    - Fetching filings from SEC EDGAR via edgartools
    - Tracking already-downloaded filings
    - Processing new filings via FilingProcessor
    """

    def __init__(
        self,
        base_dir: Path | str,
        identity: str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the filing downloader.

        Args:
            base_dir: Base directory for storing processed filings
            identity: SEC EDGAR identity string (email for rate limiting)
            verbose: Whether to print progress messages
        """
        self.base_dir = Path(base_dir)
        self.verbose = verbose
        self.processor = FilingProcessor(base_dir, verbose=verbose)

        if identity:
            set_identity(identity)

    def _log(self, message: str) -> None:
        """Print a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def get_local_filings(self, ticker: str) -> set[str]:
        """
        Get set of accession numbers already downloaded locally.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Set of accession numbers that exist locally
        """
        company_dir = self.base_dir / ticker
        if not company_dir.exists():
            return set()

        local_accessions = set()
        for item in company_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                local_accessions.add(item.name)

        return local_accessions

    def get_filings(
        self,
        ticker: str,
        form: str = "10-K",
        limit: int | None = None,
    ) -> Iterator:
        """
        Get filings for a company from SEC EDGAR.

        Args:
            ticker: Stock ticker symbol
            form: Form type (e.g., "10-K", "10-Q")
            limit: Maximum number of filings to retrieve

        Returns:
            Iterator of filing objects
        """
        company = Company(ticker)
        self._log(f"Company: {company.name}")

        filings = company.get_filings(form=form)
        if limit:
            filings = filings.head(limit)

        return iter(filings)

    def download_filings(
        self,
        ticker: str,
        form: str = "10-K",
        limit: int | None = None,
        replace_existing: bool = False,
    ) -> list[ProcessingResult]:
        """
        Download and process filings for a company.

        Args:
            ticker: Stock ticker symbol
            form: Form type (e.g., "10-K", "10-Q")
            limit: Maximum number of filings to download
            replace_existing: Whether to replace existing files

        Returns:
            List of ProcessingResult objects for each filing
        """
        ticker = ticker.upper()
        results: list[ProcessingResult] = []

        # Get filings from SEC
        filings = list(self.get_filings(ticker, form, limit))
        self._log(f"Found {len(filings)} {form} filings")

        # Check what's already downloaded
        local_accessions = self.get_local_filings(ticker)
        self._log(f"Already downloaded locally: {len(local_accessions)}")

        # Process each filing
        downloaded = 0
        skipped = 0

        for filing in filings:
            if filing.accession_number in local_accessions and not replace_existing:
                skipped += 1
                self._log(f"Skipped (exists): {filing.accession_number}")
                continue

            self._log(
                f"Processing: {filing.form} ({filing.filing_date}) - {filing.accession_number}"
            )
            result = self.processor.process(filing, ticker, replace_existing)
            results.append(result)

            if result.success:
                downloaded += 1
                self._log(f"  Complete: {result.items_processed} items, {result.statements_processed} statements")
            else:
                self._log(f"  Failed: {result.error}")

        self._log(f"Download Summary: {downloaded} new, {skipped} skipped")
        return results

    def download_single_filing(
        self,
        ticker: str,
        accession_number: str,
        replace_existing: bool = False,
    ) -> ProcessingResult | None:
        """
        Download and process a single filing by accession number.

        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            replace_existing: Whether to replace existing files

        Returns:
            ProcessingResult for the filing, or None if not found
        """
        ticker = ticker.upper()
        company = Company(ticker)

        # Search for the specific filing
        filings = company.get_filings()
        for filing in filings:
            if filing.accession_number == accession_number:
                self._log(f"Found filing: {filing.form} ({filing.filing_date})")
                return self.processor.process(filing, ticker, replace_existing)

        self._log(f"Filing not found: {accession_number}")
        return None


"""
SEC filing downloader using edgartools.

This module provides functionality to download SEC filings for companies
and coordinate with the processor for extraction.
Stores all files in Firebase Storage instead of local file system.
"""

import os
from pathlib import Path

from edgar import Company

from sources.firebase_storage import FirebaseStorageService
from sources.sec_edgar.processor import FilingProcessor, ProcessingResult


class FilingDownloader:
    """
    Downloads and processes SEC filings for companies.

    This class coordinates:
    - Fetching filings from SEC EDGAR via edgartools
    - Tracking already-downloaded filings
    - Processing new filings via FilingProcessor

    Requires EDGAR_IDENTITY environment variable to be set (e.g., in .env file).
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the filing downloader.

        Args:
            base_dir: Deprecated - kept for compatibility but not used (files go to Firebase Storage)
            verbose: Whether to print progress messages

        Raises:
            ValueError: If EDGAR_IDENTITY environment variable is not set
        """

        if not os.environ.get("EDGAR_IDENTITY"):
            raise ValueError(
                "EDGAR_IDENTITY environment variable is required. "
                f"Add EDGAR_IDENTITY=FirstName LastNameyour-email@example.com to your .env file."
            )

        self.verbose = verbose
        self.processor = FilingProcessor(base_dir, verbose=verbose)
        self.storage = FirebaseStorageService

    def _log(self, message: str) -> None:
        """Print a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def get_local_filings(self, ticker: str) -> set[str]:
        """
        Get set of accession numbers already downloaded to Firebase Storage.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Set of accession numbers that exist in Firebase Storage
        """
        try:
            accessions = self.storage.list_filings(ticker)
            return set(accessions)
        except Exception as e:
            if self.verbose:
                print(f"Error listing filings from Firebase Storage: {e}")
            return set()

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
        company = Company(ticker)
        self._log(f"Getting {form} filings for {company.name}")

        filings = company.get_filings(form=form)
        if limit:
            filings = filings.head(limit)
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
            result = self.processor.process(filing, ticker)
            results.append(result)

            if result.success:
                downloaded += 1
                self._log(f"  Complete")
            else:
                self._log(f"  Failed: {result.error}")

        self._log(f"Download Summary: {downloaded} new, {skipped} skipped")
        return results

    def download_single_filing(
        self,
        ticker: str,
        accession_number: str,
    ) -> ProcessingResult | None:
        """
        Download and process a single filing by accession number.

        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number

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
                return self.processor.process(filing, ticker)

        self._log(f"Filing not found: {accession_number}")
        return None

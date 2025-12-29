"""
Filing processor for extracting and saving SEC filing content.

This module provides deterministic processing of SEC filings,
extracting items, XBRL statements, and raw content.
Stores all files in Firebase Storage instead of local file system.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from sources.firebase_storage import FirebaseStorageService


class FilingProtocol(Protocol):
    """Protocol defining the expected interface for a filing object."""

    accession_number: str
    form: str
    filing_date: Any
    cik: int
    company: str

    def to_dict(self) -> dict: ...
    def obj(self) -> Any: ...
    def xbrl(self) -> Any: ...
    def html(self) -> str | None: ...
    def text(self) -> str | None: ...


@dataclass
class ProcessingResult:
    """Simple result of processing a filing."""

    success: bool
    error: str | None = None


class FilingProcessor:
    """
    Processes SEC filings and extracts content in a deterministic manner.

    This class handles:
    - Extracting and saving filing items (e.g., Item 1, Item 7) to Firebase Storage
    - Extracting and saving XBRL financial statements to Firebase Storage
    - Saving raw HTML and text content to Firebase Storage
    - Generating filing metadata JSON in Firebase Storage

    All files are stored in Firebase Storage at:
    companies/{ticker}/sec_edgar/{accession_number}/{file_path}
    """

    def __init__(self, base_dir: Path | str | None = None, verbose: bool = False):
        """
        Initialize the filing processor.

        Args:
            base_dir: Deprecated - kept for compatibility but not used (files go to Firebase Storage)
            verbose: Whether to print progress messages
        """
        # base_dir is kept for backward compatibility but not used
        self.verbose = verbose
        self.storage = FirebaseStorageService

    def _log(self, message: str) -> None:
        """Print a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _sanitize_form_type(self, form: str) -> str:
        """Sanitize form type for use in filenames (e.g., '10-K/A' -> '10-K_A')."""
        return form.replace("/", "_")

    def _save_filing_metadata(
        self, filing: FilingProtocol, ticker: str, accession_number: str
    ) -> None:
        """Save filing metadata as JSON to Firebase Storage."""
        def serialize(obj: Any) -> Any:
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Path):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        filing_dict = filing.to_dict()
        metadata_json = json.dumps(filing_dict, indent=4, default=serialize)
        
        self.storage.upload_file(
            ticker=ticker,
            accession_number=accession_number,
            file_path="filing.json",
            content=metadata_json,
            content_type="application/json",
        )
        self._log(f"  Saved filing metadata")

    def _process_items(
        self, filing: FilingProtocol, ticker: str, accession_number: str
    ) -> int:
        """
        Extract and save filing items to Firebase Storage.

        Returns:
            Count of successfully processed items
        """
        processed = 0
        filing_obj = filing.obj()

        if not filing_obj or not hasattr(filing_obj, "items") or len(filing_obj.items) == 0:
            self._log("  No items found in filing")
            return processed

        for item_name in filing_obj.items:
            try:
                item_content = filing_obj[item_name]
                if item_content:
                    file_path = f"items/{item_name}.txt"
                    self.storage.upload_file(
                        ticker=ticker,
                        accession_number=accession_number,
                        file_path=file_path,
                        content=item_content,
                        content_type="text/plain; charset=utf-8",
                    )
                    self._log(f"  Saved item: {item_name}.txt")
                    processed += 1
                else:
                    self._log(f"  Skipped item (empty): {item_name}")
            except Exception as e:
                self._log(f"  Error processing item {item_name}: {e}")

        return processed

    def _process_statements(
        self, filing: FilingProtocol, ticker: str, accession_number: str
    ) -> int:
        """
        Extract and save XBRL financial statements to Firebase Storage.

        Returns:
            Count of successfully processed statements
        """
        processed = 0
        xbrl = filing.xbrl()

        if not xbrl:
            self._log("  No XBRL data found in filing")
            return processed

        xbrl_statements = xbrl.statements
        for idx, stmt_info in enumerate(xbrl_statements.statements):
            statement_definition = stmt_info.get("definition")
            statement_role = stmt_info.get("role")

            # Determine statement name
            if statement_definition:
                statement_name = statement_definition
            elif statement_role:
                statement_name = statement_role
            else:
                statement_name = f"Statement{idx}"
                self._log(f"  Statement {idx} has no definition or role, using index")

            try:
                # Get statement by definition, role, or index
                if statement_definition:
                    statement = xbrl_statements[statement_definition]
                elif statement_role:
                    statement = xbrl_statements[statement_role]
                else:
                    statement = xbrl_statements[idx]

                if statement:
                    statement_markdown = statement.render().to_markdown()
                    file_path = f"statements/{statement_name}.md"
                    self.storage.upload_file(
                        ticker=ticker,
                        accession_number=accession_number,
                        file_path=file_path,
                        content=statement_markdown,
                        content_type="text/markdown; charset=utf-8",
                    )
                    self._log(f"  Saved statement: {statement_name}.md")
                    processed += 1
                else:
                    self._log(f"  Skipped statement (not found): {statement_name}")
            except Exception as e:
                self._log(f"  Error processing statement {statement_name}: {e}")

        return processed

    def _save_raw_content(
        self,
        filing: FilingProtocol,
        ticker: str,
        accession_number: str,
        file_extension: str,
    ) -> bool:
        """
        Save raw filing content (HTML or text) to Firebase Storage.

        Args:
            filing: The filing object
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            file_extension: File extension ('html' or 'txt')

        Returns:
            True if content was saved, False otherwise
        """
        safe_form = self._sanitize_form_type(filing.form)
        file_path = f"{safe_form}_{filing.filing_date}.{file_extension}"

        # Get content based on file type
        content = filing.html() if file_extension == "html" else filing.text()
        if content:
            content_type = (
                "text/html; charset=utf-8"
                if file_extension == "html"
                else "text/plain; charset=utf-8"
            )
            self.storage.upload_file(
                ticker=ticker,
                accession_number=accession_number,
                file_path=file_path,
                content=content,
                content_type=content_type,
            )
            self._log(f"  Saved {file_extension.upper()}: {file_path}")
            return True
        return False

    def process(
        self,
        filing: FilingProtocol,
        ticker: str,
    ) -> ProcessingResult:
        """
        Process a single SEC filing and upload to Firebase Storage.

        Args:
            filing: The filing object to process (from edgartools)
            ticker: The stock ticker symbol

        Returns:
            ProcessingResult indicating success or failure
        """
        ticker = ticker.upper()
        accession_number = filing.accession_number

        try:
            # Delete existing filing data if it exists (for replace operations)
            # Note: We'll let upload overwrite files, but could delete first if needed
            # self.storage.delete_filing(ticker, accession_number)

            # Save filing metadata
            self._save_filing_metadata(filing, ticker, accession_number)

            # Process items
            items_count = self._process_items(filing, ticker, accession_number)
            self._log(f"  Processed {items_count} items")

            # Process XBRL statements
            statements_count = self._process_statements(filing, ticker, accession_number)
            self._log(f"  Processed {statements_count} statements")

            # Save raw content
            self._save_raw_content(filing, ticker, accession_number, "html")
            self._save_raw_content(filing, ticker, accession_number, "txt")

            return ProcessingResult(success=True)

        except Exception as e:
            self._log(f"Error processing filing {accession_number}: {e}")
            return ProcessingResult(success=False, error=str(e))

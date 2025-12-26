"""
Filing processor for extracting and saving SEC filing content.

This module provides deterministic processing of SEC filings,
extracting items, XBRL statements, and raw content.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol


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
    - Creating directory structure for filing storage
    - Extracting and saving filing items (e.g., Item 1, Item 7)
    - Extracting and saving XBRL financial statements
    - Saving raw HTML and text content
    - Generating filing metadata JSON

    Processing is done in a temporary directory first, then atomically
    moved to the final location on success.
    """

    def __init__(self, base_dir: Path | str, verbose: bool = False):
        """
        Initialize the filing processor.

        Args:
            base_dir: Base directory for storing processed filings
            verbose: Whether to print progress messages
        """
        self.base_dir = Path(base_dir)
        self.verbose = verbose

    def _log(self, message: str) -> None:
        """Print a message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def _sanitize_form_type(self, form: str) -> str:
        """Sanitize form type for use in filenames (e.g., '10-K/A' -> '10-K_A')."""
        return form.replace("/", "_")

    def _save_filing_metadata(self, filing: FilingProtocol, filing_dir: Path) -> None:
        """Save filing metadata as JSON."""
        def serialize(obj: Any) -> str:
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Path):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        filing_dict = filing.to_dict()
        filing_json_path = filing_dir / "filing.json"
        filing_json_path.write_text(
            json.dumps(filing_dict, indent=4, default=serialize),
            encoding="utf-8",
        )
        self._log(f"  Saved filing metadata")

    def _process_items(self, filing: FilingProtocol, items_dir: Path) -> int:
        """
        Extract and save filing items.

        Returns:
            Count of successfully processed items
        """
        processed = 0
        filing_obj = filing.obj()

        if not filing_obj or not hasattr(filing_obj, "items") or len(filing_obj.items) == 0:
            self._log("  No items found in filing")
            return processed

        for item_name in filing_obj.items:
            item_file = items_dir / f"{item_name}.txt"

            try:
                item_content = filing_obj[item_name]
                if item_content:
                    item_file.write_text(item_content, encoding="utf-8")
                    self._log(f"  Saved item: {item_file.name}")
                    processed += 1
                else:
                    self._log(f"  Skipped item (empty): {item_name}")
            except Exception as e:
                self._log(f"  Error processing item {item_name}: {e}")

        return processed

    def _process_statements(self, filing: FilingProtocol, statements_dir: Path) -> int:
        """
        Extract and save XBRL financial statements.

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

            statement_file = statements_dir / f"{statement_name}.md"

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
                    statement_file.write_text(statement_markdown, encoding="utf-8")
                    self._log(f"  Saved statement: {statement_file.name}")
                    processed += 1
                else:
                    self._log(f"  Skipped statement (not found): {statement_name}")
            except Exception as e:
                self._log(f"  Error processing statement {statement_name}: {e}")

        return processed

    def _save_raw_content(
        self,
        filing: FilingProtocol,
        filing_dir: Path,
        file_extension: str,
    ) -> bool:
        """
        Save raw filing content (HTML or text).

        Args:
            filing: The filing object
            filing_dir: Directory to save the file
            file_extension: File extension ('html' or 'txt')

        Returns:
            True if content was saved, False otherwise
        """
        safe_form = self._sanitize_form_type(filing.form)
        file_path = filing_dir / f"{safe_form}_{filing.filing_date}.{file_extension}"

        # Get content based on file type
        content = filing.html() if file_extension == "html" else filing.text()
        if content:
            file_path.write_text(content, encoding="utf-8")
            self._log(f"  Saved {file_extension.upper()}: {file_path.name}")
            return True
        return False

    def process(
        self,
        filing: FilingProtocol,
        ticker: str,
    ) -> ProcessingResult:
        """
        Process a single SEC filing.

        Processing is done in a temporary directory first. On success,
        the temporary directory replaces any existing directory at the
        final location.

        Args:
            filing: The filing object to process (from edgartools)
            ticker: The stock ticker symbol

        Returns:
            ProcessingResult indicating success or failure
        """
        final_dir = self.base_dir / ticker / "sec_edgar" / filing.accession_number

        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_base:
            temp_dir = Path(temp_base) / filing.accession_number
            items_dir = temp_dir / "items"
            statements_dir = temp_dir / "statements"

            temp_dir.mkdir(parents=True, exist_ok=True)
            items_dir.mkdir(parents=True, exist_ok=True)
            statements_dir.mkdir(parents=True, exist_ok=True)

            try:
                # Save filing metadata
                self._save_filing_metadata(filing, temp_dir)

                # Process items
                items_count = self._process_items(filing, items_dir)
                self._log(f"  Processed {items_count} items")

                # Process XBRL statements
                statements_count = self._process_statements(filing, statements_dir)
                self._log(f"  Processed {statements_count} statements")

                # Save raw content
                self._save_raw_content(filing, temp_dir, "html")
                self._save_raw_content(filing, temp_dir, "txt")

                # Ensure parent directory exists
                final_dir.parent.mkdir(parents=True, exist_ok=True)

                # Remove existing directory if it exists
                if final_dir.exists():
                    shutil.rmtree(final_dir)

                # Move temp directory to final location
                shutil.move(str(temp_dir), str(final_dir))

                return ProcessingResult(success=True)

            except Exception as e:
                self._log(f"Error processing filing {filing.accession_number}: {e}")
                return ProcessingResult(success=False, error=str(e))

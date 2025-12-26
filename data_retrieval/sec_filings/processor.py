"""
Filing processor for extracting and saving SEC filing content.

This module provides deterministic processing of SEC filings,
extracting items, XBRL statements, and raw content.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from data_retrieval.sec_filings.models import (
    FilingOutput,
    ProcessingResult,
    ItemOutput,
    StatementOutput,
    json_serializer,
)


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


class FilingProcessor:
    """
    Processes SEC filings and extracts content in a deterministic manner.

    This class handles:
    - Creating directory structure for filing storage
    - Extracting and saving filing items (e.g., Item 1, Item 7)
    - Extracting and saving XBRL financial statements
    - Saving raw HTML and text content
    - Generating filing metadata JSON
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

    def _create_directories(self, ticker: str, accession_number: str) -> tuple[Path, Path, Path]:
        """
        Create the directory structure for a filing.

        Returns:
            Tuple of (filing_dir, items_dir, statements_dir)
        """
        filing_dir = self.base_dir / ticker / accession_number
        items_dir = filing_dir / "items"
        statements_dir = filing_dir / "statements"

        filing_dir.mkdir(parents=True, exist_ok=True)
        items_dir.mkdir(parents=True, exist_ok=True)
        statements_dir.mkdir(parents=True, exist_ok=True)

        return filing_dir, items_dir, statements_dir

    def _save_filing_metadata(self, filing: FilingProtocol, filing_dir: Path) -> Path:
        """Save filing metadata as JSON."""
        filing_dict = filing.to_dict()
        filing_json_path = filing_dir / "filing.json"
        filing_json_path.write_text(
            json.dumps(filing_dict, indent=4, default=json_serializer),
            encoding="utf-8",
        )
        self._log(f"  Saved filing metadata: {filing_json_path}")
        return filing_json_path

    def _process_items(
        self,
        filing: FilingProtocol,
        items_dir: Path,
        replace_existing: bool = False,
    ) -> list[ItemOutput]:
        """
        Extract and save filing items.

        Returns:
            List of ItemOutput objects describing processed items
        """
        items: list[ItemOutput] = []
        filing_obj = filing.obj()

        if not filing_obj or not hasattr(filing_obj, "items") or len(filing_obj.items) == 0:
            self._log("  No items found in filing")
            return items

        for item_name in filing_obj.items:
            item_file = items_dir / f"{item_name}.txt"

            if item_file.exists() and not replace_existing:
                self._log(f"  Skipped (exists): {item_file.name}")
                # Read existing file to get content length
                content = item_file.read_text(encoding="utf-8")
                items.append(
                    ItemOutput(
                        item_name=item_name,
                        file_path=item_file,
                        content_length=len(content),
                        success=True,
                    )
                )
                continue

            try:
                item_content = filing_obj[item_name]
                if item_content:
                    item_file.write_text(item_content, encoding="utf-8")
                    self._log(f"  Saved item: {item_file.name}")
                    items.append(
                        ItemOutput(
                            item_name=item_name,
                            file_path=item_file,
                            content_length=len(item_content),
                            success=True,
                        )
                    )
                else:
                    items.append(
                        ItemOutput(
                            item_name=item_name,
                            file_path=item_file,
                            content_length=0,
                            success=False,
                            error="Empty content",
                        )
                    )
            except Exception as e:
                self._log(f"  Error processing item {item_name}: {e}")
                items.append(
                    ItemOutput(
                        item_name=item_name,
                        file_path=item_file,
                        content_length=0,
                        success=False,
                        error=str(e),
                    )
                )

        return items

    def _process_statements(
        self,
        filing: FilingProtocol,
        statements_dir: Path,
        replace_existing: bool = False,
    ) -> list[StatementOutput]:
        """
        Extract and save XBRL financial statements.

        Returns:
            List of StatementOutput objects describing processed statements
        """
        statements: list[StatementOutput] = []
        xbrl = filing.xbrl()

        if not xbrl:
            self._log("  No XBRL data found in filing")
            return statements

        xbrl_statements = xbrl.statements
        for idx, stmt_info in enumerate(xbrl_statements.statements):
            statement_definition = stmt_info.get("definition")
            statement_role = stmt_info.get("role")

            # Determine statement name and file path
            if statement_definition:
                statement_name = statement_definition
            elif statement_role:
                statement_name = statement_role
            else:
                statement_name = f"Statement{idx}"
                self._log(f"  Statement {idx} has no definition or role, using index")

            statement_file = statements_dir / f"{statement_name}.md"

            if statement_file.exists() and not replace_existing:
                self._log(f"  Skipped (exists): {statement_file.name}")
                # Read existing file to get content length
                content = statement_file.read_text(encoding="utf-8")
                statements.append(
                    StatementOutput(
                        statement_name=statement_name,
                        file_path=statement_file,
                        content_length=len(content),
                        success=True,
                    )
                )
                continue

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
                    statements.append(
                        StatementOutput(
                            statement_name=statement_name,
                            file_path=statement_file,
                            content_length=len(statement_markdown),
                            success=True,
                        )
                    )
                else:
                    statements.append(
                        StatementOutput(
                            statement_name=statement_name,
                            file_path=statement_file,
                            content_length=0,
                            success=False,
                            error="Statement not found",
                        )
                    )
            except Exception as e:
                self._log(f"  Error processing statement {statement_name}: {e}")
                statements.append(
                    StatementOutput(
                        statement_name=statement_name,
                        file_path=statement_file,
                        content_length=0,
                        success=False,
                        error=str(e),
                    )
                )

        return statements

    def _save_html_content(
        self,
        filing: FilingProtocol,
        filing_dir: Path,
        replace_existing: bool = False,
    ) -> Path | None:
        """Save raw HTML content."""
        safe_form = self._sanitize_form_type(filing.form)
        html_file = filing_dir / f"{safe_form}_{filing.filing_date}.html"

        if html_file.exists() and not replace_existing:
            self._log(f"  Skipped (exists): {html_file.name}")
            return html_file

        html_content = filing.html()
        if html_content:
            html_file.write_text(html_content, encoding="utf-8")
            self._log(f"  Saved HTML: {html_file.name}")
            return html_file
        return None

    def _save_text_content(
        self,
        filing: FilingProtocol,
        filing_dir: Path,
        replace_existing: bool = False,
    ) -> Path | None:
        """Save raw text content."""
        safe_form = self._sanitize_form_type(filing.form)
        text_file = filing_dir / f"{safe_form}_{filing.filing_date}.txt"

        if text_file.exists() and not replace_existing:
            self._log(f"  Skipped (exists): {text_file.name}")
            return text_file

        text_content = filing.text()
        if text_content:
            text_file.write_text(text_content, encoding="utf-8")
            self._log(f"  Saved text: {text_file.name}")
            return text_file
        return None

    def process(
        self,
        filing: FilingProtocol,
        ticker: str,
        replace_existing: bool = False,
    ) -> ProcessingResult:
        """
        Process a single SEC filing.

        Args:
            filing: The filing object to process (from edgartools)
            ticker: The stock ticker symbol
            replace_existing: Whether to replace existing files

        Returns:
            ProcessingResult with details about the processing outcome
        """
        try:
            # Create directory structure
            filing_dir, items_dir, statements_dir = self._create_directories(
                ticker, filing.accession_number
            )

            # Save filing metadata
            filing_json_path = self._save_filing_metadata(filing, filing_dir)

            # Process items
            items = self._process_items(filing, items_dir, replace_existing)

            # Process XBRL statements
            statements = self._process_statements(filing, statements_dir, replace_existing)

            # Save raw content
            html_path = self._save_html_content(filing, filing_dir, replace_existing)
            text_path = self._save_text_content(filing, filing_dir, replace_existing)

            # Create output object
            output = FilingOutput(
                accession_number=filing.accession_number,
                form_type=filing.form,
                filing_date=filing.filing_date,
                company_name=filing.company,
                cik=filing.cik,
                filing_dir=filing_dir,
                items_dir=items_dir,
                statements_dir=statements_dir,
                filing_json_path=filing_json_path,
                html_path=html_path,
                text_path=text_path,
                items=items,
                statements=statements,
            )

            return ProcessingResult(success=True, output=output)

        except Exception as e:
            self._log(f"Error processing filing {filing.accession_number}: {e}")
            return ProcessingResult(success=False, error=str(e))


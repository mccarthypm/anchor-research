"""
Data models for SEC filing processing.

These models provide deterministic output structures for filing processing,
enabling consistent testing and verification of outputs.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


def json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


@dataclass
class ItemOutput:
    """Represents a processed item from a filing (e.g., Item 1, Item 7)."""

    item_name: str
    file_path: Path
    content_length: int
    success: bool
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "item_name": self.item_name,
            "file_path": str(self.file_path),
            "content_length": self.content_length,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class StatementOutput:
    """Represents a processed financial statement from XBRL data."""

    statement_name: str
    file_path: Path
    content_length: int
    success: bool
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "statement_name": self.statement_name,
            "file_path": str(self.file_path),
            "content_length": self.content_length,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class FilingOutput:
    """Represents the expected output structure from processing a filing."""

    accession_number: str
    form_type: str
    filing_date: date
    company_name: str
    cik: int
    filing_dir: Path
    items_dir: Path
    statements_dir: Path
    filing_json_path: Path
    html_path: Path | None = None
    text_path: Path | None = None
    items: list[ItemOutput] = field(default_factory=list)
    statements: list[StatementOutput] = field(default_factory=list)

    @property
    def item_files(self) -> list[Path]:
        """Return list of successfully processed item file paths."""
        return [item.file_path for item in self.items if item.success]

    @property
    def statement_files(self) -> list[Path]:
        """Return list of successfully processed statement file paths."""
        return [stmt.file_path for stmt in self.statements if stmt.success]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "accession_number": self.accession_number,
            "form_type": self.form_type,
            "filing_date": self.filing_date.isoformat(),
            "company_name": self.company_name,
            "cik": self.cik,
            "filing_dir": str(self.filing_dir),
            "items_dir": str(self.items_dir),
            "statements_dir": str(self.statements_dir),
            "filing_json_path": str(self.filing_json_path),
            "html_path": str(self.html_path) if self.html_path else None,
            "text_path": str(self.text_path) if self.text_path else None,
            "items": [item.to_dict() for item in self.items],
            "statements": [stmt.to_dict() for stmt in self.statements],
        }


@dataclass
class ProcessingResult:
    """Result of processing a filing with detailed tracking."""

    success: bool
    output: FilingOutput | None = None
    error: str | None = None

    @property
    def items_processed(self) -> int:
        """Count of successfully processed items."""
        if self.output is None:
            return 0
        return sum(1 for item in self.output.items if item.success)

    @property
    def statements_processed(self) -> int:
        """Count of successfully processed statements."""
        if self.output is None:
            return 0
        return sum(1 for stmt in self.output.statements if stmt.success)

    @property
    def failed_items(self) -> list[str]:
        """List of item names that failed to process."""
        if self.output is None:
            return []
        return [item.item_name for item in self.output.items if not item.success]

    @property
    def failed_statements(self) -> list[str]:
        """List of statement names that failed to process."""
        if self.output is None:
            return []
        return [stmt.statement_name for stmt in self.output.statements if not stmt.success]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "error": self.error,
            "items_processed": self.items_processed,
            "statements_processed": self.statements_processed,
            "failed_items": self.failed_items,
            "failed_statements": self.failed_statements,
            "output": self.output.to_dict() if self.output else None,
        }


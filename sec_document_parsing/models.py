"""
Data models for SEC document parsing.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


@dataclass
class FilingOutput:
    """Represents the expected output structure from processing a filing."""

    accession_number: str
    form_type: str
    filing_date: date
    filing_dir: Path
    items_dir: Path
    statements_dir: Path
    filing_json_path: Path
    html_path: Path | None = None
    text_path: Path | None = None
    item_files: list[Path] = field(default_factory=list)
    statement_files: list[Path] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "accession_number": self.accession_number,
            "form_type": self.form_type,
            "filing_date": self.filing_date.isoformat(),
            "filing_dir": str(self.filing_dir),
            "items_dir": str(self.items_dir),
            "statements_dir": str(self.statements_dir),
            "filing_json_path": str(self.filing_json_path),
            "html_path": str(self.html_path) if self.html_path else None,
            "text_path": str(self.text_path) if self.text_path else None,
            "item_files": [str(p) for p in self.item_files],
            "statement_files": [str(p) for p in self.statement_files],
        }


@dataclass
class ProcessingResult:
    """Result of processing a filing."""

    success: bool
    output: FilingOutput | None = None
    error: str | None = None
    items_processed: int = 0
    statements_processed: int = 0
    skipped_items: list[str] = field(default_factory=list)
    failed_statements: list[str] = field(default_factory=list)


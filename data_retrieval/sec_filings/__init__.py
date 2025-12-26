"""
SEC Filings retrieval and parsing module.

Provides utilities for downloading SEC filings, extracting financial statements,
and saving structured data in a deterministic manner.
"""

from data_retrieval.sec_filings.models import (
    FilingOutput,
    ProcessingResult,
    ItemOutput,
    StatementOutput,
)
from data_retrieval.sec_filings.processor import FilingProcessor
from data_retrieval.sec_filings.downloader import FilingDownloader

__all__ = [
    "FilingOutput",
    "ProcessingResult",
    "ItemOutput",
    "StatementOutput",
    "FilingProcessor",
    "FilingDownloader",
]


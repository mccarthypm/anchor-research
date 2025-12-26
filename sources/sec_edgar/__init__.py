"""
SEC EDGAR retrieval and parsing module.

Provides utilities for downloading SEC filings from EDGAR, extracting financial statements,
and saving structured data in a deterministic manner.
"""

from sources.sec_edgar.processor import FilingProcessor, ProcessingResult
from sources.sec_edgar.downloader import FilingDownloader

__all__ = [
    "ProcessingResult",
    "FilingProcessor",
    "FilingDownloader",
]

"""
Sources module for deterministic data engineering.

This module provides utilities for retrieving and processing financial data
from various sources including SEC filings.
"""

from sources.sec_edgar import (
    FilingProcessor,
    FilingDownloader,
    ProcessingResult,
)

__all__ = [
    "FilingProcessor",
    "FilingDownloader",
    "ProcessingResult",
]

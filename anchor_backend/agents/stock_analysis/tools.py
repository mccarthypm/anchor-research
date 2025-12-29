"""
SEC Filing Tools for the Stock Analysis Agent.

These tools provide access to SEC filings stored in Firebase Storage for a specific ticker.
All tools are scoped to a single ticker and access files at companies/{ticker}/sec_edgar/ in Firebase Storage.
"""

import json
from pathlib import Path
from typing import Any

from google.adk.tools import FunctionTool
from sources.firebase_storage import FirebaseStorageService


def create_filing_tools(ticker: str, companies_dir: Path | None = None) -> list[FunctionTool]:
    """
    Create a set of filing tools scoped to a specific ticker.
    
    Args:
        ticker: The stock ticker symbol (e.g., "AAPL")
        companies_dir: Deprecated - kept for compatibility but not used (files are in Firebase Storage)
        
    Returns:
        List of FunctionTool instances for the agent
    """
    ticker = ticker.upper()
    storage = FirebaseStorageService
    
    def get_filing_metadata(accession_number: str) -> dict[str, Any] | None:
        """Get filing metadata from Firebase Storage."""
        metadata_json = storage.download_file_text(ticker, accession_number, "filing.json")
        if metadata_json:
            return json.loads(metadata_json)
        return None
        
    def list_filings() -> dict[str, Any]:
        """
        List all available SEC filings for the ticker from Firebase Storage.
        
        Returns a list of filings with their accession numbers, form types, and dates.
        Use this to discover what filings are available before reading specific items.
        """
        try:
            accession_numbers = storage.list_filings(ticker)
            
            if not accession_numbers:
                return {
                    "status": "error",
                    "message": f"No filings found for {ticker}. Run download_sec_data.py first.",
                }
            
            filings = []
            for accession_number in sorted(accession_numbers, reverse=True):
                metadata = get_filing_metadata(accession_number)
                if metadata:
                    filings.append(metadata)
            
            return {
                "status": "success",
                "message": f"Found {len(filings)} filings for {ticker}",
                "filings": filings
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error listing filings: {e}",
            }

    def list_items(accession_number: str) -> dict[str, Any]:
        """
        List all items for a given accession number from Firebase Storage.
        """
        try:
            files = storage.list_files(ticker, accession_number, "items/")
            items = [f for f in files if f.endswith(".txt")]
            # Remove "items/" prefix and keep just the filename
            items = [item.replace("items/", "") for item in items]
            
            if not items:
                return {
                    "status": "error",
                    "message": f"No items processed for {accession_number}",
                }
            
            return {
                "status": "success",
                "message": f"Found {len(items)} items for {accession_number}",
                "items": sorted(items)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error listing items: {e}",
            }
    
    def list_statements(accession_number: str) -> dict[str, Any]:
        """
        List all statements for a given accession number from Firebase Storage.
        """
        try:
            files = storage.list_files(ticker, accession_number, "statements/")
            statements = [f for f in files if f.endswith(".md")]
            # Remove "statements/" prefix and keep just the filename
            statements = [stmt.replace("statements/", "") for stmt in statements]
            
            if not statements:
                return {
                    "status": "error",
                    "message": f"No statements processed for {accession_number}",
                }
            
            return {
                "status": "success",
                "message": f"Found {len(statements)} statements for {accession_number}",
                "statements": sorted(statements)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error listing statements: {e}",
            }
    
    def read_item(accession_number: str, item_name: str) -> dict[str, Any]:
        """
        Read a specific item from an SEC filing in Firebase Storage.
        
        Args:
            accession_number: The filing's accession number (e.g., "0000320193-23-000106")
            item_name: The item name (e.g., "Item 1", "Item 7", "Item 7A")
            
        Returns the full text content of the item.
        
        Use `list_items` to identify available items in the filing.
        """
        try:
            file_path = f"items/{item_name}.txt"
            content = storage.download_file_text(ticker, accession_number, file_path)
            if content is None:
                return {
                    "status": "error",
                    "message": f"Item '{item_name}' not found in filing {accession_number}"
                }
            return {
                "status": "success",
                "message": content
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error reading item: {e}",
            }
    
    def read_statement(accession_number: str, statement_name: str) -> dict[str, Any]:
        """
        Read a specific financial statement from an SEC filing in Firebase Storage.
        
        Args:
            accession_number: The filing's accession number (e.g., "0000320193-23-000106")
            statement_name: The statement name (e.g., "CONSOLIDATEDBALANCESHEETS")
            
        Returns the markdown content of the financial statement.
        """
        try:
            file_path = f"statements/{statement_name}.md"
            content = storage.download_file_text(ticker, accession_number, file_path)
            if content is None:
                return {
                    "status": "error",
                    "message": f"Statement '{statement_name}' not found in filing {accession_number}"
                }
            return {
                "status": "success",
                "message": content
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error reading statement: {e}",
            }
        
    
    # Create FunctionTool instances
    tools = [
        FunctionTool(list_filings),
        FunctionTool(list_items),
        FunctionTool(list_statements),
        FunctionTool(read_item),
        FunctionTool(read_statement),
        FunctionTool(get_filing_metadata),
    ]
    
    return tools


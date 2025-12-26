"""
SEC Filing Tools for the Stock Analysis Agent.

These tools provide access to locally downloaded SEC filings for a specific ticker.
All tools are scoped to a single ticker and only access files under companies/{ticker}/sec_edgar/.
"""

import json
from pathlib import Path
from typing import Any

from google.adk.tools import FunctionTool


def create_filing_tools(ticker: str, companies_dir: Path) -> list[FunctionTool]:
    """
    Create a set of filing tools scoped to a specific ticker.
    
    Args:
        ticker: The stock ticker symbol (e.g., "AAPL")
        companies_dir: Base path to the companies directory
        
    Returns:
        List of FunctionTool instances for the agent
    """
    ticker = ticker.upper()
    filings_dir = companies_dir / ticker / "sec_edgar"

    def get_filing_dir(accession_number: str) -> Path:
        return filings_dir / accession_number
    
    def get_item_dir(accession_number: str) -> Path:
        return get_filing_dir(accession_number) / "items"

    def get_statement_dir(accession_number: str) -> Path:
        return get_filing_dir(accession_number) / "statements"
    
    def get_filing_metadata(accession_number: str) -> dict[str, Any]:
        filing_dir = get_filing_dir(accession_number)
        metadata_file = filing_dir / "filing.json"
        if metadata_file.exists():
            return json.loads(metadata_file.read_text())
        return None
        
    def list_filings() -> dict[str, Any]:
        """
        List all available SEC filings for the ticker.
        
        Returns a list of filings with their accession numbers, form types, and dates.
        Use this to discover what filings are available before reading specific items.
        """
        if not filings_dir.exists():
            return {
                "status": "error",
                "message": f"No filings found for {ticker}. Run download_sec_data.py first.",
            }
        
        filings = []
        for filing_dir in sorted(filings_dir.iterdir(), reverse=True):
            if filing_dir.is_dir() and not filing_dir.name.startswith("."):
                metadata = get_filing_metadata(filing_dir.name)
                if metadata:
                    filings.append(metadata)
        
        return {
            "status": "success",
            "message": f"Found {len(filings)} filings for {ticker}",
            "filings": filings
        }

    def list_items(accession_number: str) -> dict[str, Any]:
        """
        List all items for a given accession number.
        """
        items_dir = get_item_dir(accession_number)
        if not items_dir.exists():
            return {
                "status": "error",
                "message": f"No items processed for {accession_number}",
            }
        items = []
        for item_file in sorted(items_dir.iterdir()):
            if item_file.is_file() and item_file.suffix == ".txt":
                items.append(item_file.name)

        return {
            "status": "success",
            "message": f"Found {len(items)} items for {accession_number}",
            "items": items
        }
    
    def list_statements(accession_number: str) -> dict[str, Any]:
        """
        List all statements for a given accession number.
        """
        statements_dir = get_statement_dir(accession_number)
        if not statements_dir.exists():
            return {
                "status": "error",
                "message": f"No statements processed for {accession_number}",
            }
        statements = []
        for statement_file in sorted(statements_dir.iterdir()):
            if statement_file.is_file() and statement_file.suffix == ".md":
                statements.append(statement_file.name)
        return {
            "status": "success",
            "message": f"Found {len(statements)} statements for {accession_number}",
            "statements": statements
        }
    
    def read_item(accession_number: str, item_name: str) -> dict[str, Any]:
        """
        Read a specific item from an SEC filing.
        
        Args:
            accession_number: The filing's accession number (e.g., "0000320193-23-000106")
            item_name: The item name (e.g., "Item 1", "Item 7", "Item 7A")
            
        Returns the full text content of the item.
        
        Use `list_items` to identify available items in the filing.
        """
        item_file = get_item_dir(accession_number) / f"{item_name}.txt"
        if not item_file.exists():
            return {
                "status": "error",
                "message": f"Item '{item_name}' not found in filing {accession_number}"
            }
        return {
            "status": "success",
            "message": item_file.read_text(encoding="utf-8")
        }
    
    def read_statement(accession_number: str, statement_name: str) -> dict[str, Any]:
        """
        Read a specific financial statement from an SEC filing.
        
        Args:
            accession_number: The filing's accession number (e.g., "0000320193-23-000106")
            statement_name: The statement name (e.g., "CONSOLIDATEDBALANCESHEETS")
            
        Returns the markdown content of the financial statement.
        """
        filing_dir = get_filing_dir(accession_number)
        statements_dir = filing_dir / "statements"
        statement_file = statements_dir / f"{statement_name}.md"
        
        if not statement_file.exists():
            return {
                "status": "error",
                "message": f"Statement '{statement_name}' not found in filing {accession_number}"
            }
        return {
            "status": "success",
            "message": statement_file.read_text(encoding="utf-8")
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


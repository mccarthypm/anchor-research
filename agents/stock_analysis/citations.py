"""
Citation System for the Stock Analysis Agent.

Provides tools and data structures for storing, verifying, and managing
citations from SEC filings to ensure accurate source attribution.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from google.adk.tools import FunctionTool


@dataclass
class Citation:
    """
    Represents a citation from an SEC filing.
    
    Citations store exact verbatim quotes or numbers with full source attribution
    to enable verification and proper referencing in final answers.
    """
    id: str                     # Unique citation ID (e.g., "cite-001")
    content: str                # Exact verbatim quote or number
    source_file: str            # Full path to source file
    source_filing: str          # Accession number
    source_item: str            # Item name (e.g., "Item 7") or statement name
    filing_date: str            # Date of the filing
    context: str                # Surrounding text for verification
    start_line: int | None = None  # Starting line number in source file
    end_line: int | None = None    # Ending line number in source file
    verified: bool = False      # Whether citation has been verified
    
    def to_dict(self) -> dict[str, Any]:
        """Convert citation to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        """Create citation from dictionary."""
        return cls(**data)
    
    def format_line_reference(self) -> str:
        """Format the line number reference for display."""
        if self.start_line is None:
            return ""
        if self.end_line is None or self.start_line == self.end_line:
            return f"line {self.start_line}"
        return f"lines {self.start_line}-{self.end_line}"


class CitationStore:
    """
    Manages a collection of citations for a research session.
    
    Provides methods for adding, retrieving, verifying, and formatting citations.
    """
    
    def __init__(self):
        self._citations: dict[str, Citation] = {}
        self._counter: int = 0
    
    def _generate_id(self) -> str:
        """Generate a unique citation ID."""
        self._counter += 1
        return f"cite-{self._counter:03d}"
    
    def add(
        self,
        content: str,
        source_file: str,
        source_filing: str,
        source_item: str,
        filing_date: str,
        context: str,
        start_line: int | None = None,
        end_line: int | None = None
    ) -> Citation:
        """
        Add a new citation to the store.
        
        Args:
            content: Exact verbatim quote or number
            source_file: Full path to source file
            source_filing: Accession number
            source_item: Item name or statement name
            filing_date: Date of the filing
            context: Surrounding text for verification
            start_line: Starting line number in source file
            end_line: Ending line number in source file
            
        Returns:
            The created Citation object
        """
        citation_id = self._generate_id()
        citation = Citation(
            id=citation_id,
            content=content,
            source_file=source_file,
            source_filing=source_filing,
            source_item=source_item,
            filing_date=filing_date,
            context=context,
            start_line=start_line,
            end_line=end_line,
            verified=False
        )
        self._citations[citation_id] = citation
        return citation
    
    def get(self, citation_id: str) -> Citation | None:
        """Get a citation by ID."""
        return self._citations.get(citation_id)
    
    def get_all(self) -> list[Citation]:
        """Get all citations."""
        return list(self._citations.values())
    
    def get_unverified(self) -> list[Citation]:
        """Get all unverified citations."""
        return [c for c in self._citations.values() if not c.verified]
    
    def mark_verified(self, citation_id: str, verified: bool = True) -> bool:
        """
        Mark a citation as verified or unverified.
        
        Returns True if citation was found and updated.
        """
        if citation_id in self._citations:
            self._citations[citation_id].verified = verified
            return True
        return False
    
    def update_content(self, citation_id: str, new_content: str) -> bool:
        """
        Update the content of a citation (e.g., after verification finds a discrepancy).
        
        Returns True if citation was found and updated.
        """
        if citation_id in self._citations:
            self._citations[citation_id].content = new_content
            return True
        return False
    
    def format_sources_section(self) -> str:
        """
        Format all citations as a sources section for the final answer.
        
        Returns a formatted string like:
        ---
        Sources:
        [1] 10-K (2023-11-03), Item 7, lines 45-47
        [2] 10-K (2023-11-03), Item 1A, line 12
        """
        if not self._citations:
            return ""
        
        lines = ["---", "Sources:"]
        for i, citation in enumerate(self._citations.values(), 1):
            source_desc = f"{citation.source_item}"
            line_ref = citation.format_line_reference()
            if line_ref:
                source_desc += f", {line_ref}"
            lines.append(f"[{i}] {citation.source_filing} ({citation.filing_date}), {source_desc}")
        
        return "\n".join(lines)
    
    def get_citation_number(self, citation_id: str) -> int | None:
        """Get the display number for a citation (1-indexed)."""
        for i, cid in enumerate(self._citations.keys(), 1):
            if cid == citation_id:
                return i
        return None
    
    def clear(self):
        """Clear all citations."""
        self._citations.clear()
        self._counter = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize the citation store to a dictionary."""
        return {
            "citations": {cid: c.to_dict() for cid, c in self._citations.items()},
            "counter": self._counter
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CitationStore":
        """Deserialize a citation store from a dictionary."""
        store = cls()
        store._counter = data.get("counter", 0)
        for cid, cdata in data.get("citations", {}).items():
            store._citations[cid] = Citation.from_dict(cdata)
        return store


def create_citation_tools(citation_store: CitationStore, companies_dir: Path, ticker: str) -> list[FunctionTool]:
    """
    Create citation management tools for the agent.
    
    Args:
        citation_store: The CitationStore instance to use
        companies_dir: Base path to the companies directory
        ticker: The stock ticker symbol
        
    Returns:
        List of FunctionTool instances for citation management
    """
    ticker = ticker.upper()
    ticker_dir = companies_dir / ticker / "sec_edgar"
    
    def _find_line_numbers(file_path: str, content: str) -> tuple[int | None, int | None]:
        """Find the line numbers where content appears in a file."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None, None
            
            lines = path.read_text(encoding="utf-8").splitlines()
            full_text = "\n".join(lines)
            
            # Try to find the content in the file
            # First, try exact match on a single line
            for i, line in enumerate(lines, 1):
                if content in line:
                    return i, i
            
            # If not found on a single line, try multi-line match
            if content in full_text:
                # Find the starting position
                start_pos = full_text.find(content)
                end_pos = start_pos + len(content)
                
                # Count newlines to find line numbers
                start_line = full_text[:start_pos].count("\n") + 1
                end_line = full_text[:end_pos].count("\n") + 1
                
                return start_line, end_line
            
            # Try partial match: extract key numbers/words and find them
            # This helps when agent slightly reformats the content
            import re
            # Extract numbers from the content
            numbers = re.findall(r'\d[\d,\.]+', content)
            if numbers:
                # Find the first significant number (at least 3 digits)
                for num in numbers:
                    clean_num = num.replace(',', '').replace('.', '')
                    if len(clean_num) >= 3:
                        for i, line in enumerate(lines, 1):
                            if num in line or num.replace(',', '') in line:
                                return i, i
            
            # Try finding first few words
            words = content.split()[:5]
            if len(words) >= 3:
                search_phrase = " ".join(words)
                for i, line in enumerate(lines, 1):
                    if search_phrase.lower() in line.lower():
                        return i, i
            
            return None, None
        except Exception:
            return None, None
    
    def save_citation(
        content: str,
        source_filing: str,
        source_item: str,
        context: str
    ) -> dict[str, Any]:
        """
        Save an exact quote or data point with its source location for later citation.
        
        Use this when you find relevant data that should be cited in your final answer.
        Always save the EXACT verbatim text - do not paraphrase or modify.
        
        Args:
            content: The exact verbatim quote or number from the source
            source_filing: The accession number of the filing (e.g., "0000320193-23-000106")
            source_item: The item or statement name (e.g., "Item 7", "CONSOLIDATEDBALANCESHEETS")
            context: Surrounding text (a paragraph or so) to help with verification
            
        Returns:
            The created citation with its ID for reference, including line numbers
        """
        # Determine the source file path
        filing_dir = ticker_dir / source_filing
        
        # Check if it's an item or statement
        item_file = filing_dir / "items" / f"{source_item}.txt"
        statement_file = filing_dir / "statements" / f"{source_item}.md"
        
        if item_file.exists():
            source_file = str(item_file)
        elif statement_file.exists():
            source_file = str(statement_file)
        else:
            source_file = f"{filing_dir}/{source_item}"
        
        # Get filing date from metadata
        filing_date = "Unknown"
        metadata_file = filing_dir / "filing.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
                filing_date = metadata.get("filing_date", "Unknown")
            except json.JSONDecodeError:
                pass
        
        # Find line numbers for the citation
        start_line, end_line = _find_line_numbers(source_file, content)
        
        citation = citation_store.add(
            content=content,
            source_file=source_file,
            source_filing=source_filing,
            source_item=source_item,
            filing_date=filing_date,
            context=context,
            start_line=start_line,
            end_line=end_line
        )
        
        line_info = ""
        if start_line:
            if end_line and end_line != start_line:
                line_info = f" (lines {start_line}-{end_line})"
            else:
                line_info = f" (line {start_line})"
        
        return {
            "success": True,
            "citation_id": citation.id,
            "message": f"Citation saved{line_info}. Use [{citation_store.get_citation_number(citation.id)}] to reference this in your answer.",
            "citation": citation.to_dict()
        }
    
    def verify_citation(citation_id: str) -> dict[str, Any]:
        """
        Verify a citation by checking the source document at the stored line numbers.
        
        Uses the line numbers saved when the citation was created for efficient
        verification. Falls back to full-text search if line numbers aren't available.
        
        Args:
            citation_id: The citation ID to verify (e.g., "cite-001")
            
        Returns:
            Verification result including whether the content was found verbatim
        """
        citation = citation_store.get(citation_id)
        if not citation:
            return {
                "success": False,
                "error": f"Citation {citation_id} not found"
            }
        
        source_path = Path(citation.source_file)
        if not source_path.exists():
            return {
                "success": False,
                "error": f"Source file not found: {citation.source_file}",
                "citation_id": citation_id
            }
        
        try:
            lines = source_path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            return {
                "success": False,
                "error": f"Could not read source file: {e}",
                "citation_id": citation_id
            }
        
        content_found = False
        actual_line_content = None
        
        # If we have line numbers, check those lines first (efficient path)
        if citation.start_line is not None:
            start_idx = citation.start_line - 1  # Convert to 0-indexed
            end_idx = (citation.end_line or citation.start_line)
            
            # Get the relevant lines
            if 0 <= start_idx < len(lines):
                relevant_lines = lines[start_idx:end_idx]
                relevant_text = "\n".join(relevant_lines)
                actual_line_content = relevant_text
                
                # Check if citation content is in the relevant lines
                if citation.content in relevant_text:
                    content_found = True
        
        # Fall back to full-text search if not found at line numbers
        if not content_found:
            full_text = "\n".join(lines)
            content_found = citation.content in full_text
        
        # Also check if context matches (for additional verification)
        full_text = "\n".join(lines)
        context_found = citation.context in full_text if citation.context else True
        
        if content_found:
            citation_store.mark_verified(citation_id, True)
            line_ref = citation.format_line_reference()
            return {
                "success": True,
                "verified": True,
                "citation_id": citation_id,
                "message": f"Citation verified - content found verbatim in source{' at ' + line_ref if line_ref else ''}",
                "content_match": True,
                "context_match": context_found,
                "line_reference": line_ref or None
            }
        else:
            # Try to find similar content for correction
            # Look for the first few words of the content
            words = citation.content.split()[:5]
            search_prefix = " ".join(words)
            
            suggestion = None
            if search_prefix in full_text:
                # Find the full sentence/paragraph containing the prefix
                start_idx = full_text.find(search_prefix)
                # Get surrounding context (up to 500 chars)
                context_start = max(0, start_idx - 50)
                context_end = min(len(full_text), start_idx + len(citation.content) + 200)
                suggestion = full_text[context_start:context_end].strip()
            
            return {
                "success": True,
                "verified": False,
                "citation_id": citation_id,
                "message": "Citation NOT verified - content not found verbatim",
                "content_match": False,
                "context_match": context_found,
                "cited_content": citation.content,
                "suggestion": suggestion,
                "action_required": "Re-read the source and update the citation with exact verbatim text"
            }
    
    def list_citations() -> dict[str, Any]:
        """
        List all saved citations for the current analysis.
        
        Use this to see what citations you've collected and their verification status.
        Before generating your final answer, ensure all citations are verified.
        
        Returns:
            List of all citations with their details, line numbers, and verification status
        """
        citations = citation_store.get_all()
        unverified_count = len(citation_store.get_unverified())
        
        return {
            "total_citations": len(citations),
            "verified_count": len(citations) - unverified_count,
            "unverified_count": unverified_count,
            "all_verified": unverified_count == 0,
            "citations": [
                {
                    "number": i,
                    "id": c.id,
                    "content_preview": c.content[:100] + "..." if len(c.content) > 100 else c.content,
                    "source": f"{c.source_filing}, {c.source_item}",
                    "lines": c.format_line_reference() or "unknown",
                    "filing_date": c.filing_date,
                    "verified": c.verified
                }
                for i, c in enumerate(citations, 1)
            ],
            "sources_section": citation_store.format_sources_section() if citations else None
        }
    
    def update_citation(citation_id: str, new_content: str) -> dict[str, Any]:
        """
        Update a citation's content after finding a discrepancy during verification.
        
        Use this when verify_citation shows the content doesn't match the source.
        Replace with the exact verbatim text from the source document.
        
        Args:
            citation_id: The citation ID to update
            new_content: The corrected exact verbatim content
            
        Returns:
            Result of the update operation
        """
        citation = citation_store.get(citation_id)
        if not citation:
            return {
                "success": False,
                "error": f"Citation {citation_id} not found"
            }
        
        old_content = citation.content
        citation_store.update_content(citation_id, new_content)
        # Mark as unverified since content changed
        citation_store.mark_verified(citation_id, False)
        
        return {
            "success": True,
            "citation_id": citation_id,
            "message": "Citation updated. Please verify again.",
            "old_content": old_content[:100] + "..." if len(old_content) > 100 else old_content,
            "new_content": new_content[:100] + "..." if len(new_content) > 100 else new_content
        }
    
    tools = [
        FunctionTool(save_citation),
        FunctionTool(verify_citation),
        FunctionTool(list_citations),
        FunctionTool(update_citation),
    ]
    
    return tools


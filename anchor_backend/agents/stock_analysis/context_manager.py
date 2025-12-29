"""
Context Manager for the Stock Analysis Agent.

Provides context compaction and management to keep the agent's context window
focused on relevant information while maintaining the ability to re-read
documents if they become relevant.
"""

from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

from google.adk.tools import FunctionTool


@dataclass
class DocumentSummary:
    """
    Summary of a document that has been compacted.
    
    When a document is compacted, its full content is removed from context
    but this summary is retained to track what was read and key findings.
    """
    accession_number: str
    document_type: str  # "item" or "statement"
    document_name: str  # e.g., "Item 7" or "CONSOLIDATEDBALANCESHEETS"
    filing_date: str
    source_file: str
    summary: str  # Key findings summary
    citation_ids: list[str] = field(default_factory=list)  # Citations extracted from this doc
    relevance_score: float = 0.0  # How relevant to the current question (0-1)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accession_number": self.accession_number,
            "document_type": self.document_type,
            "document_name": self.document_name,
            "filing_date": self.filing_date,
            "source_file": self.source_file,
            "summary": self.summary,
            "citation_ids": self.citation_ids,
            "relevance_score": self.relevance_score
        }


class ContextManager:
    """
    Manages the agent's context window by tracking documents read and
    providing compaction capabilities.
    
    Strategy:
    1. Track all documents that have been read
    2. Maintain full content for recent/relevant documents
    3. Compact older documents to summaries
    4. Preserve citations in full (they are never compacted)
    5. Allow re-reading of any compacted document if needed
    """
    
    def __init__(self, max_full_docs: int = 3):
        """
        Initialize the context manager.
        
        Args:
            max_full_docs: Maximum number of documents to keep in full context
        """
        self.max_full_docs = max_full_docs
        self._document_summaries: dict[str, DocumentSummary] = {}
        self._full_context_docs: list[str] = []  # Keys of docs currently in full context
        self._documents_read_count: int = 0
    
    @property
    def documents_read_count(self) -> int:
        """Total number of documents read in this session."""
        return self._documents_read_count
    
    def record_document_read(
        self,
        accession_number: str,
        document_type: str,
        document_name: str,
        filing_date: str,
        source_file: str
    ) -> str:
        """
        Record that a document has been read.
        
        Args:
            accession_number: The filing's accession number
            document_type: "item" or "statement"
            document_name: The document name (e.g., "Item 7")
            filing_date: The filing date
            source_file: Path to the source file
            
        Returns:
            A unique key for this document
        """
        key = f"{accession_number}/{document_type}/{document_name}"
        
        if key not in self._document_summaries:
            self._documents_read_count += 1
            self._document_summaries[key] = DocumentSummary(
                accession_number=accession_number,
                document_type=document_type,
                document_name=document_name,
                filing_date=filing_date,
                source_file=source_file,
                summary="",
                citation_ids=[],
                relevance_score=0.5  # Default relevance
            )
            self._full_context_docs.append(key)
        
        return key
    
    def add_summary(self, doc_key: str, summary: str, relevance_score: float = 0.5):
        """
        Add or update the summary for a document.
        
        Args:
            doc_key: The document key from record_document_read
            summary: Key findings summary
            relevance_score: How relevant to the current question (0-1)
        """
        if doc_key in self._document_summaries:
            self._document_summaries[doc_key].summary = summary
            self._document_summaries[doc_key].relevance_score = relevance_score
    
    def link_citation(self, doc_key: str, citation_id: str):
        """
        Link a citation to the document it came from.
        
        Args:
            doc_key: The document key
            citation_id: The citation ID
        """
        if doc_key in self._document_summaries:
            if citation_id not in self._document_summaries[doc_key].citation_ids:
                self._document_summaries[doc_key].citation_ids.append(citation_id)
    
    def get_documents_needing_compaction(self) -> list[str]:
        """
        Get list of document keys that should be compacted.
        
        Returns documents that are in full context but exceed the max limit,
        prioritizing compaction of lower relevance documents.
        """
        if len(self._full_context_docs) <= self.max_full_docs:
            return []
        
        # Sort by relevance (lowest first) to compact least relevant
        docs_with_scores = [
            (key, self._document_summaries[key].relevance_score)
            for key in self._full_context_docs
            if key in self._document_summaries
        ]
        docs_with_scores.sort(key=lambda x: x[1])
        
        # Return the least relevant documents that exceed the limit
        num_to_compact = len(self._full_context_docs) - self.max_full_docs
        return [key for key, _ in docs_with_scores[:num_to_compact]]
    
    def mark_compacted(self, doc_key: str):
        """Mark a document as compacted (no longer in full context)."""
        if doc_key in self._full_context_docs:
            self._full_context_docs.remove(doc_key)
    
    def get_research_status(self) -> dict[str, Any]:
        """
        Get the current research status for display to the agent.
        
        Returns summary of documents read, what's in full context,
        and what has been compacted.
        """
        all_docs = list(self._document_summaries.values())
        full_context = [
            self._document_summaries[key].to_dict()
            for key in self._full_context_docs
            if key in self._document_summaries
        ]
        compacted = [
            doc.to_dict()
            for key, doc in self._document_summaries.items()
            if key not in self._full_context_docs
        ]
        
        return {
            "total_documents_read": self._documents_read_count,
            "documents_in_full_context": len(full_context),
            "documents_compacted": len(compacted),
            "full_context_docs": full_context,
            "compacted_docs": compacted,
            "should_check_in": self._documents_read_count >= 10 and self._documents_read_count % 10 == 0
        }
    
    def get_document_index(self) -> list[dict[str, Any]]:
        """
        Get an index of all documents read for reference.
        
        This helps the agent know what's available for re-reading.
        """
        return [
            {
                "key": key,
                "accession_number": doc.accession_number,
                "document": f"{doc.document_type}: {doc.document_name}",
                "filing_date": doc.filing_date,
                "in_full_context": key in self._full_context_docs,
                "has_summary": bool(doc.summary),
                "citation_count": len(doc.citation_ids),
                "relevance_score": doc.relevance_score
            }
            for key, doc in self._document_summaries.items()
        ]
    
    def clear(self):
        """Clear all tracked documents."""
        self._document_summaries.clear()
        self._full_context_docs.clear()
        self._documents_read_count = 0


def create_context_tools(context_manager: ContextManager) -> list[FunctionTool]:
    """
    Create context management tools for the agent.
    
    Args:
        context_manager: The ContextManager instance to use
        
    Returns:
        List of FunctionTool instances for context management
    """
    
    def get_research_status() -> dict[str, Any]:
        """
        Get the current status of your research.
        
        Shows how many documents you've read, what's in full context,
        and what has been compacted to summaries. Use this to track
        your progress and decide when to check in with the user.
        
        After reading 10 documents, you should check in with the user
        if you still don't have a compelling answer.
        """
        return context_manager.get_research_status()
    
    def get_document_index() -> dict[str, Any]:
        """
        Get an index of all documents you've read.
        
        Use this to see what documents are available for re-reading
        and which ones have been compacted. You can re-read any
        compacted document if it becomes relevant again.
        """
        return {
            "documents": context_manager.get_document_index(),
            "total": context_manager.documents_read_count
        }
    
    def record_document_summary(
        doc_key: str,
        summary: str,
        relevance_score: float
    ) -> dict[str, Any]:
        """
        Record a summary of key findings from a document you just read.
        
        Use this after reading each document to capture the key insights
        relevant to the user's question. This helps with context compaction -
        when a document is compacted, only this summary is retained.
        
        Args:
            doc_key: The document key (format: "accession/type/name")
            summary: Key findings relevant to the user's question
            relevance_score: How relevant this document is (0.0 to 1.0)
            
        Returns:
            Confirmation of the summary being recorded
        """
        context_manager.add_summary(doc_key, summary, relevance_score)
        
        # Check if compaction is needed
        docs_to_compact = context_manager.get_documents_needing_compaction()
        
        return {
            "success": True,
            "doc_key": doc_key,
            "summary_recorded": True,
            "compaction_needed": len(docs_to_compact) > 0,
            "docs_to_compact": docs_to_compact if docs_to_compact else None,
            "message": "Summary recorded. " + (
                f"Consider compacting {len(docs_to_compact)} document(s) to manage context."
                if docs_to_compact else "Context is within limits."
            )
        }
    
    def compact_document(doc_key: str) -> dict[str, Any]:
        """
        Compact a document, removing its full content from context.
        
        After compaction, only the summary is retained. The document
        can be re-read if it becomes relevant again.
        
        IMPORTANT: Before compacting, ensure you have:
        1. Saved any important citations using save_citation
        2. Recorded a summary using record_document_summary
        
        Args:
            doc_key: The document key to compact
            
        Returns:
            Confirmation of compaction
        """
        context_manager.mark_compacted(doc_key)
        
        return {
            "success": True,
            "doc_key": doc_key,
            "message": "Document compacted. Summary retained. Can be re-read if needed."
        }
    
    tools = [
        FunctionTool(get_research_status),
        FunctionTool(get_document_index),
        FunctionTool(record_document_summary),
        FunctionTool(compact_document),
    ]
    
    return tools


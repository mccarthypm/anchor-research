"""
Stock Analysis Agent.

An AI agent that analyzes SEC filings to craft investment theses
for specific stock tickers using Google's ADK with Claude via LiteLLM.
"""

import json
import os
from pathlib import Path
from typing import Any

# Disable LiteLLM's background logging to avoid event loop conflicts
os.environ.setdefault("LITELLM_LOG", "ERROR")

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.stock_analysis.tools import create_filing_tools
from agents.stock_analysis.citations import CitationStore, create_citation_tools
from agents.stock_analysis.context_manager import ContextManager, create_context_tools
from agents.stock_analysis.prompts import get_system_prompt

# Default Claude model
DEFAULT_MODEL = "anthropic/claude-sonnet-4-5-20250929"


class StockAnalysisAgent:
    """
    An agent that analyzes SEC filings for a specific stock ticker.
    
    The agent uses a research loop to:
    1. Understand the user's question
    2. Create an analysis plan
    3. Read documents iteratively
    4. Save and verify citations
    5. Generate well-sourced answers
    
    Example:
        agent = StockAnalysisAgent("AAPL")
        agent.run()  # Starts interactive loop
    """
    
    def __init__(
        self,
        ticker: str,
        companies_dir: Path | str = "companies",
        model: str | None = None,
        max_full_docs: int = 3
    ):
        """
        Initialize the Stock Analysis Agent.
        
        Args:
            ticker: The stock ticker symbol (e.g., "AAPL", "MSFT")
            companies_dir: Path to the companies directory
            model: The model to use (default: Claude Sonnet via LiteLLM)
                   Format: "anthropic/claude-sonnet-4-20250514" or other LiteLLM models
            max_full_docs: Maximum documents to keep in full context
        """
        self.ticker = ticker.upper()
        self.companies_dir = Path(companies_dir) if companies_dir else None
        self.model = model or DEFAULT_MODEL
        
        # Verify ticker has filings in Firebase Storage
        from sources.firebase_storage import FirebaseStorageService
        try:
            accessions = FirebaseStorageService.list_filings(self.ticker)
            if not accessions:
                raise ValueError(
                    f"No filings found for {self.ticker} in Firebase Storage. "
                    f"Run 'uv run download_sec_data.py {self.ticker}' first."
                )
        except Exception as e:
            raise ValueError(
                f"Error checking Firebase Storage for {self.ticker}: {e}. "
                f"Ensure Firebase is properly configured."
            )
        
        # Get company name from most recent filing
        self.company_name = self._get_company_name()
        
        # Initialize stores
        self.citation_store = CitationStore()
        self.context_manager = ContextManager(max_full_docs=max_full_docs)
        
        # Create tools (companies_dir is deprecated but kept for compatibility)
        self.filing_tools = create_filing_tools(self.ticker, self.companies_dir)
        self.citation_tools = create_citation_tools(
            self.citation_store, self.companies_dir, self.ticker
        )
        self.context_tools = create_context_tools(self.context_manager)
        
        # Combine all tools
        self.all_tools = self.filing_tools + self.citation_tools + self.context_tools
        
        # Create LiteLLM model wrapper for Claude
        litellm_model = LiteLlm(model=self.model)
        
        # Create the ADK agent with LiteLLM
        self.agent = Agent(
            model=litellm_model,
            name="stock_analysis_agent",
            instruction=get_system_prompt(self.ticker, self.company_name),
            tools=self.all_tools,
        )
        
        # Session management
        self.session_service = InMemorySessionService()
        self.session_id: str | None = None
        self.runner: Runner | None = None
    
    def _get_company_name(self) -> str:
        """Get the company name from the most recent filing metadata in Firebase Storage."""
        from sources.firebase_storage import FirebaseStorageService
        try:
            accessions = FirebaseStorageService.list_filings(self.ticker)
            # Sort in reverse to get most recent first
            for accession_number in sorted(accessions, reverse=True):
                metadata_json = FirebaseStorageService.download_file_text(
                    self.ticker, accession_number, "filing.json"
                )
                if metadata_json:
                    try:
                        metadata = json.loads(metadata_json)
                        return metadata.get("company", self.ticker)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return self.ticker
    
    async def _create_session_async(self) -> str:
        """Create a new session and return the session ID (async)."""
        session = await self.session_service.create_session(
            app_name="stock_analysis",
            user_id="user",
        )
        return session.id
    
    async def start_session_async(self) -> str:
        """
        Start a new analysis session (async).
        
        Returns:
            The session ID
        """
        # Clear previous state
        self.citation_store.clear()
        self.context_manager.clear()
        
        # Create new session
        self.session_id = await self._create_session_async()
        
        # Create runner
        self.runner = Runner(
            agent=self.agent,
            app_name="stock_analysis",
            session_service=self.session_service,
        )
        
        return self.session_id
    
    def start_session(self) -> str:
        """
        Start a new analysis session (sync wrapper).
        
        Returns:
            The session ID
        """
        import asyncio
        return asyncio.run(self.start_session_async())
    
    async def chat_async(self, message: str) -> str:
        """
        Send a message to the agent and get a response (async).
        
        Args:
            message: The user's message/question
            
        Returns:
            The agent's final response (excluding chain-of-thought reasoning)
        """
        if not self.runner or not self.session_id:
            await self.start_session_async()
        
        # Create the user message
        user_content = types.Content(
            role="user",
            parts=[types.Part(text=message)]
        )
        
        # Run the agent and collect only the final response
        final_response = ""
        async for event in self.runner.run_async(
            user_id="user",
            session_id=self.session_id,
            new_message=user_content,
        ):
            if getattr(event, 'is_final_response', False):
                content = getattr(event, 'content', None)
                if content:
                    for part in content.parts:
                        text = getattr(part, 'text', None)
                        if text:
                            final_response = text
        
        return final_response
    
    def chat(self, message: str) -> str:
        """
        Send a message to the agent and get a response (sync wrapper).
        
        Args:
            message: The user's message/question
            
        Returns:
            The agent's response
        """
        import asyncio
        
        # Use asyncio.run() which properly manages the event loop lifecycle
        # The LITELLM_DISABLE_LOGGING env var prevents the logging worker conflicts
        return asyncio.run(self.chat_async(message))
    
    async def run_async(self):
        """
        Run the agent in an interactive loop (async).
        
        Starts a session and continuously prompts for user input
        until the user types 'quit' or 'exit'.
        """
        print(f"\n{'='*60}")
        print(f"Stock Analysis Agent - {self.company_name} ({self.ticker})")
        print(f"{'='*60}")
        print(f"\nI can help you analyze SEC filings for {self.company_name}.")
        print("Ask me questions about the company's financials, risks, business, etc.")
        print("Type 'quit' or 'exit' to end the session.\n")
        
        await self.start_session_async()
        
        import asyncio
        loop = asyncio.get_running_loop()
        
        while True:
            try:
                # Use run_in_executor to avoid blocking the event loop on input()
                user_input = await loop.run_in_executor(None, input, "You: ")
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ('quit', 'exit', 'q'):
                    print("\nEnding session. Goodbye!")
                    break
                
                print("\nAnalyzing...\n")
                response = await self.chat_async(user_input)
                print(f"Agent: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nSession interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")

    def run(self):
        """
        Run the agent in an interactive loop.
        
        Starts a session and continuously prompts for user input
        until the user types 'quit' or 'exit'.
        """
        import asyncio
        asyncio.run(self.run_async())
    
    def get_session_summary(self) -> dict[str, Any]:
        """
        Get a summary of the current session.
        
        Returns:
            Dictionary with session statistics
        """
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "session_id": self.session_id,
            "documents_read": self.context_manager.documents_read_count,
            "citations_saved": len(self.citation_store.get_all()),
            "citations_verified": len([c for c in self.citation_store.get_all() if c.verified]),
            "research_status": self.context_manager.get_research_status()
        }


#!/usr/bin/env python3
"""
CLI entry point for the Stock Analysis Agent.

Usage:
    uv run python run_agent.py TICKER
    uv run python run_agent.py TICKER -q "What are the main risk factors?"
    
Examples:
    uv run python run_agent.py AAPL
    uv run python run_agent.py MSFT -q "What is Microsoft's revenue growth?"
"""

import os

# Disable LiteLLM's async logging worker to avoid event loop conflicts
# Must be set before importing litellm
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_DISABLE_LOGGING"] = "true"

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Default model (Claude Sonnet via LiteLLM)
DEFAULT_MODEL = "anthropic/claude-sonnet-4-5-20250929"


def main():
    """Run the Stock Analysis Agent."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Run the Stock Analysis Agent for a specific ticker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    uv run python run_agent.py AAPL
    
    # Single question mode (non-interactive)
    uv run python run_agent.py AAPL -q "What are Apple's main revenue sources?"
    uv run python run_agent.py MSFT --question "What are the key risk factors?"
        """,
    )
    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)",
    )
    parser.add_argument(
        "--question",
        "-q",
        default=None,
        help="Ask a single question (non-interactive mode)",
    )
    parser.add_argument(
        "--companies-dir",
        "-d",
        default="companies",
        help="Path to the companies directory (default: companies)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help=f"Model to use via LiteLLM (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--max-full-docs",
        type=int,
        default=3,
        help="Maximum documents to keep in full context (default: 3)",
    )
    
    args = parser.parse_args()
    
    # Validate ticker directory exists
    companies_dir = Path(args.companies_dir)
    ticker_dir = companies_dir / args.ticker.upper() / "sec_edgar"
    
    if not ticker_dir.exists():
        print(f"\nError: No filings found for {args.ticker.upper()}")
        print(f"Expected directory: {ticker_dir}")
        print(f"\nTo download filings, run:")
        print(f"  uv run python download_sec_data.py {args.ticker.upper()}")
        sys.exit(1)
    
    # Import here to avoid import errors if dependencies aren't installed
    try:
        from agents.stock_analysis import StockAnalysisAgent
    except ImportError as e:
        print(f"\nError importing agent: {e}")
        print("\nMake sure google-adk is installed:")
        print("  uv add google-adk")
        sys.exit(1)
    
    # Check for API key based on model
    import os
    model = args.model or DEFAULT_MODEL
    
    if model.startswith("anthropic/"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("\nWarning: No Anthropic API key found in environment.")
            print("Set ANTHROPIC_API_KEY to use Claude models.")
            print("\nYou can add it to a .env file:")
            print("  ANTHROPIC_API_KEY=your-api-key-here")
            print()
    elif model.startswith("gemini") or model.startswith("google"):
        if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get("GOOGLE_GENAI_API_KEY"):
            print("\nWarning: No Google API key found in environment.")
            print("Set GOOGLE_API_KEY or GOOGLE_GENAI_API_KEY to use Gemini models.")
            print("\nYou can add it to a .env file:")
            print("  GOOGLE_API_KEY=your-api-key-here")
            print()
    elif model.startswith("openai/") or model.startswith("gpt"):
        if not os.environ.get("OPENAI_API_KEY"):
            print("\nWarning: No OpenAI API key found in environment.")
            print("Set OPENAI_API_KEY to use OpenAI models.")
            print("\nYou can add it to a .env file:")
            print("  OPENAI_API_KEY=your-api-key-here")
            print()
    
    # Create and run the agent
    try:
        agent = StockAnalysisAgent(
            ticker=args.ticker,
            companies_dir=args.companies_dir,
            model=args.model,
            max_full_docs=args.max_full_docs,
        )
        
        import asyncio
        
        async def run_agent():
            if args.question:
                # Non-interactive mode: ask a single question
                print(f"\n{'='*60}")
                print(f"Stock Analysis Agent - {agent.company_name} ({agent.ticker})")
                print(f"{'='*60}")
                print(f"\nQuestion: {args.question}\n")
                print("Analyzing...\n")
                
                response = await agent.chat_async(args.question)
                print(f"{response}\n")
            else:
                # Interactive mode
                await agent.run_async()
        
        asyncio.run(run_agent())
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nSession interrupted. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()


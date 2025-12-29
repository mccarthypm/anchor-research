"""
Command-line interface for SEC filing retrieval.

Usage:
    uv run python -m sources.sec_edgar.cli TICKER
    uv run python -m sources.sec_edgar.cli AAPL --limit 10 --form 10-K
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from sources.sec_edgar.downloader import FilingDownloader


console = Console()


def main():
    """Main entry point for the SEC filing downloader CLI."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Download SEC filings and extract content for a ticker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python -m sources.sec_edgar.cli AAPL
  uv run python -m sources.sec_edgar.cli MSFT --limit 20
  uv run python -m sources.sec_edgar.cli TSLA --form 10-Q
        """,
    )
    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g., AAPL, MSFT, TSLA)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="Limit number of filings to download (default: 20)",
    )
    parser.add_argument(
        "--form",
        "-f",
        default="10-K",
        help="Form type to download (e.g., 10-K, 10-Q)",
    )
    parser.add_argument(
        "--replace-existing",
        "-r",
        action="store_true",
        help="Replace existing filing accession directories",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("companies"),
        help="Output directory for companies (default: companies)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    ticker = args.ticker.upper()
    console.print(f"\n[bold cyan]Processing ticker: {ticker}[/bold cyan]\n")

    # Create downloader with rich console output
    downloader = FilingDownloader(
        base_dir=args.output_dir,
        verbose=True,  # Always verbose for CLI
    )

    # Download filings
    results = downloader.download_filings(
        ticker=ticker,
        form=args.form,
        limit=args.limit,
        replace_existing=args.replace_existing,
    )

    # Print summary
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    console.print(f"\n[bold]Processing Summary:[/bold]")
    console.print(f"  Successful: [green]{successful}[/green]")
    console.print(f"  Failed: [red]{failed}[/red]")
    console.print(f"  Files stored in: {args.output_dir.absolute() / ticker}")

    # Print any errors
    for result in results:
        if not result.success and result.error:
            console.print(f"  [red]Error: {result.error}[/red]")


if __name__ == "__main__":
    main()

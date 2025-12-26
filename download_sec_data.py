"""
Process SEC filings for a ticker symbol.

Downloads 10-K and 10-Q filings, extracts financial statements using XBRL stitching,
and saves the annual balance sheet as a markdown file.

Usage:
    uv run process_ticker.py TICKER

Examples:
    uv run process_ticker.py AAPL
    uv run process_ticker.py MSFT
"""

import argparse
import os
import json
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

from edgar import Company, set_identity


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


console = Console()
load_dotenv()

COMPANIES_DIR = Path("companies")


def download_filing_content(filing, company_dir: Path, replace_existing: bool = False) -> bool:
    """Download a single filing's content"""
    # create the filing directories if they don't exist
    filing_dir = company_dir / filing.accession_number
    filing_items_dir = filing_dir / "items"
    filing_statements_dir = filing_dir / "statements"
    filing_dir.mkdir(parents=True, exist_ok=True)
    filing_items_dir.mkdir(parents=True, exist_ok=True)
    filing_statements_dir.mkdir(parents=True, exist_ok=True)

    # dump the filing to a dictionary and save as a json file
    filing_dict = filing.to_dict()
    filing_dict_file = filing_dir / "filing.json"
    filing_dict_file.write_text(json.dumps(filing_dict, indent=4, default=json_serializer), encoding="utf-8")

    # Get the form-specific object (e.g. 10-K, 10-Q, etc.)
    # Iterate over the items in the object (e.g. item_1.txt, item_2.txt, etc.)
    # save each item as a separate file in the filing directory
    filing_obj = filing.obj()
    if filing_obj and hasattr(filing_obj, 'items') and len(filing_obj.items) > 0:
        for item in filing_obj.items:
            console.print(f"    Processing item: {item}")
            item_file = filing_items_dir / f"{item}.txt"
            if not item_file.exists() or replace_existing:
                try:
                    item_content = filing_obj[item]
                    if item_content:
                        item_file.write_text(item_content, encoding="utf-8")
                        console.print(f"      [green]✓ {item_file.name}[/green]")
                except Exception as e:
                    console.print(f"      [red]Error: {e}[/red]")
            else:
                console.print(f"      [yellow]Skipped (exists): {item_file.name}[/yellow]")

    # Extract XBRL statements if available
    xbrl = filing.xbrl()
    if xbrl:
        statements = xbrl.statements
        for idx, s in enumerate(statements.statements):
            statement_definition = s.get('definition', None)
            statement_role = s.get('role', None)
            try:
                if statement_definition:
                    statement = statements[statement_definition]
                    statement_file = filing_statements_dir / f"{statement_definition}.md"
                elif statement_role:
                    statement = statements[statement_role]
                    statement_file = filing_statements_dir / f"{statement_role}.md"
                else:
                    console.print(f"    {s} has no type or role, using index {idx} as the statement name")
                    statement = statements[idx]
                    statement_file = filing_statements_dir / f"Statement{idx}.md"

                if statement and (not statement_file.exists() or replace_existing):
                    statement_markdown = statement.render().to_markdown()
                    statement_file.write_text(statement_markdown, encoding="utf-8")
                    console.print(f"      [green]✓ {statement_file.name}[/green]")
            except Exception as e:
                console.print(f"      [yellow]Could not process statement {idx}: {e}[/yellow]")

    # Sanitize form type for use in filenames (e.g., "10-K/A" -> "10-K_A")
    safe_form = filing.form.replace("/", "_")

    # save the raw html content to a file
    html_content = filing.html()
    if html_content:
        html_file = filing_dir / f"{safe_form}_{filing.filing_date}.html"
        html_file.write_text(html_content, encoding="utf-8")
        console.print(f"      [green]✓ HTML saved[/green]")

    # save the raw text content to a file
    text_content = filing.text()
    if text_content:
        text_file = filing_dir / f"{safe_form}_{filing.filing_date}.txt"
        text_file.write_text(text_content, encoding="utf-8")
        console.print(f"      [green]✓ Text saved[/green]")

    return True


def get_local_filings(company_dir: Path) -> set[str]:
    """Get set of accession numbers already downloaded locally."""
    if not company_dir.exists():
        return set()

    local_accessions = set()
    for item in company_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            local_accessions.add(item.name)

    return local_accessions


def main():
    parser = argparse.ArgumentParser(
        description="Download SEC filings and extract balance sheet for a ticker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run process_ticker.py AAPL
  uv run process_ticker.py MSFT --limit 20
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

    args = parser.parse_args()

    ticker = args.ticker.upper()
    company_dir = COMPANIES_DIR / ticker
    company_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold cyan]Processing ticker: {ticker}[/bold cyan]\n")

    # Initialize company
    company = Company(ticker)
    console.print(f"[bold]Company:[/bold] {company.name}")

    # get the filings
    filings = company.get_filings(form=args.form)
    if args.limit:
        filings = filings.head(args.limit)
    filings_list = list(filings)
    console.print(f"Found {len(filings_list)} {args.form} filings")

    # Check what's already downloaded
    local_accessions = get_local_filings(company_dir)
    console.print(f"\n[bold]Already downloaded locally:[/bold] {len(local_accessions)}")

    # Download each filing individually
    console.print("\n[bold]Downloading filings...[/bold]")
    downloaded = 0
    skipped = 0

    for filing in filings_list:
        if filing.accession_number in local_accessions and not args.replace_existing:
            skipped += 1
            continue

        console.print(
            f"\n  [bold]Downloading:[/bold] {filing.form} ({filing.filing_date}) - {filing.accession_number}"
        )
        if download_filing_content(filing, company_dir, args.replace_existing):
            downloaded += 1
            console.print(f"    [green]✓ Complete[/green]")

    console.print(f"\n[bold]Download Summary:[/bold]")
    console.print(f"  New downloads: {downloaded}")
    console.print(f"  Skipped (already downloaded): {skipped}")
    console.print(f"  Files stored in: {company_dir.absolute()}")


if __name__ == "__main__":
    main()


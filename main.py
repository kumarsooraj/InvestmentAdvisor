#!/usr/bin/env python3
"""
Investment Advisor Agent — CLI entry point.

Commands:
  run        Run investment analysis now
  schedule   Start the 15-day auto-scheduler (blocking)
  status     Show last run / next scheduled run
  portfolio  Show current portfolio summary

Usage:
  python main.py run
  python main.py run --amount 750          # override investment amount
  python main.py run --csv /path/to/file.csv
  python main.py schedule
  python main.py status
  python main.py portfolio
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()


def _run_analysis(amount: float, csv_path: str | None, json_path: str | None) -> None:
    """Load data, run advisor, print & save report."""
    from portfolio import load_portfolio
    from market_data import get_market_snapshot
    from advisor import InvestmentAdvisor
    from report import print_header, print_footer, save_report
    from scheduler import mark_run_complete

    # 1. Load portfolio
    console.print("[dim]Loading portfolio...[/dim]")
    portfolio = load_portfolio(csv_path=csv_path, json_path=json_path)
    if portfolio.source == "empty":
        console.print(
            Panel(
                "[yellow]No portfolio file found.\n\n"
                "To connect your Fidelity portfolio:\n"
                "  Option A (recommended):\n"
                "    1. Log in to Fidelity → Accounts & Trade → Portfolio\n"
                "    2. Click [bold]Download[/bold] (top right) → [bold]Positions[/bold]\n"
                "    3. Save the CSV to [bold]data/portfolio.csv[/bold]\n\n"
                "  Option B — manual JSON:\n"
                "    Copy [bold]data/holdings.json.example[/bold] to "
                "[bold]data/holdings.json[/bold] and edit it.\n\n"
                "Running with general market recommendations (no portfolio personalization).[/yellow]",
                title="⚠  Portfolio Not Found",
                border_style="yellow",
            )
        )

    # 2. Fetch market data
    console.print("[dim]Fetching market snapshot from Yahoo Finance...[/dim]")
    try:
        market_snapshot = get_market_snapshot()
    except Exception as e:
        console.print(f"[yellow]Warning: market data fetch failed ({e}). Proceeding with minimal data.[/yellow]")
        market_snapshot = {"note": "Market data unavailable — relying on web search for pricing."}

    # 3. Print header
    print_header(console, portfolio, amount)

    # 4. Run advisor (streams to console)
    advisor = InvestmentAdvisor()
    analysis_text = advisor.analyze(
        portfolio_summary=portfolio.to_summary(),
        market_snapshot=market_snapshot,
        investment_amount=amount,
        console=console,
    )

    # 5. Save report
    report_path = save_report(analysis_text, portfolio, amount)

    # 6. Mark run complete (for scheduler)
    mark_run_complete()

    # 7. Footer
    print_footer(console, report_path)


def cmd_run(args: argparse.Namespace) -> None:
    _run_analysis(
        amount=args.amount,
        csv_path=getattr(args, "csv", None),
        json_path=getattr(args, "json", None),
    )


def cmd_schedule(args: argparse.Namespace) -> None:
    from scheduler import run_loop
    from config import INVESTMENT_AMOUNT

    amount = getattr(args, "amount", INVESTMENT_AMOUNT)

    def analysis_callback():
        _run_analysis(amount=amount, csv_path=None, json_path=None)

    run_loop(analysis_callback)


def cmd_status(_args: argparse.Namespace) -> None:
    from scheduler import status_summary

    console.print(
        Panel(
            status_summary(),
            title="📅 Scheduler Status",
            border_style="blue",
        )
    )


def cmd_portfolio(_args: argparse.Namespace) -> None:
    from portfolio import load_portfolio
    from report import print_header

    portfolio = load_portfolio()
    if portfolio.source == "empty":
        console.print("[yellow]No portfolio data found. See `python main.py run` for setup instructions.[/yellow]")
        return

    print_header(console, portfolio, investment_amount=0)
    summary = portfolio.to_summary()
    console.print(f"\n[bold]Symbols held:[/bold] {', '.join(portfolio.symbols)}")
    console.print(f"[bold]Total value:[/bold]  ${summary['total_portfolio_value']:,.2f}")
    console.print(f"[bold]Cost basis:[/bold]   ${summary['total_cost_basis']:,.2f}")
    gl = summary["total_gain_loss_dollar"]
    gl_pct = summary["total_gain_loss_percent"]
    color = "green" if gl >= 0 else "red"
    console.print(f"[bold]Total gain:[/bold]   [{color}]${gl:+,.2f} ({gl_pct:+.1f}%)[/{color}]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Investment Advisor Agent — AI-powered Fidelity portfolio analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = subparsers.add_parser("run", help="Run investment analysis now")
    run_p.add_argument(
        "--amount",
        type=float,
        default=None,
        help="Investment amount in dollars (default: $500 or INVESTMENT_AMOUNT env var)",
    )
    run_p.add_argument("--csv", metavar="PATH", help="Path to Fidelity portfolio CSV export")
    run_p.add_argument("--json", metavar="PATH", help="Path to manual holdings JSON file")

    # schedule
    sched_p = subparsers.add_parser("schedule", help="Start the 15-day auto-scheduler")
    sched_p.add_argument("--amount", type=float, default=None)

    # status
    subparsers.add_parser("status", help="Show last/next scheduled run")

    # portfolio
    subparsers.add_parser("portfolio", help="Display current portfolio summary")

    args = parser.parse_args()

    # Resolve investment amount
    if hasattr(args, "amount") and args.amount is None:
        from config import INVESTMENT_AMOUNT
        args.amount = INVESTMENT_AMOUNT

    dispatch = {
        "run": cmd_run,
        "schedule": cmd_schedule,
        "status": cmd_status,
        "portfolio": cmd_portfolio,
    }

    try:
        dispatch[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

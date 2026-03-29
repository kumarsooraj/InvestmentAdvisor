"""
Report formatting and persistence.

• Prints a styled header/footer in the terminal (via rich)
• Saves the full analysis to data/reports/YYYY-MM-DD_HH-MM.md
"""

from __future__ import annotations

import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from config import REPORTS_DIR
from portfolio import Portfolio


def print_header(console: Console, portfolio: Portfolio, investment_amount: float) -> None:
    """Print a styled banner before the analysis begins."""
    console.rule("[bold blue]📈 Investment Advisor — Fidelity Portfolio Analysis[/bold blue]")
    console.print()

    # Portfolio summary table
    if portfolio.holdings:
        table = Table(
            title="Current Portfolio Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Symbol", style="bold white", width=8)
        table.add_column("Name", style="white", max_width=28)
        table.add_column("Shares", justify="right", style="yellow")
        table.add_column("Price", justify="right", style="white")
        table.add_column("Value", justify="right", style="green")
        table.add_column("Gain/Loss", justify="right")

        for h in sorted(portfolio.holdings, key=lambda x: x.current_value, reverse=True):
            gl_color = "green" if h.total_gain_loss >= 0 else "red"
            gl_text = Text(
                f"${h.total_gain_loss:+,.2f} ({h.total_gain_loss_pct:+.1f}%)",
                style=gl_color,
            )
            table.add_row(
                h.symbol,
                h.description[:28],
                f"{h.quantity:,.4f}",
                f"${h.last_price:,.2f}",
                f"${h.current_value:,.2f}",
                gl_text,
            )

        # Totals row
        total_gl = portfolio.total_gain_loss
        total_gl_pct = portfolio.total_gain_loss_pct
        gl_color = "green" if total_gl >= 0 else "red"
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            "",
            "",
            "",
            f"[bold green]${portfolio.total_value:,.2f}[/bold green]",
            Text(f"${total_gl:+,.2f} ({total_gl_pct:+.1f}%)", style=f"bold {gl_color}"),
        )

        console.print(table)
        console.print()
    else:
        console.print(
            Panel(
                "[yellow]No portfolio data found.\n"
                "Add data/portfolio.csv (Fidelity export) or data/holdings.json "
                "for personalized recommendations.[/yellow]",
                title="Portfolio",
                border_style="yellow",
            )
        )
        console.print()

    # Run info
    console.print(
        Panel(
            f"[bold white]🗓  Date:[/bold white] {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n"
            f"[bold white]💰 Deploying:[/bold white] [bold green]${investment_amount:,.0f}[/bold green]\n"
            f"[bold white]🤖 Model:[/bold white] Claude Opus 4.6 + Live Web Search",
            title="Analysis Run",
            border_style="blue",
        )
    )
    console.print()
    console.rule("[dim]Fetching live market data and news...[/dim]")
    console.print()


def print_footer(console: Console, report_path: str) -> None:
    """Print a styled footer with the report path."""
    console.print()
    console.rule("[bold green]✅ Analysis Complete[/bold green]")
    console.print(
        Panel(
            f"[bold white]📄 Report saved to:[/bold white]\n[cyan]{report_path}[/cyan]\n\n"
            f"[dim]Next analysis due in 15 days. Run [bold]python main.py schedule[/bold] to automate.[/dim]",
            border_style="green",
        )
    )


def save_report(analysis_text: str, portfolio: Portfolio, investment_amount: float) -> str:
    """
    Save the analysis to a markdown file.
    Returns the file path.
    """
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H-%M") + "_investment_analysis.md"
    path = os.path.join(REPORTS_DIR, filename)

    portfolio_section = ""
    if portfolio.holdings:
        portfolio_section = "## Current Portfolio\n\n"
        portfolio_section += "| Symbol | Name | Shares | Value | Gain/Loss |\n"
        portfolio_section += "|--------|------|--------|-------|-----------|\n"
        for h in sorted(portfolio.holdings, key=lambda x: x.current_value, reverse=True):
            sign = "+" if h.total_gain_loss >= 0 else ""
            portfolio_section += (
                f"| {h.symbol} | {h.description[:30]} | {h.quantity:.4f} "
                f"| ${h.current_value:,.2f} | {sign}${h.total_gain_loss:,.2f} "
                f"({sign}{h.total_gain_loss_pct:.1f}%) |\n"
            )
        portfolio_section += f"\n**Total Portfolio Value:** ${portfolio.total_value:,.2f}\n\n"

    content = f"""# Investment Analysis Report
**Date:** {now.strftime('%B %d, %Y at %I:%M %p')}
**Investment Amount:** ${investment_amount:,.0f}
**Model:** Claude Opus 4.6 with Live Web Search

---

{portfolio_section}---

## Analysis & Recommendations

{analysis_text}

---
*Generated by Investment Advisor Agent*
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path

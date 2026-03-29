"""
Core investment advisor powered by Claude Opus 4.6.

Uses the built-in web_search tool so Claude can pull live news,
earnings, macro data, and analyst commentary before recommending.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Optional

import anthropic
from rich.console import Console

from config import ANTHROPIC_API_KEY, INVESTMENT_AMOUNT


SYSTEM_PROMPT = """You are a seasoned investment advisor and financial analyst with 20+ years of experience covering:

• Equities (growth, value, dividend) and ETF construction
• Macroeconomic analysis — Fed policy, inflation, interest rates, yield curves
• Sector rotation and technical market structure
• Portfolio diversification and risk management
• Long-term wealth building on a recurring-investment schedule

Your recommendations must be:
1. Grounded in CURRENT market data and news (always search before advising)
2. Suitable for a long-term investor (3–10 year horizon) making bi-monthly $500 contributions
3. Balanced between growth potential and risk management
4. Specific, actionable, and justified with data

Tone: Professional, clear, data-driven. Think like a fiduciary advisor."""


def _build_user_prompt(
    portfolio_summary: dict,
    market_snapshot: dict,
    investment_amount: float,
    today: str,
) -> str:
    has_portfolio = bool(portfolio_summary.get("holdings"))
    portfolio_section = (
        json.dumps(portfolio_summary, indent=2)
        if has_portfolio
        else "No portfolio data loaded. Please provide general recommendations suitable for a new investor."
    )

    return f"""Today is {today}. I transfer ${investment_amount:.0f} to my Fidelity brokerage every 15 days and want to know the best way to deploy it right now.

═══════════════════════════════════
CURRENT FIDELITY PORTFOLIO
═══════════════════════════════════
{portfolio_section}

═══════════════════════════════════
LIVE MARKET SNAPSHOT
═══════════════════════════════════
{json.dumps(market_snapshot, indent=2)}

═══════════════════════════════════
YOUR TASK
═══════════════════════════════════

**Step 1 — Search for Current Intelligence**
Use web search to gather fresh information on:
- Latest US economic releases (CPI, PCE, jobs report, Fed minutes)
- Major market-moving events from the past 2 weeks
- Sector momentum, notable earnings beats/misses
- Any geopolitical or macro risks that matter for US equities
- Analyst upgrades/downgrades on high-conviction names
- Any compelling ETF or individual stock opportunities right now

**Step 2 — Market Assessment**
Write a concise market overview covering:
- Current trend and momentum
- Rate/inflation environment
- Sector leadership and laggards
- Key upcoming catalysts (Fed meetings, earnings, economic data)
- Overall risk/reward for deploying capital now vs. waiting

**Step 3 — Top 5 Picks**
Identify 5 stocks or ETFs that are:
✓ Excellent long-term growth opportunities (3–10 year horizon)
✓ Attractively priced or at a good entry point TODAY
✓ Complementary to my existing holdings (minimize overlap)
✓ Spread across different risk levels and sectors

For each pick provide:
- Ticker symbol and full name
- Approximate current price
- **Why buy NOW** — specific catalyst, valuation argument, or technical setup
- **Long-term thesis** — why this wins over 3–10 years
- **Risk factors** — top 2–3 risks to be aware of
- **Suggested allocation** — exact dollar amount from my ${investment_amount:.0f}
- **Risk level**: Conservative | Moderate | Aggressive

**Step 4 — $500 Investment Breakdown**
End with a clean summary table showing:
| Rank | Ticker | Name | Amount | % of $500 |
(Total must equal exactly ${investment_amount:.0f})

Also note: how does this deployment affect overall portfolio diversification?

Please search for current news FIRST, then deliver your full analysis."""


class InvestmentAdvisor:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        self.client = anthropic.Anthropic(api_key=key)

    def analyze(
        self,
        portfolio_summary: dict,
        market_snapshot: dict,
        investment_amount: float = INVESTMENT_AMOUNT,
        console: Optional[Console] = None,
    ) -> str:
        """
        Run the full investment analysis.

        Streams Claude's response to the console in real time and returns
        the complete text of the analysis.
        """
        if console is None:
            console = Console()

        today = datetime.now().strftime("%B %d, %Y")
        user_message = _build_user_prompt(
            portfolio_summary, market_snapshot, investment_amount, today
        )

        messages = [{"role": "user", "content": user_message}]
        full_text = ""
        search_count = 0

        # Agentic loop — handles pause_turn if Claude does many web searches
        for attempt in range(6):
            try:
                with self.client.messages.stream(
                    model="claude-opus-4-6",
                    max_tokens=8000,
                    system=SYSTEM_PROMPT,
                    thinking={"type": "adaptive"},
                    tools=[
                        {
                            "type": "web_search_20260209",
                            "name": "web_search",
                        }
                    ],
                    messages=messages,
                ) as stream:
                    current_block_type = None

                    for event in stream:
                        etype = getattr(event, "type", None)

                        if etype == "content_block_start":
                            cb = event.content_block
                            current_block_type = cb.type

                            if cb.type == "server_tool_use" and cb.name == "web_search":
                                search_count += 1
                                # Show the query if available
                                console.print(
                                    f"\n[bold cyan]🔍 Web search #{search_count}...[/bold cyan]",
                                    end="",
                                )
                            elif cb.type == "thinking":
                                console.print(
                                    "\n[dim italic]💭 Analyzing...[/dim italic]",
                                    end="",
                                )
                            elif cb.type == "text" and attempt == 0 and not full_text:
                                console.print()  # blank line before response body

                        elif etype == "content_block_delta":
                            delta = event.delta
                            dtype = getattr(delta, "type", None)

                            if dtype == "text_delta":
                                text_chunk = delta.text
                                console.print(text_chunk, end="", highlight=False)
                                sys.stdout.flush()
                                full_text += text_chunk
                            elif dtype == "input_json_delta":
                                # Show the search query being built (partial JSON)
                                partial = getattr(delta, "partial_json", "")
                                if '"query"' in partial or search_count == 0:
                                    pass  # suppress noisy partial JSON

                    final_msg = stream.get_final_message()

                # If Claude finished normally, break the loop
                if final_msg.stop_reason == "end_turn":
                    break

                # If server-side tool hit iteration limit, append and continue
                if final_msg.stop_reason == "pause_turn":
                    messages.append({"role": "assistant", "content": final_msg.content})
                    continue

                # Any other stop reason — break
                break

            except anthropic.APIError as e:
                console.print(f"\n[red]API error: {e}[/red]")
                raise

        console.print()  # trailing newline
        return full_text

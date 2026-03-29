"""
Portfolio loader supporting two sources:
  1. Fidelity CSV export  →  data/portfolio.csv
  2. Manual JSON file     →  data/holdings.json

Fidelity export instructions:
  Accounts & Trade → Portfolio → Download (top-right) → "Positions" CSV
"""

import csv
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Optional
from config import PORTFOLIO_CSV, HOLDINGS_JSON


@dataclass
class Holding:
    symbol: str
    description: str
    quantity: float
    last_price: float
    current_value: float
    cost_basis: float
    total_gain_loss: float
    total_gain_loss_pct: float
    account_type: str = "Individual"


@dataclass
class Portfolio:
    holdings: list[Holding] = field(default_factory=list)
    total_value: float = 0.0
    total_cost_basis: float = 0.0
    total_gain_loss: float = 0.0
    cash: float = 0.0
    source: str = "unknown"

    @property
    def symbols(self) -> list[str]:
        return [h.symbol for h in self.holdings if h.symbol and h.symbol != "--"]

    @property
    def total_gain_loss_pct(self) -> float:
        if self.total_cost_basis > 0:
            return (self.total_gain_loss / self.total_cost_basis) * 100
        return 0.0

    def to_summary(self) -> dict:
        """Return a summary dict suitable for passing to Claude."""
        return {
            "total_portfolio_value": round(self.total_value, 2),
            "total_cost_basis": round(self.total_cost_basis, 2),
            "total_gain_loss_dollar": round(self.total_gain_loss, 2),
            "total_gain_loss_percent": round(self.total_gain_loss_pct, 2),
            "cash_available": round(self.cash, 2),
            "number_of_positions": len(self.holdings),
            "holdings": [
                {
                    "symbol": h.symbol,
                    "name": h.description,
                    "shares": round(h.quantity, 4),
                    "current_price": round(h.last_price, 2),
                    "current_value": round(h.current_value, 2),
                    "cost_basis": round(h.cost_basis, 2),
                    "gain_loss_dollar": round(h.total_gain_loss, 2),
                    "gain_loss_percent": round(h.total_gain_loss_pct, 2),
                    "account_type": h.account_type,
                }
                for h in sorted(self.holdings, key=lambda x: x.current_value, reverse=True)
            ],
        }


def _clean_number(val: str) -> float:
    """Strip $, %, commas and convert to float."""
    if not val or val.strip() in ("", "--", "N/A", "n/a"):
        return 0.0
    cleaned = re.sub(r"[$,%]", "", val.strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def load_from_fidelity_csv(path: str) -> Portfolio:
    """
    Parse a Fidelity portfolio CSV export.

    Fidelity's CSV has a variable number of header rows before the column
    headers row (which starts with 'Symbol' or 'Account Name').
    """
    portfolio = Portfolio(source="fidelity_csv")

    with open(path, newline="", encoding="utf-8-sig") as f:
        raw = f.read()

    lines = raw.splitlines()

    # Find the row that contains the column headers
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\bSymbol\b", line, re.IGNORECASE):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(
            "Could not find 'Symbol' header row in Fidelity CSV. "
            "Please export Positions from Fidelity (Accounts → Portfolio → Download)."
        )

    reader = csv.DictReader(lines[header_idx:])

    # Normalize column names: strip whitespace, lowercase for lookup
    def col(row: dict, *candidates) -> str:
        for c in candidates:
            for k in row:
                if k.strip().lower() == c.lower():
                    return row[k]
        return ""

    for row in reader:
        symbol = col(row, "Symbol", "symbol").strip().strip('"')

        # Skip blank rows, total rows, account header rows
        if not symbol or symbol in ("--", "Symbol") or symbol.startswith("Account"):
            continue
        # Skip cash/money market rows that aren't real equity positions
        if symbol.startswith("**") or symbol.startswith("Pending"):
            continue

        description = col(row, "Description", "description").strip().strip('"')
        quantity = _clean_number(col(row, "Quantity", "quantity"))
        last_price = _clean_number(col(row, "Last Price", "last price"))
        current_value = _clean_number(col(row, "Current Value", "current value"))
        cost_basis = _clean_number(col(row, "Cost Basis Total", "cost basis total", "cost basis"))
        tgl_dollar = _clean_number(col(row, "Total Gain/Loss Dollar", "total gain/loss dollar"))
        tgl_pct = _clean_number(col(row, "Total Gain/Loss Percent", "total gain/loss percent"))
        acct_type = col(row, "Type", "type", "Account Type").strip().strip('"') or "Individual"

        if current_value == 0 and quantity > 0 and last_price > 0:
            current_value = quantity * last_price
        if tgl_dollar == 0 and cost_basis > 0:
            tgl_dollar = current_value - cost_basis
        if tgl_pct == 0 and cost_basis > 0:
            tgl_pct = (tgl_dollar / cost_basis) * 100

        holding = Holding(
            symbol=symbol,
            description=description,
            quantity=quantity,
            last_price=last_price,
            current_value=current_value,
            cost_basis=cost_basis,
            total_gain_loss=tgl_dollar,
            total_gain_loss_pct=tgl_pct,
            account_type=acct_type,
        )
        portfolio.holdings.append(holding)

        # Accumulate totals (skip if this looks like a cash row)
        if last_price > 0:
            portfolio.total_value += current_value
            portfolio.total_cost_basis += cost_basis
            portfolio.total_gain_loss += tgl_dollar

    return portfolio


def load_from_json(path: str) -> Portfolio:
    """
    Load from a simple JSON file. Format:

    {
      "cash": 250.00,
      "holdings": [
        {"symbol": "AAPL", "description": "Apple Inc", "shares": 10,
         "avg_cost": 145.00, "current_price": 195.00},
        ...
      ]
    }
    """
    with open(path) as f:
        data = json.load(f)

    portfolio = Portfolio(source="manual_json")
    portfolio.cash = float(data.get("cash", 0))

    for item in data.get("holdings", []):
        symbol = item.get("symbol", "").upper()
        if not symbol:
            continue

        shares = float(item.get("shares", item.get("quantity", 0)))
        avg_cost = float(item.get("avg_cost", item.get("cost_per_share", 0)))
        current_price = float(item.get("current_price", item.get("last_price", 0)))
        current_value = shares * current_price if current_price else 0
        cost_basis = shares * avg_cost if avg_cost else 0
        tgl = current_value - cost_basis
        tgl_pct = (tgl / cost_basis * 100) if cost_basis else 0

        holding = Holding(
            symbol=symbol,
            description=item.get("description", item.get("name", symbol)),
            quantity=shares,
            last_price=current_price,
            current_value=current_value,
            cost_basis=cost_basis,
            total_gain_loss=tgl,
            total_gain_loss_pct=tgl_pct,
            account_type=item.get("account_type", "Individual"),
        )
        portfolio.holdings.append(holding)
        portfolio.total_value += current_value
        portfolio.total_cost_basis += cost_basis
        portfolio.total_gain_loss += tgl

    return portfolio


def load_portfolio(csv_path: Optional[str] = None, json_path: Optional[str] = None) -> Portfolio:
    """
    Auto-detect and load portfolio.
    Priority: explicit path > data/portfolio.csv > data/holdings.json
    Returns an empty Portfolio if neither file exists (user will be warned).
    """
    paths_to_try = []

    if csv_path:
        paths_to_try.append(("csv", csv_path))
    if json_path:
        paths_to_try.append(("json", json_path))

    # Auto-detect
    if os.path.exists(PORTFOLIO_CSV):
        paths_to_try.append(("csv", PORTFOLIO_CSV))
    if os.path.exists(HOLDINGS_JSON):
        paths_to_try.append(("json", HOLDINGS_JSON))

    for fmt, path in paths_to_try:
        try:
            if fmt == "csv":
                return load_from_fidelity_csv(path)
            else:
                return load_from_json(path)
        except Exception as e:
            # Try next option
            print(f"Warning: could not load portfolio from {path}: {e}")

    # Return empty portfolio — advisor will still work, just without personalization
    return Portfolio(source="empty")

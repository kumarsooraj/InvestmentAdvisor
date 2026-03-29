"""
Fetches current market data via yfinance for context passed to the advisor.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

from config import MARKET_INDICES, SECTOR_ETFS, BROAD_ETFS

# Suppress yfinance deprecation noise
warnings.filterwarnings("ignore", category=FutureWarning)


def _safe_get(ticker: yf.Ticker, period: str = "5d") -> Optional[dict]:
    """Return a minimal price snapshot for one ticker, or None on error."""
    try:
        hist = ticker.history(period=period, auto_adjust=True)
        if hist.empty:
            return None

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else hist.iloc[-1]

        close = float(latest["Close"])
        prev_close = float(prev["Close"])
        change = close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        # 1-month performance
        month_hist = ticker.history(period="1mo", auto_adjust=True)
        month_change_pct = 0.0
        if not month_hist.empty and len(month_hist) >= 2:
            month_start = float(month_hist.iloc[0]["Close"])
            month_change_pct = ((close - month_start) / month_start * 100) if month_start else 0.0

        # 52-week high/low
        year_hist = ticker.history(period="1y", auto_adjust=True)
        week52_high = float(year_hist["High"].max()) if not year_hist.empty else close
        week52_low = float(year_hist["Low"].min()) if not year_hist.empty else close
        pct_from_high = ((close - week52_high) / week52_high * 100) if week52_high else 0.0

        return {
            "price": round(close, 2),
            "change_today": round(change, 2),
            "change_today_pct": round(change_pct, 2),
            "change_1month_pct": round(month_change_pct, 2),
            "week52_high": round(week52_high, 2),
            "week52_low": round(week52_low, 2),
            "pct_from_52w_high": round(pct_from_high, 2),
        }
    except Exception:
        return None


def get_market_snapshot() -> dict:
    """
    Build a comprehensive market snapshot:
      - Major indices
      - Sector ETF performance (to identify hot/cold sectors)
      - Broad market ETFs (bonds, gold, etc.)
    Returns a dict ready for JSON serialization.
    """
    snapshot: dict = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indices": {},
        "sectors": {},
        "broad_etfs": {},
        "market_breadth": {},
    }

    # --- Indices ---
    for ticker_sym, name in MARKET_INDICES.items():
        ticker = yf.Ticker(ticker_sym)
        data = _safe_get(ticker)
        if data:
            snapshot["indices"][name] = data

    # --- Sector ETFs ---
    sector_changes: list[tuple[str, float]] = []
    for sym, name in SECTOR_ETFS.items():
        ticker = yf.Ticker(sym)
        data = _safe_get(ticker)
        if data:
            snapshot["sectors"][name] = {**data, "ticker": sym}
            sector_changes.append((name, data["change_today_pct"]))

    # Market breadth: top/bottom sectors today
    if sector_changes:
        sector_changes.sort(key=lambda x: x[1], reverse=True)
        snapshot["market_breadth"]["top_sectors_today"] = [
            {"sector": s, "change_pct": round(c, 2)} for s, c in sector_changes[:3]
        ]
        snapshot["market_breadth"]["bottom_sectors_today"] = [
            {"sector": s, "change_pct": round(c, 2)} for s, c in sector_changes[-3:]
        ]

    # --- Broad ETFs ---
    for sym, name in BROAD_ETFS.items():
        ticker = yf.Ticker(sym)
        data = _safe_get(ticker)
        if data:
            snapshot["broad_etfs"][name] = {**data, "ticker": sym}

    # --- Derived market context ---
    sp500 = snapshot["indices"].get("S&P 500", {})
    vix = snapshot["indices"].get("VIX Volatility Index", {})

    if sp500:
        pct_from_high = sp500.get("pct_from_52w_high", 0)
        if pct_from_high > -5:
            market_phase = "Near 52-week highs (strong bull)"
        elif pct_from_high > -10:
            market_phase = "Mild pullback from highs"
        elif pct_from_high > -20:
            market_phase = "Correction territory (10-20% below highs)"
        else:
            market_phase = "Bear market territory (>20% below highs)"
        snapshot["market_phase"] = market_phase

    if vix:
        vix_price = vix.get("price", 0)
        if vix_price < 15:
            vix_regime = "Low volatility — complacent market"
        elif vix_price < 20:
            vix_regime = "Normal volatility"
        elif vix_price < 30:
            vix_regime = "Elevated volatility — some fear"
        else:
            vix_regime = "High volatility — fear/panic in market"
        snapshot["volatility_regime"] = f"VIX {vix_price:.1f} — {vix_regime}"

    # Bond vs equity signal
    tlt = snapshot["broad_etfs"].get("20+ Year Treasury ETF", {})
    if tlt and sp500:
        bond_1m = tlt.get("change_1month_pct", 0)
        equity_1m = sp500.get("change_1month_pct", 0)
        if bond_1m > equity_1m + 2:
            snapshot["risk_signal"] = "Risk-off: bonds outperforming equities"
        elif equity_1m > bond_1m + 2:
            snapshot["risk_signal"] = "Risk-on: equities outperforming bonds"
        else:
            snapshot["risk_signal"] = "Neutral: equities and bonds moving together"

    return snapshot

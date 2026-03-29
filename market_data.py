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


def _safe_get(ticker: yf.Ticker, period: str = "5d") -> Optional[dict]:  # noqa: F841
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
    Attempts to fetch a market snapshot via yfinance.
    Falls back to an empty snapshot if network access is unavailable
    (Claude's web_search tool will cover market data in that case).
    """
    snapshot: dict = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": "Market data unavailable in this environment — Claude will fetch live prices and news via web search.",
    }

    try:
        # Quick connectivity test
        test = yf.Ticker("SPY")
        data = _safe_get(test, period="2d")
        if data is None:
            return snapshot

        # Full snapshot
        for ticker_sym, name in MARKET_INDICES.items():
            ticker = yf.Ticker(ticker_sym)
            d = _safe_get(ticker)
            if d:
                snapshot.setdefault("indices", {})[name] = d

        for sym, name in SECTOR_ETFS.items():
            ticker = yf.Ticker(sym)
            d = _safe_get(ticker)
            if d:
                snapshot.setdefault("sectors", {})[name] = {**d, "ticker": sym}

        for sym, name in BROAD_ETFS.items():
            ticker = yf.Ticker(sym)
            d = _safe_get(ticker)
            if d:
                snapshot.setdefault("broad_etfs", {})[name] = {**d, "ticker": sym}

        snapshot.pop("note", None)

    except Exception:
        pass  # Claude will get market data via web_search

    return snapshot

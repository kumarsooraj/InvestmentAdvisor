import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
INVESTMENT_AMOUNT = float(os.getenv("INVESTMENT_AMOUNT", "500"))
SCHEDULE_DAYS = int(os.getenv("SCHEDULE_DAYS", "15"))

# Major market indices (yfinance tickers)
MARKET_INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones Industrial",
    "^RUT": "Russell 2000",
    "^VIX": "VIX Volatility Index",
}

# Sector ETFs for breadth analysis
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

# Broad market ETFs tracked for context
BROAD_ETFS = {
    "SPY": "S&P 500 ETF",
    "QQQ": "NASDAQ-100 ETF",
    "IWM": "Russell 2000 ETF",
    "GLD": "Gold ETF",
    "TLT": "20+ Year Treasury ETF",
    "BND": "Total Bond Market ETF",
}

# File paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
LAST_RUN_FILE = os.path.join(DATA_DIR, "last_run.json")
PORTFOLIO_CSV = os.path.join(DATA_DIR, "portfolio.csv")
HOLDINGS_JSON = os.path.join(DATA_DIR, "holdings.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

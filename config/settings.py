"""
Centralized configuration for the Financial Valuation & Risk Monitoring Dashboard.
All thresholds, paths and parameters are defined here for easy tuning.
"""

import os
from pathlib import Path

# ─── Project Paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = PROJECT_ROOT / "exports"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# ─── Database Path ─────────────────────────────────────────────────────────────
DB_PATH = DATA_DIR / "audit_trail.db"

# ─── Data Generation ───────────────────────────────────────────────────────────
NUM_POSITIONS = 500
RANDOM_SEED = 42

ASSET_CLASSES = {
    "Equity":        {"weight": 0.30, "price_range": (10.0, 500.0),  "qty_range": (100, 10000)},
    "Fixed Income":  {"weight": 0.25, "price_range": (90.0, 110.0),  "qty_range": (1000, 100000)},
    "FX Forward":    {"weight": 0.15, "price_range": (0.5, 2.0),     "qty_range": (50000, 5000000)},
    "Commodity":     {"weight": 0.10, "price_range": (20.0, 2000.0), "qty_range": (10, 5000)},
    "Derivative":    {"weight": 0.10, "price_range": (1.0, 50.0),    "qty_range": (100, 50000)},
    "Structured":    {"weight": 0.10, "price_range": (80.0, 120.0),  "qty_range": (500, 20000)},
}

# Probability of injecting data-quality issues for realistic testing
MISSING_PRICE_RATE = 0.03       # 3% of positions will have missing prices
DUPLICATE_RATE = 0.02           # 2% will be intentional duplicates
INVALID_QTY_RATE = 0.02        # 2% will have invalid (negative/zero) quantities
LARGE_DEVIATION_RATE = 0.05    # 5% will have large price deviations

# ─── Valuation Thresholds ──────────────────────────────────────────────────────
DEFAULT_THRESHOLD_PCT = 5.0     # Flag if |recorded - reference| > 5%
WARNING_THRESHOLD_PCT = 2.0     # Amber warning level
CRITICAL_THRESHOLD_PCT = 10.0   # Critical deviation level

# ─── Export Settings ───────────────────────────────────────────────────────────
EXCEL_EXPORT_FILENAME = "valuation_exception_report.xlsx"
CSV_EXPORT_FILENAME = "powerbi_dataset.csv"
SUMMARY_CSV_FILENAME = "portfolio_summary.csv"

# ─── AI Summary (Optional) ────────────────────────────────────────────────────
ENABLE_AI_SUMMARY = False
OPENAI_MODEL = "gpt-4"
AI_SYSTEM_PROMPT = """You are a financial controls analyst assistant. Summarize 
the exception report data provided. You MUST NOT modify any financial calculations, 
invent missing data, or provide investment advice. Only describe patterns, highlight 
notable exceptions, and suggest areas for review."""

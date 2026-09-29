"""
Synthetic Portfolio Data Generator
===================================
Generates realistic financial position data with intentional data-quality
issues (missing prices, duplicates, invalid quantities, large deviations)
for testing the valuation control pipeline.

All data is purely synthetic and does not represent real financial instruments.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple
import string
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    NUM_POSITIONS, RANDOM_SEED, ASSET_CLASSES,
    MISSING_PRICE_RATE, DUPLICATE_RATE, INVALID_QTY_RATE,
    LARGE_DEVIATION_RATE, DATA_DIR
)


def _generate_instrument_id(asset_class: str, index: int, rng: np.random.Generator) -> str:
    """Generate a realistic-looking instrument identifier."""
    prefixes = {
        "Equity": "EQ",
        "Fixed Income": "FI",
        "FX Forward": "FX",
        "Commodity": "CM",
        "Derivative": "DV",
        "Structured": "ST",
    }
    prefix = prefixes.get(asset_class, "XX")
    suffix = ''.join(rng.choice(list(string.ascii_uppercase + string.digits), size=6))
    return f"{prefix}-{suffix}-{index:04d}"


def _generate_counterparty(rng: np.random.Generator) -> str:
    """Generate a synthetic counterparty name."""
    banks = [
        "GlobalBank Corp", "Atlantic Capital", "Pacific Securities",
        "Summit Financial", "Meridian Holdings", "Apex Trading",
        "Pinnacle Markets", "Horizon Investments", "Sterling Partners",
        "Vanguard Securities", "Fortress Capital", "Eagle Point Trading",
        "Citadel Markets", "Northstar Financial", "Emerald Trust",
    ]
    return rng.choice(banks)


def _generate_currency(asset_class: str, rng: np.random.Generator) -> str:
    """Assign a realistic currency based on asset class."""
    if asset_class == "FX Forward":
        pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]
        return rng.choice(pairs)
    currencies = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]
    weights = [0.40, 0.25, 0.10, 0.08, 0.07, 0.05, 0.05]
    return rng.choice(currencies, p=weights)


def generate_portfolio(
    num_positions: int = NUM_POSITIONS,
    seed: int = RANDOM_SEED,
    valuation_date: datetime = None,
) -> pd.DataFrame:
    """
    Generate a synthetic portfolio of financial positions.

    Parameters
    ----------
    num_positions : int
        Total number of positions to generate.
    seed : int
        Random seed for reproducibility.
    valuation_date : datetime, optional
        The valuation date stamp. Defaults to today.

    Returns
    -------
    pd.DataFrame
        Portfolio DataFrame with columns:
        - position_id, instrument_id, asset_class, counterparty, currency
        - quantity, recorded_price, reference_price, valuation_date
    """
    rng = np.random.default_rng(seed)

    if valuation_date is None:
        valuation_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Distribute positions across asset classes by weight
    asset_names = list(ASSET_CLASSES.keys())
    weights = [ASSET_CLASSES[a]["weight"] for a in asset_names]
    asset_assignments = rng.choice(asset_names, size=num_positions, p=weights)

    records = []
    for i, asset_class in enumerate(asset_assignments):
        cfg = ASSET_CLASSES[asset_class]
        price_lo, price_hi = cfg["price_range"]
        qty_lo, qty_hi = cfg["qty_range"]

        instrument_id = _generate_instrument_id(asset_class, i, rng)
        counterparty = _generate_counterparty(rng)
        currency = _generate_currency(asset_class, rng)
        quantity = int(rng.integers(qty_lo, qty_hi))

        # Generate base reference price
        reference_price = round(rng.uniform(price_lo, price_hi), 4)

        # Recorded price = reference + small normal noise (typical daily variation)
        noise_pct = rng.normal(0, 0.005)  # ~0.5% standard deviation
        recorded_price = round(reference_price * (1 + noise_pct), 4)

        records.append({
            "position_id": f"POS-{i+1:05d}",
            "instrument_id": instrument_id,
            "asset_class": asset_class,
            "counterparty": counterparty,
            "currency": currency,
            "quantity": quantity,
            "recorded_price": recorded_price,
            "reference_price": reference_price,
            "valuation_date": valuation_date.strftime("%Y-%m-%d"),
        })

    df = pd.DataFrame(records)

    # ── Inject Data-Quality Issues ──────────────────────────────────────────
    df = _inject_missing_prices(df, rng)
    df = _inject_duplicates(df, rng)
    df = _inject_invalid_quantities(df, rng)
    df = _inject_large_deviations(df, rng)

    return df.reset_index(drop=True)


def _inject_missing_prices(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Set some recorded or reference prices to NaN."""
    n_missing = max(1, int(len(df) * MISSING_PRICE_RATE))
    missing_idx = rng.choice(df.index, size=n_missing, replace=False)
    for idx in missing_idx:
        col = rng.choice(["recorded_price", "reference_price"])
        df.at[idx, col] = np.nan
    return df


def _inject_duplicates(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Duplicate a few rows to simulate duplicate position entries."""
    n_dupes = max(1, int(len(df) * DUPLICATE_RATE))
    dupe_idx = rng.choice(df.index, size=n_dupes, replace=False)
    dupes = df.loc[dupe_idx].copy()
    df = pd.concat([df, dupes], ignore_index=True)
    return df


def _inject_invalid_quantities(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Set some quantities to zero or negative values."""
    n_invalid = max(1, int(len(df) * INVALID_QTY_RATE))
    invalid_idx = rng.choice(df.index, size=n_invalid, replace=False)
    for idx in invalid_idx:
        df.at[idx, "quantity"] = rng.choice([0, -abs(int(rng.integers(1, 1000)))])
    return df


def _inject_large_deviations(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Introduce large price deviations to trigger threshold alerts."""
    n_deviate = max(1, int(len(df) * LARGE_DEVIATION_RATE))
    valid_mask = df["recorded_price"].notna() & df["reference_price"].notna()
    valid_idx = df.index[valid_mask]
    if len(valid_idx) == 0:
        return df
    deviate_idx = rng.choice(valid_idx, size=min(n_deviate, len(valid_idx)), replace=False)
    for idx in deviate_idx:
        direction = rng.choice([-1, 1])
        deviation = rng.uniform(0.08, 0.25)  # 8-25% deviation
        df.at[idx, "recorded_price"] = round(
            df.at[idx, "reference_price"] * (1 + direction * deviation), 4
        )
    return df


def generate_reconciliation_datasets(
    num_positions: int = 300,
    seed: int = RANDOM_SEED,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate separate internal position records and reference market price records
    with injected reconciliation issues (unmatched records, stale dates, price mismatches).

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (internal_positions_df, reference_prices_df)
    """
    rng = np.random.default_rng(seed)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")

    asset_names = list(ASSET_CLASSES.keys())
    weights = [ASSET_CLASSES[a]["weight"] for a in asset_names]
    asset_assignments = rng.choice(asset_names, size=num_positions, p=weights)

    internal_records = []
    reference_records = []

    for i, asset_class in enumerate(asset_assignments):
        cfg = ASSET_CLASSES[asset_class]
        price_lo, price_hi = cfg["price_range"]
        qty_lo, qty_hi = cfg["qty_range"]

        inst_id = _generate_instrument_id(asset_class, i, rng)
        ref_price = round(float(rng.uniform(price_lo, price_hi)), 4)
        noise = rng.normal(0, 0.005)
        rec_price = round(ref_price * (1 + noise), 4)

        internal_records.append({
            "position_id": f"POS-INT-{i+1:05d}",
            "instrument_id": inst_id,
            "asset_class": asset_class,
            "counterparty": _generate_counterparty(rng),
            "currency": _generate_currency(asset_class, rng),
            "quantity": int(rng.integers(qty_lo, qty_hi)),
            "recorded_price": rec_price,
            "valuation_date": today_str,
        })

        reference_records.append({
            "instrument_id": inst_id,
            "reference_price": ref_price,
            "valuation_date": today_str,
            "source": rng.choice(["Bloomberg", "Reuters", "ICE", "Markit"]),
        })

    internal_df = pd.DataFrame(internal_records)
    reference_df = pd.DataFrame(reference_records)

    # ── Inject Reconciliation Issues ────────────────────────────────────────

    # 1. Unmatched Internal Positions: Drop 10 reference records
    drop_ref_idx = rng.choice(reference_df.index, size=10, replace=False)
    reference_df = reference_df.drop(index=drop_ref_idx).reset_index(drop=True)

    # 2. Unmatched Reference Records: Add 10 dummy market feed records
    extra_ref = []
    for k in range(10):
        extra_inst = f"MARKET-EXTRA-{k+1:03d}"
        extra_ref.append({
            "instrument_id": extra_inst,
            "reference_price": round(float(rng.uniform(50.0, 500.0)), 4),
            "valuation_date": today_str,
            "source": "Bloomberg",
        })
    reference_df = pd.concat([reference_df, pd.DataFrame(extra_ref)], ignore_index=True)

    # 3. Stale Reference Prices: Set 8 reference valuation dates to 2-5 days ago
    stale_idx = rng.choice(reference_df.index[:len(reference_df)-10], size=8, replace=False)
    for idx in stale_idx:
        days_ago = int(rng.integers(2, 6))
        stale_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        reference_df.at[idx, "valuation_date"] = stale_date

    # 4. Large Price Mismatches: Change recorded prices on 15 positions by 8-25%
    mismatch_idx = rng.choice(internal_df.index, size=15, replace=False)
    for idx in mismatch_idx:
        dev = rng.uniform(0.08, 0.25)
        sign = rng.choice([-1, 1])
        internal_df.at[idx, "recorded_price"] = round(internal_df.at[idx, "recorded_price"] * (1 + sign * dev), 4)

    return internal_df.reset_index(drop=True), reference_df.reset_index(drop=True)


def save_portfolio(df: pd.DataFrame, filename: str = "portfolio_data.csv") -> str:
    """Save portfolio to CSV in the data directory."""
    filepath = DATA_DIR / filename
    df.to_csv(filepath, index=False)
    return str(filepath)


def save_reconciliation_files() -> Tuple[str, str]:
    """Generate and save dual reconciliation CSV files."""
    int_df, ref_df = generate_reconciliation_datasets()
    int_path = DATA_DIR / "internal_positions.csv"
    ref_path = DATA_DIR / "reference_prices.csv"
    int_df.to_csv(int_path, index=False)
    ref_df.to_csv(ref_path, index=False)
    return str(int_path), str(ref_path)


if __name__ == "__main__":
    print("Generating synthetic portfolio data...")
    portfolio = generate_portfolio()
    path = save_portfolio(portfolio)
    print(f"Generated {len(portfolio)} positions -> {path}")

    print("\nGenerating reconciliation test files...")
    int_path, ref_path = save_reconciliation_files()
    print(f"Internal positions saved -> {int_path}")
    print(f"Reference prices saved  -> {ref_path}")


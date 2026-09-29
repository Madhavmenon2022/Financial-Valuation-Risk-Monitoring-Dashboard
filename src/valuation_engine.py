"""
Valuation Engine
=================
Core calculation module that computes recorded values, reference values,
absolute differences and percentage differences for each position.

This module contains pure financial calculation logic with no side effects.
"""

import numpy as np
import pandas as pd
from typing import Tuple


def calculate_position_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate valuation metrics for each position.

    Adds the following columns:
    - recorded_value:   quantity × recorded_price
    - reference_value:  quantity × reference_price
    - absolute_diff:    |recorded_value - reference_value|
    - percentage_diff:  (absolute_diff / reference_value) × 100

    Parameters
    ----------
    df : pd.DataFrame
        Portfolio data with quantity, recorded_price, reference_price columns.

    Returns
    -------
    pd.DataFrame
        Input DataFrame enriched with valuation columns.
    """
    result = df.copy()

    result["recorded_value"] = result["quantity"] * result["recorded_price"]
    result["reference_value"] = result["quantity"] * result["reference_price"]

    result["absolute_diff"] = (result["recorded_value"] - result["reference_value"]).abs()

    # Percentage difference: guard against division by zero
    pct_series = np.where(
        result["reference_value"].abs() > 1e-10,
        (result["absolute_diff"] / result["reference_value"].abs()) * 100,
        np.where(result["absolute_diff"].abs() > 1e-10, 100.0, 0.0)
    )
    result["percentage_diff"] = pd.Series(pct_series, index=result.index, dtype=float).round(4)
    result["recorded_value"] = result["recorded_value"].astype(float).round(2)
    result["reference_value"] = result["reference_value"].astype(float).round(2)
    result["absolute_diff"] = result["absolute_diff"].astype(float).round(2)

    return result


def calculate_portfolio_summary(df: pd.DataFrame) -> dict:
    """
    Compute aggregate portfolio-level metrics.

    Parameters
    ----------
    df : pd.DataFrame
        Valued portfolio (must have recorded_value, reference_value columns).

    Returns
    -------
    dict
        Summary statistics including total values, mean/max deviations, etc.
    """
    valid = df.dropna(subset=["recorded_value", "reference_value"])

    total_recorded = valid["recorded_value"].sum()
    total_reference = valid["reference_value"].sum()
    total_abs_diff = valid["absolute_diff"].sum()

    portfolio_pct_diff = (
        (abs(total_recorded - total_reference) / abs(total_reference) * 100)
        if abs(total_reference) > 1e-10 else 0.0
    )

    return {
        "total_positions": len(df),
        "valid_positions": len(valid),
        "total_recorded_value": round(total_recorded, 2),
        "total_reference_value": round(total_reference, 2),
        "total_absolute_diff": round(total_abs_diff, 2),
        "portfolio_pct_diff": round(portfolio_pct_diff, 4),
        "mean_pct_diff": round(valid["percentage_diff"].mean(), 4) if len(valid) > 0 else 0.0,
        "median_pct_diff": round(valid["percentage_diff"].median(), 4) if len(valid) > 0 else 0.0,
        "max_pct_diff": round(valid["percentage_diff"].max(), 4) if len(valid) > 0 else 0.0,
        "std_pct_diff": round(valid["percentage_diff"].std(), 4) if len(valid) > 0 else 0.0,
    }


def calculate_asset_class_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute valuation summary grouped by asset class.

    Parameters
    ----------
    df : pd.DataFrame
        Valued portfolio DataFrame.

    Returns
    -------
    pd.DataFrame
        Aggregated metrics per asset class.
    """
    valid = df.dropna(subset=["recorded_value", "reference_value"])

    if len(valid) == 0:
        return pd.DataFrame()

    summary = valid.groupby("asset_class").agg(
        position_count=("position_id", "count"),
        total_recorded_value=("recorded_value", "sum"),
        total_reference_value=("reference_value", "sum"),
        total_absolute_diff=("absolute_diff", "sum"),
        mean_pct_diff=("percentage_diff", "mean"),
        max_pct_diff=("percentage_diff", "max"),
    ).round(2)

    summary = summary.sort_values("total_recorded_value", ascending=False)
    return summary.reset_index()


def calculate_counterparty_exposure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute exposure summary grouped by counterparty.

    Parameters
    ----------
    df : pd.DataFrame
        Valued portfolio DataFrame.

    Returns
    -------
    pd.DataFrame
        Aggregated exposure per counterparty.
    """
    valid = df.dropna(subset=["recorded_value", "reference_value"])

    if len(valid) == 0:
        return pd.DataFrame()

    exposure = valid.groupby("counterparty").agg(
        position_count=("position_id", "count"),
        total_recorded_value=("recorded_value", "sum"),
        total_absolute_diff=("absolute_diff", "sum"),
        mean_pct_diff=("percentage_diff", "mean"),
    ).round(2)

    exposure = exposure.sort_values("total_recorded_value", ascending=False)
    return exposure.reset_index()

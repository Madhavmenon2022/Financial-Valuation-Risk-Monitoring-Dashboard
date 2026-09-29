"""
Export Manager
===============
Exports exception reports and Power BI-ready datasets to Excel and CSV.
Produces professionally formatted multi-sheet Excel workbooks and clean CSV files.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    EXPORTS_DIR, EXCEL_EXPORT_FILENAME, CSV_EXPORT_FILENAME, SUMMARY_CSV_FILENAME
)


def export_exception_report_excel(
    portfolio_df: pd.DataFrame,
    exceptions_df: pd.DataFrame,
    summary: dict,
    asset_summary: pd.DataFrame,
    filepath: str = None,
) -> str:
    """
    Export a multi-sheet Excel workbook containing:
      - Executive Summary
      - Full Portfolio Data
      - Exception Details
      - Asset Class Summary

    Parameters
    ----------
    portfolio_df : pd.DataFrame
        Full valued portfolio.
    exceptions_df : pd.DataFrame
        Exception report from run_all_controls().
    summary : dict
        Portfolio summary metrics.
    asset_summary : pd.DataFrame
        Asset class aggregated summary.
    filepath : str, optional
        Output path. Defaults to exports/valuation_exception_report.xlsx.

    Returns
    -------
    str
        Path to the saved Excel file.
    """
    if filepath is None:
        filepath = str(EXPORTS_DIR / EXCEL_EXPORT_FILENAME)

    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        workbook = writer.book

        # ── Formats ─────────────────────────────────────────────────────────
        header_fmt = workbook.add_format({
            "bold": True,
            "font_size": 12,
            "bg_color": "#1B2838",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
        })
        title_fmt = workbook.add_format({
            "bold": True,
            "font_size": 16,
            "font_color": "#1B2838",
        })
        subtitle_fmt = workbook.add_format({
            "bold": True,
            "font_size": 11,
            "font_color": "#4A6785",
        })
        number_fmt = workbook.add_format({"num_format": "#,##0.00"})
        pct_fmt = workbook.add_format({"num_format": "0.00%"})
        critical_fmt = workbook.add_format({
            "bg_color": "#FF4444",
            "font_color": "#FFFFFF",
            "bold": True,
        })
        high_fmt = workbook.add_format({
            "bg_color": "#FF8800",
            "font_color": "#FFFFFF",
            "bold": True,
        })
        warning_fmt = workbook.add_format({
            "bg_color": "#FFCC00",
            "font_color": "#000000",
        })

        # ── Sheet 1: Executive Summary ──────────────────────────────────────
        ws_summary = workbook.add_worksheet("Executive Summary")
        writer.sheets["Executive Summary"] = ws_summary

        ws_summary.set_column("A:A", 35)
        ws_summary.set_column("B:B", 25)

        ws_summary.write("A1", "Financial Valuation & Risk Monitoring", title_fmt)
        ws_summary.write("A2", f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_fmt)
        ws_summary.write("A3", "This report is generated from synthetic data only.", subtitle_fmt)

        row = 5
        metrics = [
            ("Total Positions", summary.get("total_positions", 0)),
            ("Valid Positions", summary.get("valid_positions", 0)),
            ("Total Recorded Value", f"${summary.get('total_recorded_value', 0):,.2f}"),
            ("Total Reference Value", f"${summary.get('total_reference_value', 0):,.2f}"),
            ("Total Absolute Difference", f"${summary.get('total_absolute_diff', 0):,.2f}"),
            ("Portfolio % Difference", f"{summary.get('portfolio_pct_diff', 0):.4f}%"),
            ("Mean Position % Diff", f"{summary.get('mean_pct_diff', 0):.4f}%"),
            ("Max Position % Diff", f"{summary.get('max_pct_diff', 0):.4f}%"),
        ]
        for label, value in metrics:
            ws_summary.write(row, 0, label, subtitle_fmt)
            ws_summary.write(row, 1, str(value))
            row += 1

        # ── Sheet 2: Portfolio Data ─────────────────────────────────────────
        portfolio_export = portfolio_df.copy()
        portfolio_export.to_excel(writer, sheet_name="Portfolio Data", index=False, startrow=1)

        ws_port = writer.sheets["Portfolio Data"]
        for col_num, col_name in enumerate(portfolio_export.columns):
            ws_port.write(0, col_num, col_name, header_fmt)
            ws_port.set_column(col_num, col_num, max(len(str(col_name)) + 4, 15))

        # ── Sheet 3: Exception Report ───────────────────────────────────────
        if len(exceptions_df) > 0:
            exc_export = exceptions_df.copy()
            exc_export.to_excel(writer, sheet_name="Exceptions", index=False, startrow=1)

            ws_exc = writer.sheets["Exceptions"]
            for col_num, col_name in enumerate(exc_export.columns):
                ws_exc.write(0, col_num, col_name, header_fmt)
                ws_exc.set_column(col_num, col_num, max(len(str(col_name)) + 4, 15))

            # Apply conditional formatting to severity column
            sev_col = list(exc_export.columns).index("severity") if "severity" in exc_export.columns else -1
            if sev_col >= 0:
                for row_idx in range(len(exc_export)):
                    sev = exc_export.iloc[row_idx]["severity"]
                    fmt = {"Critical": critical_fmt, "High": high_fmt, "Warning": warning_fmt}.get(sev)
                    if fmt:
                        ws_exc.write(row_idx + 2, sev_col, sev, fmt)

        # ── Sheet 4: Asset Class Summary ────────────────────────────────────
        if len(asset_summary) > 0:
            asset_summary.to_excel(writer, sheet_name="Asset Summary", index=False, startrow=1)
            ws_asset = writer.sheets["Asset Summary"]
            for col_num, col_name in enumerate(asset_summary.columns):
                ws_asset.write(0, col_num, col_name, header_fmt)
                ws_asset.set_column(col_num, col_num, max(len(str(col_name)) + 4, 15))

    return filepath


def export_powerbi_csv(
    portfolio_df: pd.DataFrame,
    exceptions_df: pd.DataFrame,
    filepath: str = None,
) -> str:
    """
    Export a flattened, Power BI-optimized CSV dataset.

    Merges portfolio data with exception flags for direct import into Power BI.

    Parameters
    ----------
    portfolio_df : pd.DataFrame
        Full valued portfolio.
    exceptions_df : pd.DataFrame
        Exception report.
    filepath : str, optional
        Output path. Defaults to exports/powerbi_dataset.csv.

    Returns
    -------
    str
        Path to the saved CSV file.
    """
    if filepath is None:
        filepath = str(EXPORTS_DIR / CSV_EXPORT_FILENAME)

    # Create exception flags per position
    if len(exceptions_df) > 0:
        exc_flags = exceptions_df.groupby("position_id").agg(
            exception_types=("exception_type", lambda x: "|".join(sorted(x.unique()))),
            max_severity=("severity", lambda x: _max_severity(x)),
            exception_count=("exception_type", "count"),
        ).reset_index()

        merged = portfolio_df.merge(exc_flags, on="position_id", how="left")
    else:
        merged = portfolio_df.copy()
        merged["exception_types"] = None
        merged["max_severity"] = None
        merged["exception_count"] = 0

    merged["has_exception"] = merged["exception_types"].notna()
    merged["exception_count"] = merged["exception_count"].fillna(0).astype(int)

    merged.to_csv(filepath, index=False)
    return filepath


def export_summary_csv(
    summary: dict,
    asset_summary: pd.DataFrame,
    exception_summary: dict,
    filepath: str = None,
) -> str:
    """
    Export portfolio and exception summary metrics to CSV.

    Parameters
    ----------
    summary : dict
        Portfolio summary from valuation_engine.
    asset_summary : pd.DataFrame
        Asset class summary.
    exception_summary : dict
        Exception summary from exception_detector.
    filepath : str, optional
        Output path.

    Returns
    -------
    str
        Path to the saved CSV.
    """
    if filepath is None:
        filepath = str(EXPORTS_DIR / SUMMARY_CSV_FILENAME)

    rows = []
    for key, value in summary.items():
        rows.append({"metric": key, "value": value, "category": "Portfolio"})

    for key, value in exception_summary.items():
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                rows.append({
                    "metric": f"{key}.{sub_key}",
                    "value": sub_val,
                    "category": "Exceptions",
                })
        else:
            rows.append({"metric": key, "value": value, "category": "Exceptions"})

    pd.DataFrame(rows).to_csv(filepath, index=False)
    return filepath


def export_reconciliation_report_excel(
    rec_results: dict,
    filepath: str = None,
) -> str:
    """
    Export a multi-sheet Excel reconciliation report containing:
      - Reconciliation Summary
      - Matched Positions
      - Discrepancies & Exceptions
      - Unmatched Internal Positions
      - Unmatched Reference Prices

    Parameters
    ----------
    rec_results : dict
        Output dictionary from run_reconciliation().
    filepath : str, optional
        Output Excel file path. Defaults to exports/reconciliation_report.xlsx.

    Returns
    -------
    str
        Path to saved Excel file.
    """
    if filepath is None:
        filepath = str(EXPORTS_DIR / "reconciliation_report.xlsx")

    summary = rec_results.get("summary", {})
    matched_df = rec_results.get("matched_df", pd.DataFrame())
    exceptions_df = rec_results.get("exceptions_df", pd.DataFrame())
    unmatched_int = rec_results.get("unmatched_internal", pd.DataFrame())
    unmatched_ref = rec_results.get("unmatched_reference", pd.DataFrame())

    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        workbook = writer.book

        header_fmt = workbook.add_format({
            "bold": True,
            "font_size": 11,
            "bg_color": "#1B2838",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
        })
        title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#1B2838"})
        subtitle_fmt = workbook.add_format({"bold": True, "font_size": 11, "font_color": "#4A6785"})

        # Sheet 1: Executive Summary
        ws_sum = workbook.add_worksheet("Reconciliation Summary")
        writer.sheets["Reconciliation Summary"] = ws_sum
        ws_sum.set_column("A:A", 35)
        ws_sum.set_column("B:B", 25)

        ws_sum.write("A1", "Automated Reconciliation Report", title_fmt)
        ws_sum.write("A2", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_fmt)

        row = 4
        for k, v in summary.items():
            label = k.replace("_", " ").title()
            val_str = f"${v:,.2f}" if "usd" in k else (f"{v}%" if "pct" in k else f"{v}")
            ws_sum.write(row, 0, label, subtitle_fmt)
            ws_sum.write(row, 1, val_str)
            row += 1

        # Sheet 2: Matched Positions
        if len(matched_df) > 0:
            matched_df.to_excel(writer, sheet_name="Matched Positions", index=False, startrow=1)
            ws_m = writer.sheets["Matched Positions"]
            for col_num, col_name in enumerate(matched_df.columns):
                ws_m.write(0, col_num, col_name, header_fmt)
                ws_m.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

        # Sheet 3: Discrepancies & Exceptions
        if len(exceptions_df) > 0:
            exceptions_df.to_excel(writer, sheet_name="Reconciliation Exceptions", index=False, startrow=1)
            ws_e = writer.sheets["Reconciliation Exceptions"]
            for col_num, col_name in enumerate(exceptions_df.columns):
                ws_e.write(0, col_num, col_name, header_fmt)
                ws_e.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

        # Sheet 4: Unmatched Internal Positions
        if len(unmatched_int) > 0:
            unmatched_int.to_excel(writer, sheet_name="Unmatched Internal", index=False, startrow=1)
            ws_ui = writer.sheets["Unmatched Internal"]
            for col_num, col_name in enumerate(unmatched_int.columns):
                ws_ui.write(0, col_num, col_name, header_fmt)
                ws_ui.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

        # Sheet 5: Unmatched Reference Prices
        if len(unmatched_ref) > 0:
            unmatched_ref.to_excel(writer, sheet_name="Unmatched Reference", index=False, startrow=1)
            ws_ur = writer.sheets["Unmatched Reference"]
            for col_num, col_name in enumerate(unmatched_ref.columns):
                ws_ur.write(0, col_num, col_name, header_fmt)
                ws_ur.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

    return filepath


def _max_severity(severities) -> str:
    """Return the highest severity from a collection."""
    order = {"Critical": 0, "High": 1, "Warning": 2}
    return min(severities, key=lambda s: order.get(s, 99))

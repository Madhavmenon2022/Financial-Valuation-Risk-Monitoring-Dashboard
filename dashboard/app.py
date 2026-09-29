"""
Financial Valuation & Risk Monitoring Dashboard
=================================================
Streamlit-based professional dashboard for daily valuation control,
automated reconciliation, exception management workflow, and audit trail.

Launch: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_generator import (
    generate_portfolio,
    save_portfolio,
    generate_reconciliation_datasets
)
from src.valuation_engine import (
    calculate_position_values,
    calculate_portfolio_summary,
    calculate_asset_class_summary,
    calculate_counterparty_exposure,
)
from src.exception_detector import run_all_controls, get_exception_summary
from src.exception_workflow import (
    change_exception_status,
    bulk_update_status,
    add_investigation_note,
    get_persisted_exceptions,
    get_workflow_kpis,
)
from src.reconciliation_engine import run_reconciliation
from src.database import get_audit_trail, init_db
from src.export_manager import (
    export_exception_report_excel,
    export_powerbi_csv,
    export_summary_csv,
    export_reconciliation_report_excel,
)
from src.ai_summary import generate_exception_summary
from config.settings import (
    DEFAULT_THRESHOLD_PCT,
    WARNING_THRESHOLD_PCT,
    CRITICAL_THRESHOLD_PCT,
    EXPORTS_DIR,
    DB_PATH,
)


# ─── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial Valuation & Risk Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database schema
init_db()

# ─── Custom Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --primary: #8B5CF6;
        --primary-light: #C084FC;
        --accent-green: #10B981;
        --accent-rose: #F43F5E;
        --accent-amber: #F59E0B;
        --accent-cyan: #06B6D4;
        --accent-pink: #EC4899;
        --surface: #131B2E;
        --surface-elevated: #1E293B;
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
    }

    html, body, p, label, .stMarkdown, button, input {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    /* Preserve Streamlit Material Icons for collapse button & header icons */
    [data-testid="stSidebarCollapseButton"] *,
    [data-testid="stHeader"] *,
    [class*="material-symbols"],
    [class*="MaterialSymbols"],
    [data-testid="stIconMaterial"],
    i.material-icons {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* Repeating Rupee Symbol Watermark Pattern */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0B0F19 !important;
        background-image: url("data:image/svg+xml,%3Csvg width='120' height='120' viewBox='0 0 120 120' xmlns='http://www.w3.org/2000/svg'%3E%3Ctext x='20' y='50' fill='%238B5CF6' fill-opacity='0.05' font-family='Arial, sans-serif' font-size='38' font-weight='bold'%3E₹%3C/text%3E%3Ctext x='75' y='105' fill='%2310B981' fill-opacity='0.05' font-family='Arial, sans-serif' font-size='38' font-weight='bold'%3E₹%3C/text%3E%3C/svg%3E") !important;
        background-repeat: repeat !important;
        background-attachment: fixed !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Header banner */
    .dashboard-header {
        background: linear-gradient(135deg, #1E1B4B 0%, #4C1D95 35%, #7C3AED 70%, #06B6D4 100%);
        border-radius: 20px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 12px 40px rgba(124, 58, 237, 0.25);
        border: 1px solid rgba(192, 132, 252, 0.3);
        position: relative;
        overflow: hidden;
    }
    .dashboard-header::after {
        content: "₹";
        position: absolute;
        right: 20px;
        bottom: -20px;
        font-size: 140px;
        font-weight: 800;
        color: rgba(255, 255, 255, 0.06);
        pointer-events: none;
    }
    .dashboard-header h1 {
        color: #FFFFFF;
        font-family: 'Space Grotesk', 'Outfit', sans-serif !important;
        font-size: 2rem;
        font-weight: 700;
        margin: 0 0 0.4rem 0;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    .dashboard-header p {
        color: #E9D5FF;
        font-size: 0.95rem;
        margin: 0;
        font-weight: 500;
    }

    /* Glassmorphic KPI Cards */
    .kpi-card {
        background: rgba(19, 27, 46, 0.85);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 16px;
        padding: 1.3rem 1.4rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease, box-shadow 0.25s ease;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        border-color: rgba(192, 132, 252, 0.6);
        box-shadow: 0 14px 40px rgba(139, 92, 246, 0.3);
    }
    .kpi-label {
        color: #94A3B8;
        font-size: 0.76rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        font-family: 'Space Grotesk', 'Outfit', sans-serif !important;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
        font-variant-numeric: tabular-nums;
    }
    .kpi-sub {
        color: #64748B;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .kpi-green { color: #10B981; text-shadow: 0 0 12px rgba(16, 185, 129, 0.3); }
    .kpi-red { color: #F43F5E; text-shadow: 0 0 12px rgba(244, 63, 94, 0.3); }
    .kpi-amber { color: #F59E0B; text-shadow: 0 0 12px rgba(245, 158, 11, 0.3); }
    .kpi-blue { color: #8B5CF6; text-shadow: 0 0 12px rgba(139, 92, 246, 0.3); }
    .kpi-cyan { color: #06B6D4; text-shadow: 0 0 12px rgba(6, 182, 212, 0.3); }

    .section-header {
        color: #F8FAFC;
        font-family: 'Space Grotesk', 'Outfit', sans-serif !important;
        font-size: 1.2rem;
        font-weight: 700;
        margin: 1.4rem 0 0.9rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(139, 92, 246, 0.4);
        letter-spacing: -0.01em;
    }

    /* Vibrant Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(19, 27, 46, 0.6);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid rgba(139, 92, 246, 0.2);
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 8px;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700;
        font-size: 0.88rem;
        color: #94A3B8;
        padding: 0 18px;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #7C3AED, #06B6D4) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 16px rgba(124, 58, 237, 0.4);
    }

    /* Styled Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #7C3AED 0%, #4F46E5 50%, #06B6D4 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.4rem;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700;
        box-shadow: 0 4px 16px rgba(124, 58, 237, 0.3);
        transition: all 0.25s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(124, 58, 237, 0.5);
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .disclaimer-banner {
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.4);
        border-radius: 10px;
        padding: 0.6rem 1rem;
        font-size: 0.78rem;
        color: #FCD34D;
        margin-bottom: 1.1rem;
    }
</style>
""", unsafe_allow_html=True)


# ─── Helper Functions ──────────────────────────────────────────────────────────

def render_kpi_card(label: str, value: str, sub: str = "", color_class: str = "kpi-blue"):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color_class}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


def format_currency(val: float) -> str:
    if abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    elif abs(val) >= 1e3:
        return f"${val/1e3:.1f}K"
    else:
        return f"${val:,.2f}"


PLOTLY_COLORS = {
    "primary": "#8B5CF6",
    "accent1": "#10B981",
    "accent2": "#F59E0B",
    "accent3": "#F43F5E",
    "accent4": "#06B6D4",
    "accent5": "#EC4899",
    "bg": "#0B0F19",
    "surface": "#131B2E",
    "text": "#F8FAFC",
    "grid": "#1E293B",
}

COLOR_SEQUENCE = [
    PLOTLY_COLORS["primary"],
    PLOTLY_COLORS["accent1"],
    PLOTLY_COLORS["accent4"],
    PLOTLY_COLORS["accent2"],
    PLOTLY_COLORS["accent5"],
    PLOTLY_COLORS["accent3"],
]

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(19, 27, 46, 0.8)",
    plot_bgcolor="rgba(19, 27, 46, 0.9)",
    font=dict(family="Outfit, Space Grotesk, sans-serif", color=PLOTLY_COLORS["text"]),
    margin=dict(l=40, r=40, t=45, b=40),
    xaxis=dict(gridcolor=PLOTLY_COLORS["grid"], zerolinecolor=PLOTLY_COLORS["grid"]),
    yaxis=dict(gridcolor=PLOTLY_COLORS["grid"], zerolinecolor=PLOTLY_COLORS["grid"]),
)


# ─── Main Application ──────────────────────────────────────────────────────────

def main():
    st.markdown("""
    <div class="dashboard-header">
        <h1>📊 Financial Valuation, Risk & Reconciliation Control System</h1>
        <p>Daily valuation control • Automated position & reference reconciliation • Exception workflow & audit trail</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="disclaimer-banner">
        ⚠️ <strong>Disclaimer:</strong> Synthetic demonstration data only. Does not provide real regulatory compliance certification or investment advice.
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar Controls ────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Control Settings")
        st.markdown("---")

        st.markdown("###  Threshold Settings")
        warning_pct = st.slider("Warning Threshold (%)", 0.5, 10.0, WARNING_THRESHOLD_PCT, 0.5)
        default_pct = st.slider("High Threshold (%)", 1.0, 15.0, DEFAULT_THRESHOLD_PCT, 0.5)
        critical_pct = st.slider("Critical Threshold (%)", 2.0, 25.0, CRITICAL_THRESHOLD_PCT, 1.0)

        st.markdown("---")
        st.markdown("###  Valuation Data Parameters")
        num_positions = st.number_input("Number of Positions", 50, 5000, 500, 50)
        random_seed = st.number_input("Random Seed", 1, 9999, 42)
        regenerate = st.button("🔄 Regenerate Valuation Data", use_container_width=True)

        st.markdown("---")
        st.markdown("###  AI Summary Options")
        enable_ai = st.checkbox("Enable OpenAI LLM Summary", value=False)

        st.markdown("---")
        st.markdown("###  Analyst Persona")
        analyst_id = st.text_input("Analyst ID / Name", value="Analyst_Senior")

    # ── Pipeline Execution ──────────────────────────────────────────────────
    @st.cache_data
    def run_valuation_pipeline(n_positions, seed, warn_pct, def_pct, crit_pct):
        portfolio = generate_portfolio(num_positions=n_positions, seed=seed)
        valued = calculate_position_values(portfolio)
        exceptions = run_all_controls(valued, warn_pct, def_pct, crit_pct)
        port_summary = calculate_portfolio_summary(valued)
        asset_summary = calculate_asset_class_summary(valued)
        counterparty_exp = calculate_counterparty_exposure(valued)
        exc_summary = get_exception_summary(exceptions)
        return valued, exceptions, port_summary, asset_summary, counterparty_exp, exc_summary

    if regenerate:
        st.cache_data.clear()

    valued, exceptions, port_summary, asset_summary, counterparty_exp, exc_summary = (
        run_valuation_pipeline(num_positions, random_seed, warning_pct, default_pct, critical_pct)
    )

    # ── Top-Level Tabs Navigation ──────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Portfolio Valuation",
        "🔄 Automated Reconciliation",
        "🚨 Exception Workflow Management",
        "📜 Audit Trail & History",
    ])

    # =========================================================================
    # TAB 1: PORTFOLIO VALUATION DASHBOARD
    # =========================================================================
    with tab1:
        st.markdown('<div class="section-header">📋 Valuation Overview</div>', unsafe_allow_html=True)

        kpi_cols = st.columns(5)
        with kpi_cols[0]:
            st.markdown(render_kpi_card("Recorded Value", format_currency(port_summary["total_recorded_value"]), f"{port_summary['total_positions']} positions", "kpi-blue"), unsafe_allow_html=True)
        with kpi_cols[1]:
            st.markdown(render_kpi_card("Reference Value", format_currency(port_summary["total_reference_value"]), "Market benchmark", "kpi-green"), unsafe_allow_html=True)
        with kpi_cols[2]:
            st.markdown(render_kpi_card("Total Variance", format_currency(port_summary["total_absolute_diff"]), f"{port_summary['portfolio_pct_diff']:.3f}% overall", "kpi-amber"), unsafe_allow_html=True)
        with kpi_cols[3]:
            st.markdown(render_kpi_card("Flagged Exceptions", str(exc_summary["total_exceptions"]), f"{exc_summary['critical_count']} critical", "kpi-red" if exc_summary["critical_count"] > 0 else "kpi-green"), unsafe_allow_html=True)
        with kpi_cols[4]:
            st.markdown(render_kpi_card("Max Deviation", f"{port_summary['max_pct_diff']:.1f}%", f"Mean: {port_summary['mean_pct_diff']:.2f}%", "kpi-red" if port_summary["max_pct_diff"] > critical_pct else "kpi-amber"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            if len(asset_summary) > 0:
                fig_donut = go.Figure(data=[go.Pie(
                    labels=asset_summary["asset_class"],
                    values=asset_summary["total_recorded_value"],
                    hole=0.55,
                    marker=dict(colors=COLOR_SEQUENCE),
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Value: $%{value:,.0f}<extra></extra>",
                )])
                fig_donut.update_layout(title=dict(text="Portfolio Composition by Asset Class", font=dict(size=14)), **PLOTLY_LAYOUT, height=360)
                st.plotly_chart(fig_donut, use_container_width=True)

        with chart_col2:
            if len(asset_summary) > 0:
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=asset_summary["asset_class"], y=asset_summary["mean_pct_diff"], name="Mean % Diff", marker_color=PLOTLY_COLORS["primary"]))
                fig_bar.add_trace(go.Bar(x=asset_summary["asset_class"], y=asset_summary["max_pct_diff"], name="Max % Diff", marker_color=PLOTLY_COLORS["accent3"]))
                fig_bar.update_layout(title=dict(text="Valuation Differences by Asset Class", font=dict(size=14)), barmode="group", **PLOTLY_LAYOUT, height=360)
                st.plotly_chart(fig_bar, use_container_width=True)

        # Scatter Plot
        st.markdown('<div class="section-header">🔍 Position-Level Deviation Scatter</div>', unsafe_allow_html=True)
        valid_pos = valued.dropna(subset=["recorded_value", "reference_value"]).copy()
        if len(valid_pos) > 0:
            fig_scatter = px.scatter(
                valid_pos, x="reference_value", y="recorded_value", color="asset_class", size="percentage_diff",
                color_discrete_sequence=COLOR_SEQUENCE, hover_data=["position_id", "instrument_id", "percentage_diff"]
            )
            fig_scatter.update_layout(title=dict(text="Recorded vs Reference Price (size = deviation %)", font=dict(size=14)), **PLOTLY_LAYOUT, height=400)
            st.plotly_chart(fig_scatter, use_container_width=True)

        # Counterparty Exposure & AI Summary
        cp_col, ai_col = st.columns(2)
        with cp_col:
            st.markdown('<div class="section-header">🏦 Counterparty Exposure</div>', unsafe_allow_html=True)
            if len(counterparty_exp) > 0:
                fig_cp = go.Figure(go.Bar(x=counterparty_exp.head(8)["counterparty"], y=counterparty_exp.head(8)["total_recorded_value"], marker_color=PLOTLY_COLORS["primary"]))
                fig_cp.update_layout(title=dict(text="Top Counterparty Exposures", font=dict(size=14)), **PLOTLY_LAYOUT, height=320)
                st.plotly_chart(fig_cp, use_container_width=True)

        with ai_col:
            st.markdown('<div class="section-header">🤖 Exception Summary</div>', unsafe_allow_html=True)
            ai_text = generate_exception_summary(exceptions, exc_summary, port_summary, use_ai=enable_ai)
            st.markdown(ai_text)

        # Export Buttons
        st.markdown('<div class="section-header">📥 Export Valuation Reports</div>', unsafe_allow_html=True)
        e_col1, e_col2, e_col3 = st.columns(3)
        with e_col1:
            if st.button("📊 Export Multi-Sheet Excel Report", use_container_width=True):
                path = export_exception_report_excel(valued, exceptions, port_summary, asset_summary)
                st.success(f"Excel report saved: `{path}`")
        with e_col2:
            if st.button("📈 Export Power BI CSV Dataset", use_container_width=True):
                path = export_powerbi_csv(valued, exceptions)
                st.success(f"Power BI CSV saved: `{path}`")
        with e_col3:
            if st.button("📋 Export Summary CSV", use_container_width=True):
                path = export_summary_csv(port_summary, asset_summary, exc_summary)
                st.success(f"Summary CSV saved: `{path}`")

    # =========================================================================
    # TAB 2: AUTOMATED RECONCILIATION ENGINE
    # =========================================================================
    with tab2:
        st.markdown('<div class="section-header">🔄 Automated Position & Reference Price Reconciliation</div>', unsafe_allow_html=True)
        st.write("Upload separate **Internal Positions** and **Reference Market Prices** files (CSV or Excel) to match records and detect missing, stale, or mismatched prices.")

        up_col1, up_col2 = st.columns(2)
        with up_col1:
            internal_file = st.file_uploader("Internal Positions File (CSV/XLSX)", type=["csv", "xlsx"])
        with up_col2:
            reference_file = st.file_uploader("Reference Market Prices File (CSV/XLSX)", type=["csv", "xlsx"])

        stale_threshold = st.slider("Stale Market Price Threshold (Days)", 0, 10, 1, help="Flag reference prices whose date is older than internal position date")

        # Handle data load
        int_df, ref_df = None, None
        if internal_file:
            try:
                int_df = pd.read_csv(internal_file) if internal_file.name.endswith(".csv") else pd.read_excel(internal_file)
            except Exception as e:
                st.error(f"Error reading internal file: {e}")

        if reference_file:
            try:
                ref_df = pd.read_csv(reference_file) if reference_file.name.endswith(".csv") else pd.read_excel(reference_file)
            except Exception as e:
                st.error(f"Error reading reference file: {e}")

        load_demo = st.button("🎲 Load Synthetic Demonstration Reconciliation Datasets")
        if load_demo or (int_df is None and ref_df is None):
            int_df, ref_df = generate_reconciliation_datasets(num_positions=300, seed=42)
            if load_demo:
                st.info("Loaded 300 synthetic internal positions and market reference records.")

        if int_df is not None and ref_df is not None:
            with st.spinner("Running automated reconciliation matcher..."):
                rec_results = run_reconciliation(
                    int_df, ref_df, stale_days_threshold=stale_threshold,
                    warning_pct=warning_pct, default_pct=default_pct, critical_pct=critical_pct
                )

            rec_sum = rec_results["summary"]

            # Reconciliation KPIs
            r_kpis = st.columns(6)
            with r_kpis[0]:
                st.markdown(render_kpi_card("Internal Positions", str(rec_sum["total_internal_positions"]), "Source booking", "kpi-blue"), unsafe_allow_html=True)
            with r_kpis[1]:
                st.markdown(render_kpi_card("Reference Feeds", str(rec_sum["total_reference_records"]), "Market data", "kpi-blue"), unsafe_allow_html=True)
            with r_kpis[2]:
                st.markdown(render_kpi_card("Matched Count", str(rec_sum["matched_count"]), f"{rec_sum['match_rate_pct']}% matched", "kpi-green"), unsafe_allow_html=True)
            with r_kpis[3]:
                st.markdown(render_kpi_card("Unmatched Internal", str(rec_sum["unmatched_internal_count"]), "Missing market price", "kpi-red"), unsafe_allow_html=True)
            with r_kpis[4]:
                st.markdown(render_kpi_card("Stale Market Prices", str(rec_sum["stale_price_count"]), f">{stale_threshold} day old", "kpi-amber"), unsafe_allow_html=True)
            with r_kpis[5]:
                st.markdown(render_kpi_card("Reconciliation Exceptions", str(rec_sum["total_exceptions_count"]), format_currency(rec_sum["total_variance_usd"]), "kpi-red"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Sub-tabs for detailed reconciliation inspection
            rt1, rt2, rt3, rt4 = st.tabs(["Matched Positions", "Reconciliation Exceptions", "Unmatched Internal", "Unmatched Reference"])
            with rt1:
                st.dataframe(rec_results["matched_df"], use_container_width=True, height=350)
            with rt2:
                st.dataframe(rec_results["exceptions_df"], use_container_width=True, height=350)
            with rt3:
                st.dataframe(rec_results["unmatched_internal"], use_container_width=True, height=350)
            with rt4:
                st.dataframe(rec_results["unmatched_reference"], use_container_width=True, height=350)

            # Export button
            st.markdown("---")
            if st.button("📥 Export Detailed Excel Reconciliation Report", use_container_width=True):
                rec_path = export_reconciliation_report_excel(rec_results)
                st.success(f"✅ Excel Reconciliation Report exported to: `{rec_path}`")

    # =========================================================================
    # TAB 3: EXCEPTION MANAGEMENT WORKFLOW
    # =========================================================================
    with tab3:
        st.markdown('<div class="section-header">🚨 Exception Lifecycle Management Workflow</div>', unsafe_allow_html=True)
        st.write("Track exception investigation statuses (`Open`, `Under Review`, `Resolved`), assign analyst notes, and maintain SQLite database state.")

        # Workflow KPIs from DB
        wk_kpis = get_workflow_kpis(DB_PATH)
        w_cols = st.columns(5)
        with w_cols[0]:
            st.markdown(render_kpi_card("Total Exceptions", str(wk_kpis["total"]), "Persisted in DB", "kpi-blue"), unsafe_allow_html=True)
        with w_cols[1]:
            st.markdown(render_kpi_card("Open", str(wk_kpis["open"]), "Requires review", "kpi-red"), unsafe_allow_html=True)
        with w_cols[2]:
            st.markdown(render_kpi_card("Under Review", str(wk_kpis["under_review"]), "Investigation active", "kpi-amber"), unsafe_allow_html=True)
        with w_cols[3]:
            st.markdown(render_kpi_card("Resolved", str(wk_kpis["resolved"]), "Approved / closed", "kpi-green"), unsafe_allow_html=True)
        with w_cols[4]:
            st.markdown(render_kpi_card("Resolution Rate", f"{wk_kpis['resolution_rate_pct']}%", "Completion percentage", "kpi-green"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        persisted_df = get_persisted_exceptions(DB_PATH)

        if len(persisted_df) > 0:
            # Filters
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                status_filter = st.multiselect("Status Filter", options=["Open", "Under Review", "Resolved"], default=["Open", "Under Review", "Resolved"])
            with f_col2:
                sev_filter = st.multiselect("Severity Filter", options=persisted_df["severity"].unique().tolist(), default=persisted_df["severity"].unique().tolist())
            with f_col3:
                type_filter = st.multiselect("Type Filter", options=persisted_df["exception_type"].unique().tolist(), default=persisted_df["exception_type"].unique().tolist())
            with f_col4:
                search_text = st.text_input("Search (ID / Instrument / Reason)", "")

            # Apply filters
            filtered_df = persisted_df[
                persisted_df["status"].isin(status_filter) &
                persisted_df["severity"].isin(sev_filter) &
                persisted_df["exception_type"].isin(type_filter)
            ]
            if search_text:
                mask = (
                    filtered_df["exception_id"].str.contains(search_text, case=False, na=False) |
                    filtered_df["instrument_id"].str.contains(search_text, case=False, na=False) |
                    filtered_df["reason"].str.contains(search_text, case=False, na=False)
                )
                filtered_df = filtered_df[mask]

            st.markdown(f"**Showing {len(filtered_df)} of {len(persisted_df)} persistent exceptions**")

            # Table display
            disp_cols = ["exception_id", "position_id", "instrument_id", "exception_type", "severity", "status", "percentage_diff", "reason", "analyst_notes", "created_at", "updated_at"]
            st.dataframe(filtered_df[[c for c in disp_cols if c in filtered_df.columns]], use_container_width=True, height=350)

            # Workflow Action Form
            st.markdown('<div class="section-header">✏️ Update Exception Status & Add Notes</div>', unsafe_allow_html=True)
            act_col1, act_col2 = st.columns([1, 1])

            with act_col1:
                st.markdown("#### Single Exception Action")
                selected_id = st.selectbox("Select Exception ID", options=filtered_df["exception_id"].tolist() if len(filtered_df) > 0 else [])
                new_status = st.selectbox("New Status", options=["Open", "Under Review", "Resolved"])
                analyst_notes_input = st.text_area("Analyst Investigation Notes", placeholder="Enter root cause diagnosis, price override authorization, or remediation steps...")

                if st.button("💾 Save Status Update & Note", use_container_width=True):
                    if selected_id:
                        change_exception_status(selected_id, new_status, analyst_id=analyst_id, notes=analyst_notes_input, db_path=DB_PATH)
                        st.success(f"Updated `{selected_id}` status to `{new_status}`")
                        st.rerun()

            with act_col2:
                st.markdown("#### Bulk Status Action")
                selected_bulk_ids = st.multiselect("Select Exception IDs for Bulk Update", options=filtered_df["exception_id"].tolist())
                bulk_status = st.selectbox("Bulk Target Status", options=["Open", "Under Review", "Resolved"], key="bulk_st")
                bulk_notes = st.text_input("Bulk Action Reason", placeholder="Batch approved after daily pricing meeting...")

                if st.button("⚡ Apply Bulk Status Update", use_container_width=True):
                    if selected_bulk_ids:
                        count = bulk_update_status(selected_bulk_ids, bulk_status, analyst_id=analyst_id, notes=bulk_notes, db_path=DB_PATH)
                        st.success(f"Successfully updated {count} exceptions to `{bulk_status}`")
                        st.rerun()
        else:
            st.info("No exceptions currently recorded in the SQLite database.")

    # =========================================================================
    # TAB 4: AUDIT TRAIL & HISTORICAL LOGS
    # =========================================================================
    with tab4:
        st.markdown('<div class="section-header">📜 Immutable SQLite Audit Trail Logs</div>', unsafe_allow_html=True)
        st.write("View time-stamped history of all exception creation events, status transitions, and analyst investigation notes.")

        audit_df = get_audit_trail(db_path=DB_PATH, limit=500)

        if len(audit_df) > 0:
            a_kpis = st.columns(4)
            with a_kpis[0]:
                st.markdown(render_kpi_card("Total Audit Events", str(len(audit_df)), "Recorded in SQLite", "kpi-blue"), unsafe_allow_html=True)
            with a_kpis[1]:
                st.markdown(render_kpi_card("Creation Events", str((audit_df["action"] == "EXCEPTION_CREATED").sum()), "System generated", "kpi-green"), unsafe_allow_html=True)
            with a_kpis[2]:
                st.markdown(render_kpi_card("Status Changes", str(audit_df["action"].str.contains("STATUS_CHANGE").sum()), "Analyst workflow", "kpi-amber"), unsafe_allow_html=True)
            with a_kpis[3]:
                st.markdown(render_kpi_card("Notes Added", str((audit_df["action"] == "NOTE_ADDED").sum()), "Investigation entries", "kpi-blue"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Audit filters
            flt_col1, flt_col2 = st.columns(2)
            with flt_col1:
                action_filter = st.multiselect("Filter by Action Type", options=audit_df["action"].unique().tolist(), default=audit_df["action"].unique().tolist())
            with flt_col2:
                exc_id_search = st.text_input("Filter by Exception ID", "")

            filtered_audit = audit_df[audit_df["action"].isin(action_filter)]
            if exc_id_search:
                filtered_audit = filtered_audit[filtered_audit["exception_id"].str.contains(exc_id_search, case=False, na=False)]

            st.dataframe(filtered_audit, use_container_width=True, height=450)

            # Export Audit Trail CSV
            st.markdown("---")
            audit_csv = filtered_audit.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Full Audit Trail Log (CSV)", data=audit_csv, file_name=f"audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("No audit logs currently recorded in the SQLite database.")


if __name__ == "__main__":
    main()

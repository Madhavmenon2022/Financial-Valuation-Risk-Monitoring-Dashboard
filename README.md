#     Financial Valuation & Risk Monitoring Dashboard

<div align="center">

**A portfolio-ready Python application simulating a financial institution's daily valuation control, automated reconciliation, exception management workflow, and audit trail process.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/SQLite-Audit%20Trail-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![Power BI](https://img.shields.io/badge/Power%20BI-Ready-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)](https://powerbi.microsoft.com)

</div>

---

## Overview

This application simulates an enterprise-grade **daily valuation control and reconciliation workflow** used by financial institutions to verify recorded portfolio valuations against independent market reference price feeds. It features automated exception detection, exception lifecycle management (`Open`, `Under Review`, `Resolved`), SQLite audit trail persistence, position matching, stale price detection, and an interactive 4-tab Streamlit dashboard.

>  **Disclaimer:** This application uses **synthetic data only** and does not provide real regulatory compliance certification or investment advice. It is designed for educational and portfolio demonstration purposes.

---

## Core Modules & Key Features

### 1. Exception Management Workflow
- **Unique Exception Identifiers:** Every detected discrepancy receives a unique, stable `exception_id` (e.g. `EXC-POS-00001-MP`).
- **Analyst Workflow Lifecycle:** Supports state transitions between **`Open`**, **`Under Review`**, and **`Resolved`**.
- **Analyst Investigation Notes:** Analysts can append timestamped root cause notes and override audit logs.
- **Timestamps:** Tracks creation (`created_at`), update (`updated_at`), and resolution (`resolved_at`) timestamps.

### 2. Automated Position & Reference Reconciliation
- **Dual Dataset Matching:** Accepts separate Internal Position files (CSV/Excel) and Market Reference Price feeds.
- **Record Matching:** Joins records by `instrument_id` and `valuation_date`.
- **Discrepancy Detection:**
  - **Unmatched Internal Positions:** Internal position bookings missing a market reference price.
  - **Unmatched Reference Feeds:** Market reference prices without an internal booking.
  - **Stale Market Prices:** Reference price valuation date is older than position date (configurable threshold).
  - **Price Valuation Mismatches:** Percentage variance exceeds warning/high/critical limits.
- **Downloadable Excel Reconciliation Report:** Generates a multi-sheet Excel workbook with Executive Summary, Matched Positions, Discrepancies, and Unmatched items.

### 3. Immutable SQLite Audit Trail
- **Persistent Storage:** SQLite database (`data/audit_trail.db`) preserves exception states, notes, and history across file uploads or dashboard restarts.
- **Audit Logs:** Log every creation event, status change (`Open` ➔ `Under Review` ➔ `Resolved`), and note addition with analyst IDs and timestamps.
- **Downloadable Audit Trail:** Export complete audit logs to CSV for regulatory compliance documentation.

### 4. 4-Tab Interactive Streamlit Interface
- **Tab 1: Portfolio Valuation Dashboard:** Portfolio KPIs, composition donut chart, asset deviation bar chart, deviation scatter plot, counterparty exposure, AI summary.
- **Tab 2: Automated Reconciliation Engine:** Upload internal & market price files, run automated matching, view reconciliation KPIs, inspect unmatched/stale tables, export Excel report.
- **Tab 3: Exception Workflow Management:** Interactive workflow dashboard, status & severity filters, single & bulk status update forms, analyst note editor.
- **Tab 4: Audit Trail & History:** View chronological SQLite audit events, filter by action or analyst, export audit log.

### 5. AI-Powered Summary (Optional)
- Natural-language exception summaries using OpenAI GPT-4.
- Deterministic rule-based template fallback when AI is disabled or unavailable.

---

## Architecture

```
financial-valuation-dashboard/
├── config/
│   └── settings.py              # Configuration thresholds, DB paths & settings
├── src/
│   ├── database.py              # SQLite database manager for audit trail & persistence
│   ├── data_generator.py        # Synthetic portfolio & dual reconciliation dataset generator
│   ├── valuation_engine.py      # Core valuation calculations & metrics
│   ├── exception_detector.py    # Automated control checks & Exception ID assignment
│   ├── exception_workflow.py    # Analyst status workflow & notes management
│   ├── reconciliation_engine.py # Automated record matcher (internal vs market reference)
│   ├── export_manager.py        # Multi-sheet Excel and CSV export generator
│   └── ai_summary.py            # Optional AI exception summaries
├── dashboard/
│   └── app.py                   # Multi-tab Streamlit dashboard
├── powerbi/
│   ├── POWERBI_GUIDE.md         # Power BI setup instructions
│   └── theme.json               # Power BI color theme
├── tests/
│   ├── test_valuation.py        # Valuation engine unit tests
│   ├── test_exceptions.py       # Exception detection unit tests
│   ├── test_reconciliation.py   # Automated reconciliation unit tests
│   └── test_audit.py            # SQLite database & audit trail unit tests
├── data/                        # Generated CSVs & audit_trail.db
├── exports/                     # Exported Excel & CSV reports
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.9 or higher
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/financial-valuation-dashboard.git
cd financial-valuation-dashboard

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # macOS/Linux
# or
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Dashboard

```bash
# Launch the Streamlit dashboard
streamlit run dashboard/app.py
```
The dashboard will open in your browser at `http://localhost:8501`.

### Running Tests (61 Unit Tests)

```bash
# Run all unit tests
pytest tests/ -v
```

---

## Test Suite Summary

The application includes 61 automated unit tests passing at 100%:

| Test File | Covered Functionality |
| :--- | :--- |
| `tests/test_valuation.py` | Position value math, aggregations, empty DataFrame edge cases |
| `tests/test_exceptions.py` | Automated controls, severity classification, Exception ID assignment |
| `tests/test_reconciliation.py` | Record matching, stale price detection, unmatched records, column alias normalization |
| `tests/test_audit.py` | SQLite database initialization, status workflow, analyst notes, audit logging |

---

## Enterprise Financial Control Workflow

```
1. DATA INTAKE           → Load internal positions & market reference price feeds
2. RECONCILIATION MATCH  → Join records on instrument_id & valuation_date
3. CONTROL CHECKS        → Flag missing, duplicate, stale, and mismatched prices
4. EXCEPTION ID ASSIGN   → Generate unique exception IDs and sync with SQLite DB
5. ANALYST WORKFLOW      → Analysts review exceptions, transition status (Open -> Under Review -> Resolved)
6. AUDIT TRAIL LOGGING   → Record all state changes & analyst notes in SQLite DB
7. MANAGEMENT REPORTING  → Export multi-sheet Excel reports and Power BI datasets
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.9+ | Core application logic |
| **Data Processing** | Pandas, NumPy | Data manipulation and financial calculations |
| **Database** | SQLite3 | Persistent exception state & audit trail logging |
| **UI Framework** | Streamlit | 4-tab interactive web dashboard |
| **Visualizations** | Plotly Express / Graph Objects | Interactive charts and scatter plots |
| **Excel Export** | xlsxwriter, openpyxl | Multi-sheet formatted Excel report generation |
| **BI Integration** | Power BI | DAX measures & enterprise BI theme |
| **Testing** | pytest | Automated test suite (61 tests) |

---

## License

This project is open source and available under the [MIT License](LICENSE).

# Power BI Dashboard Design Guide

## 📊 Building the Financial Valuation Dashboard in Power BI

This guide walks you through importing the exported data, creating DAX measures, and building interactive visualizations for the Financial Valuation & Risk Monitoring Dashboard.

> **Note:** This guide uses exported synthetic data only. The resulting dashboard does not provide real regulatory compliance certification.

---

## 1. Importing Data into Power BI

### Step 1: Open Power BI Desktop
1. Launch **Power BI Desktop**
2. Click **Get Data** → **Text/CSV**

### Step 2: Import the Power BI Dataset
1. Navigate to the `exports/` folder in this project
2. Select `powerbi_dataset.csv` and click **Open**
3. In the preview window, verify:
   - Delimiter: **Comma**
   - Data Type Detection: **Based on entire dataset**
4. Click **Transform Data** to open Power Query Editor

### Step 3: Configure Data Types in Power Query
Apply these data type transformations:

| Column | Type |
|--------|------|
| `position_id` | Text |
| `instrument_id` | Text |
| `asset_class` | Text |
| `counterparty` | Text |
| `currency` | Text |
| `quantity` | Whole Number |
| `recorded_price` | Decimal Number |
| `reference_price` | Decimal Number |
| `recorded_value` | Decimal Number |
| `reference_value` | Decimal Number |
| `absolute_diff` | Decimal Number |
| `percentage_diff` | Decimal Number |
| `valuation_date` | Date |
| `exception_types` | Text |
| `max_severity` | Text |
| `exception_count` | Whole Number |
| `has_exception` | True/False |

### Step 4: Import the Summary CSV (Optional)
1. **Get Data** → **Text/CSV** → Select `portfolio_summary.csv`
2. This provides pre-aggregated metrics for summary cards

### Step 5: Close & Apply
Click **Close & Apply** to load the data into the model.

---

## 2. Creating DAX Measures

Create these DAX measures in Power BI for dynamic calculations:

### Portfolio Metrics
```dax
// Total Portfolio Value (Recorded)
Total Recorded Value = SUM('powerbi_dataset'[recorded_value])

// Total Portfolio Value (Reference)
Total Reference Value = SUM('powerbi_dataset'[reference_value])

// Total Absolute Variance
Total Variance = SUM('powerbi_dataset'[absolute_diff])

// Portfolio-Level % Difference
Portfolio Pct Diff = 
    DIVIDE(
        ABS([Total Recorded Value] - [Total Reference Value]),
        ABS([Total Reference Value]),
        0
    ) * 100

// Total Position Count
Total Positions = COUNTROWS('powerbi_dataset')
```

### Exception Metrics
```dax
// Total Exceptions
Total Exceptions = 
    COUNTROWS(
        FILTER('powerbi_dataset', 'powerbi_dataset'[has_exception] = TRUE())
    )

// Exception Rate
Exception Rate = 
    DIVIDE([Total Exceptions], [Total Positions], 0) * 100

// Critical Exceptions
Critical Exceptions = 
    COUNTROWS(
        FILTER('powerbi_dataset', 'powerbi_dataset'[max_severity] = "Critical")
    )

// High Severity Exceptions
High Exceptions = 
    COUNTROWS(
        FILTER('powerbi_dataset', 'powerbi_dataset'[max_severity] = "High")
    )

// Warning Exceptions
Warning Exceptions = 
    COUNTROWS(
        FILTER('powerbi_dataset', 'powerbi_dataset'[max_severity] = "Warning")
    )
```

### Advanced Analytics
```dax
// Average Deviation %
Avg Deviation Pct = AVERAGE('powerbi_dataset'[percentage_diff])

// Max Deviation %
Max Deviation Pct = MAX('powerbi_dataset'[percentage_diff])

// Positions Within Threshold (< 5%)
Positions Within Threshold = 
    COUNTROWS(
        FILTER(
            'powerbi_dataset', 
            'powerbi_dataset'[percentage_diff] <= 5 
            && 'powerbi_dataset'[has_exception] = FALSE()
        )
    )

// Compliance Rate
Compliance Rate = 
    DIVIDE([Positions Within Threshold], [Total Positions], 0) * 100

// Exposure by Counterparty (use in matrix visuals)
Counterparty Exposure = 
    SUMX(
        FILTER('powerbi_dataset', NOT(ISBLANK('powerbi_dataset'[recorded_value]))),
        'powerbi_dataset'[recorded_value]
    )
```

### Conditional Formatting Measures
```dax
// Severity Color
Severity Color = 
    SWITCH(
        SELECTEDVALUE('powerbi_dataset'[max_severity]),
        "Critical", "#EF4444",
        "High", "#F59E0B",
        "Warning", "#FACC15",
        "#10B981"
    )

// Deviation RAG Status
Deviation RAG = 
    SWITCH(
        TRUE(),
        [Max Deviation Pct] >= 10, "Red",
        [Max Deviation Pct] >= 5, "Amber",
        "Green"
    )
```

---

## 3. Building the Dashboard Layout

### Recommended Page Structure

#### Page 1: Executive Summary
Create a high-level overview dashboard with these visuals:

| Visual | Type | Fields |
|--------|------|--------|
| **Portfolio Value** | Card | `[Total Recorded Value]` |
| **Reference Value** | Card | `[Total Reference Value]` |
| **Total Variance** | Card | `[Total Variance]` |
| **Exception Count** | Card | `[Total Exceptions]` |
| **Compliance Rate** | Gauge | `[Compliance Rate]` (max: 100) |
| **Asset Allocation** | Donut Chart | Legend: `asset_class`, Values: `recorded_value` |
| **Deviation by Asset** | Clustered Bar | Axis: `asset_class`, Values: `[Avg Deviation Pct]`, `[Max Deviation Pct]` |
| **Severity Breakdown** | Pie Chart | Legend: `max_severity`, Values: Count of `position_id` |

**Design Tips:**
- Use a dark background (#1E1E2E) with light text (#E2E8F0)
- Apply the indigo accent color (#6366F1) for key metrics
- Add the report date as a text box at the top

#### Page 2: Exception Deep Dive
Detailed exception analysis:

| Visual | Type | Fields |
|--------|------|--------|
| **Exception Table** | Table | `position_id`, `instrument_id`, `asset_class`, `exception_types`, `max_severity`, `percentage_diff` |
| **Exceptions by Type** | Horizontal Bar | Axis: `exception_types`, Values: Count |
| **Critical Alerts** | Card | `[Critical Exceptions]` with red conditional formatting |
| **Scatter Plot** | Scatter | X: `reference_value`, Y: `recorded_value`, Legend: `asset_class`, Size: `percentage_diff` |
| **Slicer: Severity** | Slicer | `max_severity` |
| **Slicer: Asset Class** | Slicer | `asset_class` |

**Conditional Formatting:**
- Apply `[Severity Color]` measure to the severity column background
- Set data bars on `percentage_diff` column

#### Page 3: Counterparty Analysis
Risk exposure by counterparty:

| Visual | Type | Fields |
|--------|------|--------|
| **Top Counterparties** | Bar Chart | Axis: `counterparty`, Values: `[Counterparty Exposure]` |
| **Counterparty Matrix** | Matrix | Rows: `counterparty`, Columns: `asset_class`, Values: `recorded_value` |
| **Exception Heatmap** | Matrix | Rows: `counterparty`, Values: `exception_count` (with background color rules) |

---

## 4. Formatting & Theming

### Custom Color Theme
Save this as a `.json` theme file and import via **View** → **Themes** → **Browse for themes**:

```json
{
    "name": "Financial Valuation Dashboard",
    "dataColors": [
        "#6366F1", "#10B981", "#F59E0B", "#EF4444",
        "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6"
    ],
    "background": "#1E1E2E",
    "foreground": "#E2E8F0",
    "tableAccent": "#6366F1",
    "visualStyles": {
        "*": {
            "*": {
                "background": [{
                    "color": {"solid": {"color": "#2A2A3E"}},
                    "transparency": 10
                }],
                "border": [{
                    "color": {"solid": {"color": "#334155"}},
                    "show": true
                }]
            }
        }
    }
}
```

### Typography
- **Title**: Segoe UI Semibold, 16pt, #E2E8F0
- **Subtitle**: Segoe UI, 11pt, #94A3B8
- **Card values**: Segoe UI Bold, 28pt
- **Table headers**: Segoe UI Semibold, 10pt

---

## 5. Interactivity Features

### Slicers to Add
- **Asset Class** (dropdown)
- **Severity Level** (buttons)
- **Counterparty** (dropdown with search)
- **Has Exception** (toggle)
- **Valuation Date** (date picker, useful with multi-day data)

### Cross-Filtering
Enable cross-filtering between:
- Donut chart → Exception table
- Severity slicer → All visuals
- Scatter plot → Detail table

### Drillthrough
Set up drillthrough from the Executive Summary page to the Exception Deep Dive page:
1. On the Exception page, add `position_id` to the **Drillthrough** field well
2. Right-click any data point on the Executive Summary to drill through

### Bookmarks
Create bookmarks for common views:
- "All Exceptions" (no filters)
- "Critical Only" (severity = Critical)
- "Equity Focus" (asset_class = Equity)

---

## 6. Publishing & Scheduling

### Publish to Power BI Service
1. Click **Publish** → Select your workspace
2. Open the report in Power BI Service

### Schedule Refresh
To automate data refreshes:
1. Set up a **Scheduled Refresh** on the dataset
2. Point the data source to the export directory
3. Configure a **Python script** activity in the gateway to regenerate data:

```python
# Script to regenerate data before Power BI refresh
import subprocess
subprocess.run([
    "python", "-m", "src.data_generator"
], cwd="path/to/financial-valuation-dashboard")

from src.data_generator import generate_portfolio
from src.valuation_engine import calculate_position_values
from src.exception_detector import run_all_controls
from src.export_manager import export_powerbi_csv

portfolio = generate_portfolio()
valued = calculate_position_values(portfolio)
exceptions = run_all_controls(valued)
export_powerbi_csv(valued, exceptions)
```

---

## 7. Sample Screenshots Layout

### Executive Summary Page
```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Financial Valuation & Risk Monitoring Dashboard             │
│  Report Date: 2024-01-15                                        │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Portfolio│ Reference│  Total   │Exception │   Compliance        │
│  Value   │  Value   │ Variance │  Count   │     Rate            │
│ $XX.XM   │ $XX.XM   │ $XX.XK   │   XX     │  [===|  XX%  ]     │
├──────────┴──────────┼──────────┴──────────┴─────────────────────┤
│                     │                                           │
│   Asset Allocation  │    Deviation by Asset Class               │
│      (Donut)        │    (Clustered Bar Chart)                  │
│                     │                                           │
├─────────────────────┼───────────────────────────────────────────┤
│  Severity Breakdown │                                           │
│      (Pie)          │    Recent Exceptions (Table)              │
│                     │                                           │
└─────────────────────┴───────────────────────────────────────────┘
```

---

## ⚠️ Disclaimer

This Power BI dashboard uses **synthetic data** generated by the Financial Valuation Dashboard application. It is intended for **portfolio demonstration and educational purposes only**. It does not provide real regulatory compliance certification or investment advice.

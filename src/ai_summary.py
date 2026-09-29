"""
AI-Powered Exception Summary (Optional)
=========================================
Generates natural-language summaries of exception reports using an LLM.

IMPORTANT CONSTRAINTS:
- AI MUST NOT modify any financial calculations
- AI MUST NOT invent or impute missing data
- AI MUST NOT provide investment advice
- AI only summarizes patterns and highlights exceptions for human review
"""

import pandas as pd
from typing import Optional
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ENABLE_AI_SUMMARY, OPENAI_MODEL, AI_SYSTEM_PROMPT


def generate_exception_summary(
    exceptions_df: pd.DataFrame,
    exception_summary: dict,
    portfolio_summary: dict,
    use_ai: bool = ENABLE_AI_SUMMARY,
    api_key: Optional[str] = None,
) -> str:
    """
    Generate a human-readable summary of exceptions.

    If AI is disabled or unavailable, falls back to a rule-based template summary.

    Parameters
    ----------
    exceptions_df : pd.DataFrame
        Exception report DataFrame.
    exception_summary : dict
        Exception counts by type and severity.
    portfolio_summary : dict
        Portfolio-level summary metrics.
    use_ai : bool
        Whether to attempt AI-powered summarization.
    api_key : str, optional
        OpenAI API key. If None, reads from environment.

    Returns
    -------
    str
        Natural-language summary of exceptions.
    """
    if use_ai:
        try:
            return _ai_summary(exceptions_df, exception_summary, portfolio_summary, api_key)
        except Exception as e:
            return _template_summary(exception_summary, portfolio_summary) + (
                f"\n\n⚠️ AI summary unavailable: {str(e)}"
            )
    else:
        return _template_summary(exception_summary, portfolio_summary)


def _template_summary(exception_summary: dict, portfolio_summary: dict) -> str:
    """
    Generate a rule-based template summary (no AI required).
    This summary is deterministic and based purely on calculated metrics.
    """
    total = exception_summary.get("total_exceptions", 0)
    critical = exception_summary.get("critical_count", 0)
    high = exception_summary.get("high_count", 0)
    warning = exception_summary.get("warning_count", 0)
    by_type = exception_summary.get("by_type", {})

    total_positions = portfolio_summary.get("total_positions", 0)
    portfolio_pct = portfolio_summary.get("portfolio_pct_diff", 0)
    max_pct = portfolio_summary.get("max_pct_diff", 0)

    # Build summary
    lines = []
    lines.append("## 📊 Exception Summary Report")
    lines.append("")

    if total == 0:
        lines.append("✅ **No exceptions detected.** All positions passed valuation controls.")
        return "\n".join(lines)

    exception_rate = (total / total_positions * 100) if total_positions > 0 else 0
    lines.append(
        f"**{total} exceptions** detected across **{total_positions}** positions "
        f"({exception_rate:.1f}% exception rate)."
    )
    lines.append("")

    # Severity breakdown
    lines.append("### Severity Breakdown")
    if critical > 0:
        lines.append(f"- 🔴 **Critical:** {critical} — Requires immediate review")
    if high > 0:
        lines.append(f"- 🟠 **High:** {high} — Requires investigation")
    if warning > 0:
        lines.append(f"- 🟡 **Warning:** {warning} — Monitor closely")
    lines.append("")

    # Exception types
    lines.append("### Exception Types")
    for exc_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        icon = {
            "Missing Price": "❌",
            "Duplicate Position": "📋",
            "Invalid Quantity": "⚠️",
            "Threshold Breach": "📈",
        }.get(exc_type, "•")
        lines.append(f"- {icon} **{exc_type}:** {count}")
    lines.append("")

    # Key metrics
    lines.append("### Key Metrics")
    lines.append(f"- Portfolio-level valuation difference: **{portfolio_pct:.4f}%**")
    lines.append(f"- Maximum position-level difference: **{max_pct:.2f}%**")
    lines.append("")

    # Recommendations
    lines.append("### 🔍 Recommended Actions")
    if critical > 0:
        lines.append("1. **Immediately review** all Critical-severity exceptions")
    if by_type.get("Missing Price", 0) > 0:
        lines.append(
            f"2. Investigate **{by_type['Missing Price']} missing price(s)** — "
            "check data feeds and pricing sources"
        )
    if by_type.get("Duplicate Position", 0) > 0:
        lines.append(
            f"3. Resolve **{by_type['Duplicate Position']} duplicate position(s)** — "
            "verify against source booking system"
        )
    if by_type.get("Invalid Quantity", 0) > 0:
        lines.append(
            f"4. Correct **{by_type['Invalid Quantity']} invalid quantity entries** — "
            "validate trade capture data"
        )
    if by_type.get("Threshold Breach", 0) > 0:
        lines.append(
            f"5. Analyze **{by_type['Threshold Breach']} threshold breach(es)** — "
            "review pricing methodology and market data"
        )

    lines.append("")
    lines.append(
        "*This summary is auto-generated from calculated exception data. "
        "AI has not modified any financial calculations or created data.*"
    )

    return "\n".join(lines)


def _ai_summary(
    exceptions_df: pd.DataFrame,
    exception_summary: dict,
    portfolio_summary: dict,
    api_key: Optional[str],
) -> str:
    """
    Generate an AI-powered summary using OpenAI's API.
    Requires: pip install openai and a valid API key.
    """
    try:
        import openai
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("No OpenAI API key provided. Set OPENAI_API_KEY env var or pass api_key.")

    client = openai.OpenAI(api_key=api_key)

    # Prepare data context for the LLM — only summary stats, no raw data
    context = f"""
Portfolio Summary:
- Total positions: {portfolio_summary.get('total_positions', 0)}
- Total recorded value: ${portfolio_summary.get('total_recorded_value', 0):,.2f}
- Total reference value: ${portfolio_summary.get('total_reference_value', 0):,.2f}
- Portfolio % difference: {portfolio_summary.get('portfolio_pct_diff', 0):.4f}%
- Max position % difference: {portfolio_summary.get('max_pct_diff', 0):.2f}%

Exception Summary:
- Total exceptions: {exception_summary.get('total_exceptions', 0)}
- Critical: {exception_summary.get('critical_count', 0)}
- High: {exception_summary.get('high_count', 0)}
- Warning: {exception_summary.get('warning_count', 0)}
- By type: {exception_summary.get('by_type', {})}

Top 10 exceptions by severity:
{exceptions_df.head(10)[['position_id', 'asset_class', 'exception_type', 'severity', 'reason']].to_string(index=False) if len(exceptions_df) > 0 else 'None'}
"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Analyze the following valuation control exception report and provide "
                    "a concise summary with key observations and recommended next steps. "
                    "Do NOT modify any numbers or invent data.\n\n" + context
                ),
            },
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    ai_text = response.choices[0].message.content

    return (
        "## 🤖 AI-Powered Exception Summary\n\n"
        + ai_text
        + "\n\n---\n*Generated by AI. AI has not modified any financial calculations "
        "or created data. All numbers come from the valuation engine.*"
    )

from __future__ import annotations

from pam.models import DailyBrief


def render_brief_md(brief: DailyBrief) -> str:
    lines: list[str] = []
    lines.append(f"# DAILY PORTFOLIO BRIEF — {brief.date}")
    lines.append("")
    lines.append(f"- Macro Mode: **{brief.macro_mode}**")
    lines.append(f"- Portfolio Heat: **{brief.portfolio_heat:.4f}**")
    lines.append(f"- Cash Utilisation: **{brief.cash_utilisation:.4f}**")
    lines.append("")
    lines.append("## Portfolio Recommendations")
    for r in brief.recommendations:
        lines.append(
            f"- **{r.symbol}**: {r.action} (conf {r.confidence:.2f}) "
            f"entry {r.entry_range} | exit {r.exit_range} | stop {r.hard_stop} | trail {r.trailing_stop}"
        )
        lines.append(f"  - Tax: {r.tax_note}")
        lines.append(f"  - Fees: {r.fees_note}")
    lines.append("")
    lines.append("## Watchlist Opportunities")
    for r in brief.watchlist_opportunities:
        lines.append(
            f"- **{r.symbol}**: {r.action} (conf {r.confidence:.2f}) "
            f"entry {r.entry_range} | exit {r.exit_range} | stop {r.hard_stop} | trail {r.trailing_stop}"
        )
    if brief.risk_alerts:
        lines.append("")
        lines.append("## Risk Alerts")
        for a in brief.risk_alerts:
            lines.append(f"- {a}")
    if brief.notes:
        lines.append("")
        lines.append("## Notes")
        for n in brief.notes:
            lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)

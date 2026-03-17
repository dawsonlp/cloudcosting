"""Output formatters for cloudcosting.

Transforms Estimate domain objects into various output formats.
"""

from cloudcosting.domain import Estimate, ProviderEstimate


def to_docsmith(estimate: Estimate) -> dict:
    """Transform an Estimate into docsmith-compatible YAML structure.

    Docsmith expects:
        title: str
        subtitle: str (optional)
        status: str (optional)
        content: list of block dicts (heading, text, table, bullets, etc.)
    """
    content: list[dict] = []

    for provider_est in estimate.providers:
        _add_provider_section(content, provider_est)

    # Totals summary
    content.append({"heading": "Cost Summary"})
    content.append(
        {
            "table": {
                "headers": ["Metric", "Amount"],
                "rows": [
                    ["Monthly Total", f"${estimate.totals.get('monthly', 0.0):,.2f}"],
                    ["Annual Total", f"${estimate.totals.get('annual', 0.0):,.2f}"],
                ],
            }
        }
    )

    if estimate.warnings:
        content.append({"heading": "Warnings"})
        content.append({"bullets": list(estimate.warnings)})

    if estimate.errors:
        content.append({"heading": "Errors"})
        content.append(
            {"bullets": [f"{e.label} ({e.type}): {e.reason}" for e in estimate.errors]}
        )

    return {
        "title": "Infrastructure Cost Estimate",
        "subtitle": f"Generated {estimate.timestamp[:10]}",
        "status": estimate.status.capitalize(),
        "content": content,
    }


def _add_provider_section(content: list[dict], pe: ProviderEstimate) -> None:
    """Add content blocks for one provider estimate."""
    content.append({"heading": f"{pe.provider.upper()} - {pe.region}"})
    content.append(
        {
            "text": (
                f"Pricing date: {pe.pricing_date} | "
                f"Currency: {pe.currency} | "
                f"Cache: {pe.cache_status}"
            )
        }
    )

    # Resource table: one row per resource with monthly and annual costs
    if pe.resources:
        headers = ["Resource", "Type", "Monthly", "Annual"]
        rows = []
        for rc in pe.resources:
            rows.append(
                [
                    rc.label or rc.type,
                    rc.type,
                    f"${rc.monthly:,.2f}",
                    f"${rc.annual:,.2f}",
                ]
            )
        content.append({"table": {"headers": headers, "rows": rows}})

    # Line item detail per resource
    for rc in pe.resources:
        if rc.line_items:
            content.append({"heading": {"text": rc.label or rc.type, "level": 3}})
            li_headers = ["Component", "Monthly"]
            li_rows = [[li.name, f"${li.monthly:,.2f}"] for li in rc.line_items]
            content.append({"table": {"headers": li_headers, "rows": li_rows}})

        if rc.notes:
            content.append({"bullets": list(rc.notes)})

    # Provider-level errors
    if pe.errors:
        content.append(
            {"bullets": [f"Error: {e.label} ({e.type}): {e.reason}" for e in pe.errors]}
        )

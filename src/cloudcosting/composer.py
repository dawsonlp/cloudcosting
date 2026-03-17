"""Comparison Composer: produces multi-scenario docsmith comparison documents.

Pure function. Takes named scenarios (each an Estimate domain object),
aligns resources by label, and returns a docsmith-compatible dict.
No I/O, no side effects.
"""

from cloudcosting.domain import Estimate, ResourceCost


def compose_comparison(
    scenarios: list[tuple[str, Estimate]],
    include_detail: bool = False,
    title: str | None = None,
    subtitle: str | None = None,
    intro_text: str | None = None,
) -> tuple[dict, list[str]]:
    """Compose a multi-scenario comparison document.

    Args:
        scenarios: Ordered list of (name, Estimate) pairs.
        include_detail: Include per-resource line-item breakdowns.
        title: Document title. Defaults to 'Infrastructure Cost Comparison'.
        subtitle: Document subtitle. Optional.
        intro_text: Introductory paragraph. Optional.

    Returns:
        A tuple of (docsmith_dict, warnings).
        docsmith_dict has keys: title, subtitle, status, content.
        warnings is a list of warning strings (e.g., duplicate labels).
    """
    effective_title = title or "Infrastructure Cost Comparison"
    warnings: list[str] = []

    # Build alignment structures
    label_order, lookup = _align_resources(scenarios, warnings)
    scenario_names = [name for name, _ in scenarios]

    # Build content blocks
    content: list[dict] = []

    if intro_text:
        content.append({"text": intro_text})

    _add_cost_summary(content, scenarios)
    _add_resource_comparison(content, label_order, lookup, scenario_names)

    if include_detail:
        _add_resource_details(content, label_order, lookup, scenarios)

    _add_context(content, scenarios)

    result = {
        "title": effective_title,
        "content": content,
    }
    if subtitle:
        result["subtitle"] = subtitle

    return result, warnings


def _align_resources(
    scenarios: list[tuple[str, Estimate]],
    warnings: list[str],
) -> tuple[list[str], dict[str, dict[str, ResourceCost | None]]]:
    """Build ordered label list and lookup matrix.

    Returns:
        label_order: list of labels in first-seen order.
        lookup: {label: {scenario_name: ResourceCost | None}}
    """
    label_order: list[str] = []
    label_set: set[str] = set()
    lookup: dict[str, dict[str, ResourceCost | None]] = {}
    scenario_names = [name for name, _ in scenarios]

    for name, estimate in scenarios:
        seen_in_scenario: set[str] = set()
        for pe in estimate.providers:
            for rc in pe.resources:
                label = rc.label

                # Duplicate within scenario
                if label in seen_in_scenario:
                    warnings.append(
                        f"Duplicate label '{label}' in scenario '{name}' -- using first occurrence"
                    )
                    continue
                seen_in_scenario.add(label)

                # Track first-seen order
                if label not in label_set:
                    label_set.add(label)
                    label_order.append(label)
                    lookup[label] = {n: None for n in scenario_names}

                lookup[label][name] = rc

    return label_order, lookup


def _fmt(amount: float) -> str:
    """Format a dollar amount: $1,234.56"""
    return f"${amount:,.2f}"


def _add_cost_summary(
    content: list[dict],
    scenarios: list[tuple[str, Estimate]],
) -> None:
    """Add the cost summary table (monthly/annual per scenario)."""
    content.append({"heading": "Cost Summary"})

    headers = ["Metric"] + [name for name, _ in scenarios]
    monthly_row = ["Monthly Total"] + [
        _fmt(est.totals.get("monthly", 0.0)) for _, est in scenarios
    ]
    annual_row = ["Annual Total"] + [
        _fmt(est.totals.get("annual", 0.0)) for _, est in scenarios
    ]

    content.append({"table": {"headers": headers, "rows": [monthly_row, annual_row]}})


def _add_resource_comparison(
    content: list[dict],
    label_order: list[str],
    lookup: dict[str, dict[str, ResourceCost | None]],
    scenario_names: list[str],
) -> None:
    """Add the resource comparison table (per-resource monthly costs)."""
    content.append({"heading": "Resource Comparison"})

    headers = ["Resource"] + scenario_names
    rows = []
    for label in label_order:
        row = [label]
        for name in scenario_names:
            rc = lookup[label].get(name)
            row.append(_fmt(rc.monthly) if rc else "--")
        rows.append(row)

    content.append({"table": {"headers": headers, "rows": rows}})


def _add_resource_details(
    content: list[dict],
    label_order: list[str],
    lookup: dict[str, dict[str, ResourceCost | None]],
    scenarios: list[tuple[str, Estimate]],
) -> None:
    """Add per-resource line-item detail sections."""
    content.append({"heading": "Resource Details"})
    scenario_names = [name for name, _ in scenarios]

    for label in label_order:
        content.append({"heading": {"text": label, "level": 2}})

        # Collect all line-item names across scenarios for this resource
        li_names_order: list[str] = []
        li_names_set: set[str] = set()
        li_lookup: dict[str, dict[str, float | None]] = {}

        for name in scenario_names:
            rc = lookup[label].get(name)
            if rc and rc.line_items:
                for li in rc.line_items:
                    if li.name not in li_names_set:
                        li_names_set.add(li.name)
                        li_names_order.append(li.name)
                        li_lookup[li.name] = {n: None for n in scenario_names}
                    li_lookup[li.name][name] = li.monthly

        # Line-item table
        if li_names_order:
            headers = ["Component"] + scenario_names
            rows = []
            for li_name in li_names_order:
                row = [li_name]
                for sname in scenario_names:
                    val = li_lookup[li_name].get(sname)
                    row.append(_fmt(val) if val is not None else "--")
                rows.append(row)
            content.append({"table": {"headers": headers, "rows": rows}})

        # Notes attributed to scenario
        notes: list[str] = []
        for name in scenario_names:
            rc = lookup[label].get(name)
            if rc and rc.notes:
                for note in rc.notes:
                    notes.append(f"{name}: {note}")
        if notes:
            content.append({"bullets": notes})


def _add_context(
    content: list[dict],
    scenarios: list[tuple[str, Estimate]],
) -> None:
    """Add estimation context: metadata, warnings, errors."""
    content.append({"heading": "Estimation Context"})

    # Metadata table
    headers = ["Scenario", "Provider", "Region", "Pricing Date", "Cache", "Status"]
    rows = []
    for name, est in scenarios:
        providers = ", ".join(pe.provider for pe in est.providers)
        regions = ", ".join(pe.region for pe in est.providers)
        dates = ", ".join(pe.pricing_date for pe in est.providers)
        caches = ", ".join(pe.cache_status for pe in est.providers)
        rows.append([name, providers, regions, dates, caches, est.status])

    content.append({"table": {"headers": headers, "rows": rows}})

    # Warnings
    all_warnings: list[str] = []
    for name, est in scenarios:
        for w in est.warnings:
            all_warnings.append(f"{name}: {w}")
    if all_warnings:
        content.append({"bullets": all_warnings})

    # Errors
    all_errors: list[str] = []
    for name, est in scenarios:
        for e in est.errors:
            all_errors.append(f"{name}: {e.label} ({e.type}): {e.reason}")
        for pe in est.providers:
            for e in pe.errors:
                all_errors.append(f"{name}: {e.label} ({e.type}): {e.reason}")
    if all_errors:
        content.append({"heading": {"text": "Errors", "level": 2}})
        content.append({"bullets": all_errors})

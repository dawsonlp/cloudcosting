"""Tests for docsmith output formatter.

Tests that to_docsmith produces valid docsmith-compatible structure
from representative Estimate objects.
"""

import yaml

from cloudcosting.domain import (
    CostLineItem,
    Estimate,
    ProviderEstimate,
    ResourceCost,
    ResourceError,
)
from cloudcosting.formatters import to_docsmith


def test_docsmith_has_required_top_level_keys():
    """Docsmith requires title and content at minimum."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    assert "title" in result
    assert "content" in result
    assert isinstance(result["content"], list)


def test_docsmith_content_blocks_are_valid_types():
    """Every content block must use a recognized docsmith block type."""
    valid_keys = {"heading", "text", "bullets", "numbered", "table", "decision"}
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    for block in result["content"]:
        assert isinstance(block, dict), f"Content block is not a dict: {block}"
        block_keys = set(block.keys())
        assert block_keys & valid_keys, (
            f"Block has no recognized docsmith key: {block_keys}"
        )


def test_docsmith_includes_provider_heading():
    """Output includes a heading for the provider/region."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    headings = [
        b["heading"]
        for b in result["content"]
        if "heading" in b and isinstance(b["heading"], str)
    ]
    assert any("AWS" in h and "us-east-1" in h for h in headings)


def test_docsmith_includes_resource_table():
    """Output includes a table with resource cost rows."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    tables = [b["table"] for b in result["content"] if "table" in b]
    # At least one table should have resource data
    resource_tables = [t for t in tables if "Resource" in t.get("headers", [])]
    assert len(resource_tables) >= 1
    assert len(resource_tables[0]["rows"]) >= 1


def test_docsmith_includes_totals_table():
    """Output includes a cost summary table with monthly and annual totals."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    tables = [b["table"] for b in result["content"] if "table" in b]
    summary_tables = [t for t in tables if "Metric" in t.get("headers", [])]
    assert len(summary_tables) == 1
    rows_flat = [cell for row in summary_tables[0]["rows"] for cell in row]
    assert any("Monthly" in cell for cell in rows_flat)
    assert any("Annual" in cell for cell in rows_flat)


def test_docsmith_includes_warnings_when_present():
    """Warnings appear as bullets when present."""
    estimate = _make_estimate(warnings=("Stale cache for aws/us-east-1",))
    result = to_docsmith(estimate)
    bullet_blocks = [b["bullets"] for b in result["content"] if "bullets" in b]
    all_bullets = [item for bl in bullet_blocks for item in bl]
    assert any("Stale" in b for b in all_bullets)


def test_docsmith_includes_errors_when_present():
    """Errors appear as bullets when present."""
    error = ResourceError(label="Bad DB", type="rds", reason="Invalid engine")
    estimate = _make_estimate(errors=(error,))
    result = to_docsmith(estimate)
    bullet_blocks = [b["bullets"] for b in result["content"] if "bullets" in b]
    all_bullets = [item for bl in bullet_blocks for item in bl]
    assert any("Invalid engine" in b for b in all_bullets)


def test_docsmith_no_warnings_section_when_empty():
    """No warnings heading or bullets when there are no warnings."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    headings = [
        b["heading"]
        for b in result["content"]
        if "heading" in b and isinstance(b["heading"], str)
    ]
    assert "Warnings" not in headings


def test_docsmith_output_is_yaml_serializable():
    """The docsmith dict must round-trip through YAML cleanly."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    yaml_str = yaml.dump(result, default_flow_style=False, sort_keys=False)
    loaded = yaml.safe_load(yaml_str)
    assert loaded["title"] == result["title"]
    assert len(loaded["content"]) == len(result["content"])


def test_docsmith_status_is_capitalized():
    """Status field should be capitalized for display."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    assert result["status"] == "Complete"


def test_docsmith_subtitle_contains_date():
    """Subtitle includes the estimate date."""
    estimate = _make_estimate()
    result = to_docsmith(estimate)
    assert "2026-03-16" in result["subtitle"]


# -- Helpers --


def _make_estimate(
    warnings=(),
    errors=(),
) -> Estimate:
    line_items = (
        CostLineItem(name="instance", monthly=760.0),
        CostLineItem(name="storage", monthly=29.0),
    )
    rc = ResourceCost(
        label="Primary DB",
        type="rds",
        monthly=789.0,
        annual=9468.0,
        line_items=line_items,
        notes=("Multi-AZ: instance cost doubled",),
    )
    pe = ProviderEstimate(
        provider="aws",
        region="us-east-1",
        pricing_date="2026-03-16",
        currency="USD",
        cache_status="fresh",
        resources=(rc,),
    )
    return Estimate(
        version="0.1.0",
        timestamp="2026-03-16T10:00:00Z",
        status="complete",
        providers=(pe,),
        totals={"monthly": 789.0, "annual": 9468.0},
        warnings=warnings,
        errors=errors,
    )

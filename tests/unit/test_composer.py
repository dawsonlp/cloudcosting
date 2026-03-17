"""Tests for the Comparison Composer.

Pure function tests using synthetic domain objects.
No mocks, no I/O, no filesystem.
"""

from cloudcosting.composer import compose_comparison
from cloudcosting.domain import (
    CostLineItem,
    Estimate,
    ProviderEstimate,
    ResourceCost,
    ResourceError,
)


def _rc(label, monthly=100.0, line_items=(), notes=()):
    """Shorthand for building a ResourceCost."""
    return ResourceCost(
        label=label,
        type="ec2",
        monthly=monthly,
        annual=monthly * 12,
        line_items=tuple(line_items),
        notes=tuple(notes),
    )


def _estimate(resources, status="complete", warnings=(), errors=(), provider_errors=()):
    """Shorthand for building an Estimate with one provider."""
    total = sum(r.monthly for r in resources)
    return Estimate(
        version="1.2.0",
        timestamp="2026-03-16T00:00:00+00:00",
        status=status,
        providers=(
            ProviderEstimate(
                provider="aws",
                region="us-east-1",
                pricing_date="2026-03-16",
                currency="USD",
                cache_status="fresh",
                resources=tuple(resources),
                errors=tuple(provider_errors),
            ),
        ),
        totals={"monthly": total, "annual": total * 12},
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _multi_provider_estimate(provider_estimates, status="complete", warnings=()):
    """Build an Estimate with multiple providers."""
    total = sum(r.monthly for pe in provider_estimates for r in pe.resources)
    return Estimate(
        version="1.2.0",
        timestamp="2026-03-16T00:00:00+00:00",
        status=status,
        providers=tuple(provider_estimates),
        totals={"monthly": total, "annual": total * 12},
        warnings=tuple(warnings),
    )


def _find_table(content, after_heading):
    """Find the first table block that appears after a heading matching the text."""
    found_heading = False
    for block in content:
        if not found_heading:
            if (
                isinstance(block.get("heading"), str)
                and after_heading in block["heading"]
            ):
                found_heading = True
            continue
        if "table" in block:
            return block["table"]
    return None


def _find_bullets(content, after_heading):
    """Find the first bullets block after a heading."""
    found_heading = False
    for block in content:
        if not found_heading:
            if (
                isinstance(block.get("heading"), str)
                and after_heading in block["heading"]
            ):
                found_heading = True
            continue
        if "bullets" in block:
            return block["bullets"]
    return None


class TestResourceAlignment:
    def test_identical_scenarios_all_matched(self):
        """Two scenarios with same resources: no absent markers."""
        est = _estimate([_rc("Web Server"), _rc("Database")])
        result, warnings = compose_comparison([("Small", est), ("Large", est)])

        table = _find_table(result["content"], "Resource Comparison")
        assert table is not None
        # All cells should have dollar amounts, no '--'
        for row in table["rows"]:
            for cell in row[1:]:  # skip label column
                assert cell != "--"

    def test_different_resources_show_absent_markers(self):
        """Resources in one scenario but not the other show '--'."""
        est_a = _estimate([_rc("Web Server"), _rc("Database")])
        est_b = _estimate([_rc("Web Server"), _rc("Cache")])

        result, _ = compose_comparison([("A", est_a), ("B", est_b)])

        table = _find_table(result["content"], "Resource Comparison")
        rows_by_label = {row[0]: row for row in table["rows"]}

        # Database is in A but not B
        assert rows_by_label["Database"][1] != "--"  # A has it
        assert rows_by_label["Database"][2] == "--"  # B does not

        # Cache is in B but not A
        assert rows_by_label["Cache"][1] == "--"  # A does not
        assert rows_by_label["Cache"][2] != "--"  # B has it

    def test_first_seen_ordering(self):
        """Resources appear in order of first encounter across scenarios."""
        est_a = _estimate([_rc("Gamma"), _rc("Alpha")])
        est_b = _estimate([_rc("Beta"), _rc("Alpha")])

        result, _ = compose_comparison([("A", est_a), ("B", est_b)])

        table = _find_table(result["content"], "Resource Comparison")
        labels = [row[0] for row in table["rows"]]
        # Gamma and Alpha from A first, then Beta from B
        assert labels == ["Gamma", "Alpha", "Beta"]


class TestDetailSections:
    def test_detail_adds_line_item_tables(self):
        """include_detail=True produces per-resource line-item breakdowns."""
        items = [CostLineItem("Instance", 80.0), CostLineItem("Storage", 20.0)]
        est = _estimate([_rc("Web Server", line_items=items)])

        result, _ = compose_comparison(
            [("Small", est), ("Large", est)], include_detail=True
        )

        # Find a detail heading for Web Server
        found = False
        for block in result["content"]:
            h = block.get("heading")
            if isinstance(h, dict) and h.get("text") == "Web Server":
                found = True
                break
        assert found, "Detail heading for 'Web Server' not found"

    def test_detail_includes_notes(self):
        """Notes are attributed to the correct scenario."""
        est_a = _estimate([_rc("DB", notes=("Multi-AZ enabled",))])
        est_b = _estimate([_rc("DB", notes=("Single-AZ",))])

        result, _ = compose_comparison(
            [("HA", est_a), ("Standard", est_b)], include_detail=True
        )

        # Find bullets after DB detail heading
        found_db = False
        for _i, block in enumerate(result["content"]):
            h = block.get("heading")
            if isinstance(h, dict) and h.get("text") == "DB":
                found_db = True
                continue
            if found_db and "bullets" in block:
                bullets = block["bullets"]
                assert any("HA:" in b for b in bullets)
                assert any("Standard:" in b for b in bullets)
                break

    def test_no_detail_omits_line_items(self):
        """include_detail=False produces no Resource Details section."""
        items = [CostLineItem("Instance", 80.0)]
        est = _estimate([_rc("Web", line_items=items)])

        result, _ = compose_comparison([("A", est), ("B", est)], include_detail=False)

        headings = [
            b["heading"] for b in result["content"] if isinstance(b.get("heading"), str)
        ]
        assert "Resource Details" not in headings


class TestDocumentMetadata:
    def test_custom_title_subtitle_intro(self):
        """Custom title, subtitle, intro_text appear in output."""
        est = _estimate([_rc("Web")])
        result, _ = compose_comparison(
            [("A", est), ("B", est)],
            title="Project Phoenix",
            subtitle="Q2 2026",
            intro_text="Comparing two deployment options.",
        )

        assert result["title"] == "Project Phoenix"
        assert result["subtitle"] == "Q2 2026"
        assert result["content"][0] == {"text": "Comparing two deployment options."}

    def test_default_title(self):
        """No title provided uses default."""
        est = _estimate([_rc("Web")])
        result, _ = compose_comparison([("A", est), ("B", est)])
        assert result["title"] == "Infrastructure Cost Comparison"


class TestDuplicateLabels:
    def test_duplicate_label_first_wins_with_warning(self):
        """Duplicate labels within a scenario: first occurrence used, warning emitted."""
        rc_first = _rc("Server", monthly=100.0)
        rc_dup = _rc("Server", monthly=999.0)

        est = Estimate(
            version="1.2.0",
            timestamp="2026-03-16T00:00:00+00:00",
            status="complete",
            providers=(
                ProviderEstimate(
                    provider="aws",
                    region="us-east-1",
                    pricing_date="2026-03-16",
                    currency="USD",
                    cache_status="fresh",
                    resources=(rc_first, rc_dup),
                ),
            ),
            totals={"monthly": 1099.0, "annual": 13188.0},
        )

        result, warnings = compose_comparison([("A", est), ("B", est)])

        # Warning about duplicate
        assert any("Duplicate" in w and "Server" in w for w in warnings)

        # Table should use $100.00, not $999.00
        table = _find_table(result["content"], "Resource Comparison")
        server_row = [r for r in table["rows"] if r[0] == "Server"][0]
        assert server_row[1] == "$100.00"


class TestMultiProvider:
    def test_multi_provider_metadata(self):
        """Multi-provider scenario lists all providers in context."""
        pe_aws = ProviderEstimate(
            provider="aws",
            region="us-east-1",
            pricing_date="2026-03-16",
            currency="USD",
            cache_status="fresh",
            resources=(_rc("Web"),),
        )
        pe_azure = ProviderEstimate(
            provider="azure",
            region="eastus",
            pricing_date="2026-03-16",
            currency="USD",
            cache_status="fresh",
            resources=(_rc("DB"),),
        )
        est = _multi_provider_estimate([pe_aws, pe_azure])

        result, _ = compose_comparison(
            [("Mixed", est), ("AWS Only", _estimate([_rc("Web")]))]
        )

        table = _find_table(result["content"], "Estimation Context")
        mixed_row = [r for r in table["rows"] if r[0] == "Mixed"][0]
        assert "aws" in mixed_row[1]
        assert "azure" in mixed_row[1]


class TestWarningsAndErrors:
    def test_warnings_attributed_to_scenario(self):
        """Warnings from different scenarios are prefixed with scenario name."""
        est_a = _estimate([_rc("Web")], warnings=("Stale pricing cache",))
        est_b = _estimate([_rc("Web")])

        result, _ = compose_comparison([("Stale", est_a), ("Fresh", est_b)])

        bullets = _find_bullets(result["content"], "Estimation Context")
        assert bullets is not None
        assert any("Stale:" in b for b in bullets)

    def test_partial_status_noted(self):
        """Scenario with partial status appears in context metadata."""
        est = _estimate([_rc("Web")], status="partial")

        result, _ = compose_comparison([("A", est), ("B", _estimate([_rc("Web")]))])

        table = _find_table(result["content"], "Estimation Context")
        a_row = [r for r in table["rows"] if r[0] == "A"][0]
        assert a_row[5] == "partial"


class TestEmptyScenario:
    def test_scenario_with_no_resources(self):
        """Scenario with only errors and no resources is handled gracefully."""
        est_empty = Estimate(
            version="1.2.0",
            timestamp="2026-03-16T00:00:00+00:00",
            status="failed",
            providers=(
                ProviderEstimate(
                    provider="aws",
                    region="us-east-1",
                    pricing_date="2026-03-16",
                    currency="USD",
                    cache_status="miss",
                    resources=(),
                    errors=(ResourceError("DB", "rds", "Pricing unavailable"),),
                ),
            ),
            totals={"monthly": 0.0, "annual": 0.0},
            errors=(ResourceError("DB", "rds", "Pricing unavailable"),),
        )
        est_good = _estimate([_rc("Web", monthly=50.0)])

        result, _ = compose_comparison([("Failed", est_empty), ("Good", est_good)])

        # Should still produce output with the good scenario's resources
        table = _find_table(result["content"], "Resource Comparison")
        assert table is not None
        assert len(table["rows"]) == 1  # Only "Web" from Good
        web_row = table["rows"][0]
        assert web_row[0] == "Web"
        assert web_row[1] == "--"  # Failed has no Web
        assert web_row[2] != "--"  # Good has Web

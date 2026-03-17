"""Property tests for domain objects.

Tests business-meaningful invariants, not that dataclasses have fields.
"""

import json

import yaml
from hypothesis import given
from hypothesis.strategies import (
    floats,
    lists,
    text,
)

from cloudcosting.domain import (
    CostLineItem,
    Estimate,
    ProviderEstimate,
    ResourceCost,
    ResourceError,
)

# -- Strategies --

reasonable_cost = floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False)
short_text = text(min_size=1, max_size=50)


# -- Conservation: sum of line items == monthly total --


@given(
    amounts=lists(reasonable_cost, min_size=1, max_size=10),
)
def test_resource_cost_conservation(amounts):
    """Sum of line item monthly amounts must equal monthly total."""
    line_items = tuple(
        CostLineItem(name=f"item_{i}", monthly=amt) for i, amt in enumerate(amounts)
    )
    monthly = sum(amounts)
    annual = monthly * 12

    rc = ResourceCost(
        label="test",
        type="test",
        monthly=monthly,
        annual=annual,
        line_items=line_items,
    )

    d = rc.to_dict()
    line_item_sum = sum(item["monthly"] for item in d["line_items"])
    # Allow rounding tolerance from round(x, 2)
    assert abs(d["monthly"] - line_item_sum) < 0.01 * len(amounts) + 0.01


# -- Non-negative: no cost is ever negative --


@given(amount=reasonable_cost)
def test_cost_line_item_non_negative(amount):
    """Cost line items with non-negative input produce non-negative output."""
    item = CostLineItem(name="test", monthly=amount)
    assert item.to_dict()["monthly"] >= 0.0


# -- Annual = monthly * 12 --


@given(monthly=reasonable_cost)
def test_annual_is_twelve_times_monthly(monthly):
    """Annual cost is always monthly * 12."""
    annual = monthly * 12
    rc = ResourceCost(
        label="test",
        type="test",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="total", monthly=monthly),),
    )
    d = rc.to_dict()
    # Rounding monthly to 2dp introduces up to 0.005 error, *12 = 0.06
    assert abs(d["annual"] - d["monthly"] * 12) < 0.07


# -- to_dict produces JSON-serializable output --


def test_estimate_to_dict_json_serializable():
    """Full Estimate.to_dict() must be JSON-serializable."""
    estimate = _make_sample_estimate()
    d = estimate.to_dict()
    # Must not raise
    json_str = json.dumps(d)
    assert isinstance(json_str, str)


def test_estimate_to_dict_yaml_serializable():
    """Full Estimate.to_dict() must be YAML-serializable."""
    estimate = _make_sample_estimate()
    d = estimate.to_dict()
    yaml_str = yaml.dump(d, default_flow_style=False)
    assert isinstance(yaml_str, str)


def test_estimate_to_dict_roundtrip():
    """YAML serialize then deserialize produces equivalent structure."""
    estimate = _make_sample_estimate()
    d = estimate.to_dict()
    yaml_str = yaml.dump(d, default_flow_style=False)
    loaded = yaml.safe_load(yaml_str)
    assert loaded == d


def test_partial_estimate_has_errors():
    """A partial estimate includes errors in output."""
    error = ResourceError(label="Bad DB", type="rds", reason="Invalid engine")
    estimate = Estimate(
        version="0.1.0",
        timestamp="2026-03-16T10:00:00Z",
        status="partial",
        providers=(),
        totals={"monthly": 0.0, "annual": 0.0},
        errors=(error,),
    )
    d = estimate.to_dict()
    assert d["estimate"]["status"] == "partial"
    assert len(d["estimate"]["errors"]) == 1
    assert d["estimate"]["errors"][0]["reason"] == "Invalid engine"


# -- Helpers --


def _make_sample_estimate() -> Estimate:
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
    )

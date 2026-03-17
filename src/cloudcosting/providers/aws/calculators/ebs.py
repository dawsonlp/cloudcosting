"""EBS Storage cost calculator."""

from __future__ import annotations

from cloudcosting.domain import CostLineItem, ResourceCost

EBS_PRICES = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
}


def validate(params: dict) -> list[str]:
    errors = []
    if "size_gb" not in params:
        errors.append("EBS: missing required parameter 'size_gb'")
    return errors


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    volume_type = params.get("volume_type", "gp3")
    size_gb = int(params["size_gb"])
    count = int(params.get("count", 1))

    try:
        data = pricing_adapter.get_price(
            service_code="AmazonEC2",
            filters={"productFamily": "Storage", "volumeApiName": volume_type},
            region=region,
        )
        per_gb = _extract_gb_month(data) or EBS_PRICES.get(volume_type, 0.08)
    except Exception:
        per_gb = EBS_PRICES.get(volume_type, 0.08)

    monthly = per_gb * size_gb * count
    annual = monthly * 12

    notes = [f"Volume type: {volume_type}"]
    if count > 1:
        notes.append(f"Count: {count} volumes")

    return ResourceCost(
        label=label or f"EBS {volume_type}",
        type="ebs",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="storage", monthly=monthly),),
        notes=tuple(notes),
    )


def _extract_gb_month(data: dict) -> float:
    prices = data.get("prices", {})
    for key in ("gb-mo", "gb-month", "gb"):
        if key in prices:
            return prices[key]["price"]
    for entry in prices.values():
        return entry["price"]
    return 0.0

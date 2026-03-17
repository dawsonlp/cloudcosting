"""S3 Storage cost calculator."""

from __future__ import annotations

from cloudcosting.domain import CostLineItem, ResourceCost

S3_PRICES = {
    "STANDARD": 0.023,
    "STANDARD_IA": 0.0125,
    "GLACIER": 0.004,
    "DEEP_ARCHIVE": 0.00099,
}


def validate(params: dict) -> list[str]:
    errors = []
    if "size_gb" not in params:
        errors.append("S3: missing required parameter 'size_gb'")
    return errors


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    storage_class = params.get("storage_class", "STANDARD")
    size_gb = int(params["size_gb"])

    try:
        data = pricing_adapter.get_price(
            service_code="AmazonS3",
            filters={"productFamily": "Storage", "storageClass": storage_class},
            region=region,
        )
        per_gb = _extract_gb_month(data) or S3_PRICES.get(storage_class, 0.023)
    except Exception:
        per_gb = S3_PRICES.get(storage_class, 0.023)

    monthly = per_gb * size_gb
    annual = monthly * 12

    return ResourceCost(
        label=label or f"S3 {storage_class}",
        type="s3",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="storage", monthly=monthly),),
        notes=(
            f"Storage class: {storage_class}",
            "Request and transfer costs excluded (usage-dependent)",
        ),
    )


def _extract_gb_month(data: dict) -> float:
    prices = data.get("prices", {})
    for key in ("gb-mo", "gb-month", "gb"):
        if key in prices:
            return prices[key]["price"]
    for entry in prices.values():
        return entry["price"]
    return 0.0

"""EC2 cost calculator."""

from __future__ import annotations

from cloudcosting.domain import CostLineItem, ResourceCost

HOURS_PER_MONTH = 730


def validate(params: dict) -> list[str]:
    errors = []
    if "instance_type" not in params:
        errors.append("EC2: missing required parameter 'instance_type'")
    return errors


# Fallback hourly prices when API is unavailable (us-east-1, On-Demand, Linux)
EC2_FALLBACK_PRICES = {
    "t3.nano": 0.0052,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "t3.xlarge": 0.1664,
    "t3.2xlarge": 0.3328,
    "m6i.large": 0.096,
    "m6i.xlarge": 0.192,
    "m6i.2xlarge": 0.384,
    "c6i.large": 0.085,
    "c6i.xlarge": 0.17,
    "c6i.2xlarge": 0.34,
    "r6i.large": 0.126,
    "r6i.xlarge": 0.252,
    "r6i.2xlarge": 0.504,
}


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    instance_type = params["instance_type"]
    count = int(params.get("count", 1))

    try:
        data = pricing_adapter.get_price(
            service_code="AmazonEC2",
            filters={
                "instanceType": instance_type,
                "operatingSystem": "Linux",
                "tenancy": "Shared",
                "preInstalledSw": "NA",
            },
            region=region,
        )
        hourly = _extract_hourly(data) or EC2_FALLBACK_PRICES.get(instance_type, 0.10)
    except Exception:
        hourly = EC2_FALLBACK_PRICES.get(instance_type, 0.10)
    instance_monthly = hourly * HOURS_PER_MONTH * count
    monthly = instance_monthly
    annual = monthly * 12

    notes = []
    if count > 1:
        notes.append(f"Count: {count} instances")

    return ResourceCost(
        label=label or f"EC2 {instance_type}",
        type="ec2",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="instance", monthly=monthly),),
        notes=tuple(notes),
    )


def _extract_hourly(data: dict) -> float:
    prices = data.get("prices", {})
    for key in ("hrs", "hr", "hour", "hours"):
        if key in prices:
            return prices[key]["price"]
    for entry in prices.values():
        return entry["price"]
    return 0.0

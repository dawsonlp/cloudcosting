"""NAT Gateway cost calculator."""

from cloudcosting.domain import CostLineItem, ResourceCost

HOURS_PER_MONTH = 730
NAT_GATEWAY_HOURLY = 0.045  # Fixed hourly rate, fetched from API when available


def validate(params: dict) -> list[str]:
    return []  # No required params beyond defaults


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    count = int(params.get("count", 1))

    try:
        data = pricing_adapter.get_price(
            service_code="AmazonEC2",
            filters={"productFamily": "NAT Gateway", "usagetype": "NatGateway-Hours"},
            region=region,
        )
        hourly = _extract_hourly(data) or NAT_GATEWAY_HOURLY
    except Exception:
        hourly = NAT_GATEWAY_HOURLY

    monthly = hourly * HOURS_PER_MONTH * count
    annual = monthly * 12

    notes = ["Data transfer costs excluded (usage-dependent)"]
    if count > 1:
        notes.append(f"Count: {count} gateways")

    return ResourceCost(
        label=label or "NAT Gateway",
        type="nat_gateway",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="gateway", monthly=monthly),),
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

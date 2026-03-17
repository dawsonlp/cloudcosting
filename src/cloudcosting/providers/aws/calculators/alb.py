"""Application Load Balancer cost calculator."""

from __future__ import annotations

from cloudcosting.domain import CostLineItem, ResourceCost

HOURS_PER_MONTH = 730
ALB_HOURLY = 0.0225


def validate(params: dict) -> list[str]:
    return []


def estimate(params: dict, pricing_adapter, region: str, label: str) -> ResourceCost:
    count = int(params.get("count", 1))

    try:
        data = pricing_adapter.get_price(
            service_code="ElasticLoadBalancing",
            filters={
                "productFamily": "Load Balancer-Application",
                "usagetype": "LoadBalancerUsage",
            },
            region=region,
        )
        hourly = _extract_hourly(data) or ALB_HOURLY
    except Exception:
        hourly = ALB_HOURLY

    monthly = hourly * HOURS_PER_MONTH * count
    annual = monthly * 12

    notes = ["LCU costs excluded (usage-dependent)"]
    if count > 1:
        notes.append(f"Count: {count} load balancers")

    return ResourceCost(
        label=label or "Application Load Balancer",
        type="alb",
        monthly=monthly,
        annual=annual,
        line_items=(CostLineItem(name="load_balancer", monthly=monthly),),
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

"""AWS Provider: orchestrates calculators for AWS resources."""

import logging
from datetime import date

from cloudcosting.cache import PriceCache
from cloudcosting.domain import (
    ProviderEstimate,
    ResourceCost,
    ResourceError,
    ResourceSpec,
)
from cloudcosting.providers.aws.calculators import alb, ebs, ec2, nat_gateway, rds, s3
from cloudcosting.providers.aws.pricing import AwsPricingAdapter

logger = logging.getLogger(__name__)

CALCULATOR_REGISTRY = {
    "rds": rds,
    "ec2": ec2,
    "nat_gateway": nat_gateway,
    "alb": alb,
    "ebs": ebs,
    "s3": s3,
}

PROVIDER_ID = "aws"


class AwsProvider:
    """AWS cost estimation provider."""

    def __init__(self, cache: PriceCache, profile: str | None = None):
        self._cache = cache
        self._profile = profile
        self._adapters: dict[str, AwsPricingAdapter] = {}

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    @property
    def supported_types(self) -> set[str]:
        return set(CALCULATOR_REGISTRY.keys())

    def _get_adapter(self, region: str) -> AwsPricingAdapter:
        if region not in self._adapters:
            self._adapters[region] = AwsPricingAdapter(
                cache=self._cache, region=region, profile=self._profile
            )
        return self._adapters[region]

    def estimate_resources(
        self, resources: list[ResourceSpec], region: str
    ) -> ProviderEstimate:
        """Estimate costs for a list of AWS resources in a given region."""
        adapter = self._get_adapter(region)
        results: list[ResourceCost] = []
        errors: list[ResourceError] = []

        for spec in resources:
            calculator = CALCULATOR_REGISTRY.get(spec.type)
            if calculator is None:
                errors.append(
                    ResourceError(
                        label=spec.label or spec.type,
                        type=spec.type,
                        reason=f"Unknown AWS resource type '{spec.type}'. "
                        f"Supported: {sorted(CALCULATOR_REGISTRY.keys())}",
                    )
                )
                continue

            # Validate params
            validation_errors = calculator.validate(spec.params)
            if validation_errors:
                errors.append(
                    ResourceError(
                        label=spec.label or spec.type,
                        type=spec.type,
                        reason="; ".join(validation_errors),
                    )
                )
                continue

            # Estimate
            try:
                cost = calculator.estimate(
                    params=spec.params,
                    pricing_adapter=adapter,
                    region=spec.region,
                    label=spec.label,
                )
                results.append(cost)
            except Exception as e:
                logger.error("Failed to estimate %s: %s", spec.label or spec.type, e)
                errors.append(
                    ResourceError(
                        label=spec.label or spec.type,
                        type=spec.type,
                        reason=str(e),
                    )
                )

        return ProviderEstimate(
            provider=PROVIDER_ID,
            region=region,
            pricing_date=adapter.pricing_date or str(date.today()),
            currency="USD",
            cache_status=adapter.cache_status,
            resources=tuple(results),
            errors=tuple(errors),
        )

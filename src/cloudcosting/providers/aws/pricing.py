"""AWS Pricing Adapter.

Fetches prices from the AWS Pricing API via boto3 and uses the shared Price Cache.
All API response parsing is encapsulated here -- calculators never see raw responses.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from cloudcosting.cache import PriceCache
from cloudcosting.domain import PricingError

logger = logging.getLogger(__name__)

PRICING_REGION = "us-east-1"  # Only region with the full Pricing API


class PricingAdapter(Protocol):
    """Interface that calculators use to get unit prices."""

    def get_price(self, service_code: str, filters: dict, region: str) -> dict:
        """Get pricing data for a service with given filters."""
        ...

    @property
    def pricing_date(self) -> str: ...

    @property
    def cache_status(self) -> str: ...


class AwsPricingAdapter:
    """Fetches AWS prices via boto3, with Price Cache integration."""

    def __init__(self, cache: PriceCache, region: str, profile: str | None = None):
        self._cache = cache
        self._region = region
        self._profile = profile
        self._client = None
        self._pricing_date = ""
        self._cache_status = "unknown"

    @property
    def pricing_date(self) -> str:
        return self._pricing_date

    @property
    def cache_status(self) -> str:
        return self._cache_status

    def _get_client(self):
        if self._client is None:
            session = boto3.Session(profile_name=self._profile)
            self._client = session.client("pricing", region_name=PRICING_REGION)
        return self._client

    def get_price(self, service_code: str, filters: dict, region: str) -> dict:
        """Get pricing data. Checks cache first, then API, then stale cache."""
        cache_key = ("aws", region, service_code, json.dumps(filters, sort_keys=True))

        # Try fresh cache
        result = self._cache.retrieve(cache_key)
        if result.status == "fresh" and result.data is not None:
            self._cache_status = "fresh"
            self._pricing_date = result.data.get("pricing_date", "cached")
            return result.data

        # Try API
        try:
            data = self._fetch_from_api(service_code, filters, region)
            self._cache.store("aws", cache_key, data)
            self._cache_status = "fresh"
            self._pricing_date = data.get("pricing_date", "")
            return data
        except (PricingError, BotoCoreError, ClientError, Exception) as api_err:
            logger.warning("AWS Pricing API failed: %s. Trying stale cache.", api_err)

            # Fall back to stale cache
            stale = self._cache.retrieve(cache_key, allow_stale=True)
            if stale.status == "stale" and stale.data is not None:
                self._cache_status = "stale"
                self._pricing_date = stale.data.get("pricing_date", "cached")
                logger.warning(
                    "Using stale cached pricing (age: %.0f seconds)",
                    stale.age_seconds or 0,
                )
                return stale.data

            raise PricingError(
                f"Failed to fetch pricing for {service_code} and no cached data available: {api_err}"
            ) from api_err

    def _fetch_from_api(self, service_code: str, filters: dict, region: str) -> dict:
        """Fetch pricing from AWS Pricing API and parse the response."""
        client = self._get_client()

        api_filters = [
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
        ]
        for field, value in filters.items():
            api_filters.append(
                {"Type": "TERM_MATCH", "Field": field, "Value": str(value)}
            )

        try:
            response = client.get_products(
                ServiceCode=service_code,
                Filters=api_filters,
                MaxResults=10,
            )
        except (BotoCoreError, ClientError) as e:
            raise PricingError(f"AWS Pricing API call failed: {e}") from e

        price_list = response.get("PriceList", [])
        if not price_list:
            raise PricingError(
                f"No pricing found for {service_code} with filters {filters} in {region}"
            )

        # Parse the first result
        return self._parse_price_list(price_list, service_code)

    def _parse_price_list(self, price_list: list, service_code: str) -> dict:
        """Extract unit prices from the verbose AWS pricing response."""
        from datetime import date

        prices = {}
        for item_str in price_list:
            item = json.loads(item_str) if isinstance(item_str, str) else item_str

            terms = item.get("terms", {})
            on_demand = terms.get("OnDemand", {})

            for _term_key, term_value in on_demand.items():
                price_dimensions = term_value.get("priceDimensions", {})
                for _dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get("pricePerUnit", {})
                    usd = price_per_unit.get("USD", "0")
                    unit = dim_value.get("unit", "unknown")
                    description = dim_value.get("description", "")

                    try:
                        price_val = float(usd)
                    except (ValueError, TypeError):
                        price_val = 0.0

                    if price_val > 0:
                        prices[unit.lower()] = {
                            "price": price_val,
                            "unit": unit,
                            "description": description,
                            "currency": "USD",
                        }

        return {
            "service_code": service_code,
            "prices": prices,
            "pricing_date": str(date.today()),
            "raw_count": len(price_list),
        }

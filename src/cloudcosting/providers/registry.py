"""Provider Registry: maps provider IDs to provider instances."""

from cloudcosting.cache import PriceCache
from cloudcosting.providers.aws.provider import AwsProvider


class ProviderRegistry:
    """Registry of cost estimation providers."""

    def __init__(self, cache: PriceCache, profile: str | None = None):
        self._providers = {}
        self._cache = cache
        self._profile = profile
        self._register_defaults()

    def _register_defaults(self):
        aws = AwsProvider(cache=self._cache, profile=self._profile)
        self._providers[aws.provider_id] = aws

    def get(self, provider_id: str):
        return self._providers.get(provider_id)

    @property
    def known_ids(self) -> set[str]:
        return set(self._providers.keys())

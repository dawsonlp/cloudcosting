"""Tests for PriceCache behavior.

Tests store/retrieve, TTL expiry, staleness, and refresh operations.
"""

import json
import time

import pytest

from cloudcosting.cache import PriceCache


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "test_cache"


@pytest.fixture
def cache(cache_dir):
    return PriceCache(cache_dir=cache_dir, ttl_seconds=60)


SAMPLE_KEY = ("aws", "us-east-1", "AmazonRDS", "db.r6g.xlarge")
SAMPLE_DATA = {"price_per_hour": 1.04, "currency": "USD"}


def test_store_then_retrieve_returns_same_data(cache):
    """Store then retrieve returns identical data."""
    cache.store("aws", SAMPLE_KEY, SAMPLE_DATA)
    result = cache.retrieve(SAMPLE_KEY)
    assert result.status == "fresh"
    assert result.data == SAMPLE_DATA


def test_retrieve_missing_key_returns_miss(cache):
    """Retrieving a key that was never stored returns miss."""
    result = cache.retrieve(("nonexistent",))
    assert result.status == "miss"
    assert result.data is None


def test_expired_entry_not_returned_as_fresh(cache_dir):
    """Expired entries are not returned as fresh."""
    cache = PriceCache(cache_dir=cache_dir, ttl_seconds=1)
    cache.store("aws", SAMPLE_KEY, SAMPLE_DATA)

    # Manually backdate the timestamp to make it expired
    filepath = cache._key_to_path(SAMPLE_KEY)
    entry = json.loads(filepath.read_text())
    entry["timestamp"] = time.time() - 100
    filepath.write_text(json.dumps(entry))

    result = cache.retrieve(SAMPLE_KEY, allow_stale=False)
    assert result.status == "miss"
    assert result.data is None


def test_expired_entry_returned_as_stale_when_requested(cache_dir):
    """Expired entries are returned as stale when allow_stale=True."""
    cache = PriceCache(cache_dir=cache_dir, ttl_seconds=1)
    cache.store("aws", SAMPLE_KEY, SAMPLE_DATA)

    # Backdate
    filepath = cache._key_to_path(SAMPLE_KEY)
    entry = json.loads(filepath.read_text())
    entry["timestamp"] = time.time() - 100
    filepath.write_text(json.dumps(entry))

    result = cache.retrieve(SAMPLE_KEY, allow_stale=True)
    assert result.status == "stale"
    assert result.data == SAMPLE_DATA
    assert result.age_seconds is not None
    assert result.age_seconds > 90


def test_provider_scoped_refresh_removes_only_that_provider(cache):
    """Provider-scoped refresh removes only matching provider's entries."""
    aws_key = ("aws", "us-east-1", "AmazonRDS")
    azure_key = ("azure", "eastus", "VirtualMachines")

    cache.store("aws", aws_key, {"price": 1.0})
    cache.store("azure", azure_key, {"price": 2.0})

    deleted = cache.refresh_provider("aws")
    assert deleted == 1

    assert cache.retrieve(aws_key).status == "miss"
    assert cache.retrieve(azure_key).status == "fresh"


def test_global_refresh_removes_all_entries(cache):
    """Global refresh removes all cached entries."""
    cache.store("aws", ("aws", "key1"), {"price": 1.0})
    cache.store("azure", ("azure", "key2"), {"price": 2.0})

    deleted = cache.refresh_all()
    assert deleted == 2

    assert cache.retrieve(("aws", "key1")).status == "miss"
    assert cache.retrieve(("azure", "key2")).status == "miss"


def test_refresh_empty_cache_returns_zero(cache):
    """Refreshing an empty/nonexistent cache returns 0."""
    assert cache.refresh_all() == 0
    assert cache.refresh_provider("aws") == 0

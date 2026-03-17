"""File-based Price Cache with TTL.

Provider-agnostic cache that stores keyed pricing data as JSON files.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from cloudcosting.domain import CacheError

DEFAULT_CACHE_DIR = Path.home() / ".cloudcosting" / "cache"
DEFAULT_TTL_SECONDS = 86400  # 24 hours


@dataclass(frozen=True)
class CacheResult:
    """Result of a cache retrieval."""

    data: dict | None
    status: str  # "fresh", "stale", "miss"
    age_seconds: float | None = None


class PriceCache:
    """File-based key-value cache with TTL and provider-scoped refresh."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        self._cache_dir = cache_dir
        self._ttl_seconds = ttl_seconds

    def store(self, provider: str, key: tuple, data: dict) -> None:
        """Store pricing data with a cache key."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            entry = {
                "provider": provider,
                "key": str(key),
                "data": data,
                "timestamp": time.time(),
                "ttl_seconds": self._ttl_seconds,
            }
            filepath = self._key_to_path(key)
            filepath.write_text(json.dumps(entry, indent=2))
        except OSError as e:
            raise CacheError(f"Failed to write cache: {e}") from e

    def retrieve(self, key: tuple, allow_stale: bool = False) -> CacheResult:
        """Retrieve cached data. Returns fresh, stale, or miss."""
        filepath = self._key_to_path(key)
        if not filepath.exists():
            return CacheResult(data=None, status="miss")

        try:
            entry = json.loads(filepath.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise CacheError(f"Failed to read cache: {e}") from e

        age = time.time() - entry["timestamp"]
        is_expired = age > entry.get("ttl_seconds", self._ttl_seconds)

        if not is_expired:
            return CacheResult(data=entry["data"], status="fresh", age_seconds=age)

        if allow_stale:
            return CacheResult(data=entry["data"], status="stale", age_seconds=age)

        return CacheResult(data=None, status="miss", age_seconds=age)

    def refresh_provider(self, provider: str) -> int:
        """Delete all cached entries for a provider. Returns count deleted."""
        if not self._cache_dir.exists():
            return 0
        count = 0
        for filepath in self._cache_dir.glob("*.json"):
            try:
                entry = json.loads(filepath.read_text())
                if entry.get("provider") == provider:
                    filepath.unlink()
                    count += 1
            except (OSError, json.JSONDecodeError):
                continue
        return count

    def refresh_all(self) -> int:
        """Delete all cached entries. Returns count deleted."""
        if not self._cache_dir.exists():
            return 0
        count = 0
        for filepath in self._cache_dir.glob("*.json"):
            try:
                filepath.unlink()
                count += 1
            except OSError:
                continue
        return count

    def _key_to_path(self, key: tuple) -> Path:
        """Deterministic hash of cache key to file path."""
        key_str = json.dumps(key, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        return self._cache_dir / f"{key_hash}.json"

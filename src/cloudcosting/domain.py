"""Domain objects and exceptions for cloudcosting.

All data flowing through the system is represented here.
No component defines its own ad-hoc dictionaries for passing data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# -- Exceptions --


class CloudCostError(Exception):
    """Base exception for all cloudcosting errors."""


class ConfigError(CloudCostError):
    """Configuration file is malformed or missing required fields."""


class ProviderError(CloudCostError):
    """Provider-specific validation failure."""


class PricingError(CloudCostError):
    """Unable to fetch or parse pricing data."""


class CacheError(CloudCostError):
    """Cache read/write failure (filesystem issues)."""


# -- Input domain --


@dataclass(frozen=True)
class ResourceSpec:
    """A single resource specification from the configuration."""

    provider: str
    region: str
    type: str
    params: dict = field(default_factory=dict)
    label: str = ""


@dataclass(frozen=True)
class EstimationConfig:
    """Full parsed configuration: resources plus global defaults."""

    resources: tuple[ResourceSpec, ...]
    defaults: dict = field(default_factory=dict)


# -- Output domain --


@dataclass(frozen=True)
class CostLineItem:
    """One cost component (e.g., instance, storage, backup)."""

    name: str
    monthly: float

    def to_dict(self) -> dict:
        return {"name": self.name, "monthly": round(self.monthly, 2)}


@dataclass(frozen=True)
class ResourceCost:
    """Full cost breakdown for one successfully estimated resource."""

    label: str
    type: str
    monthly: float
    annual: float
    line_items: tuple[CostLineItem, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        result = {
            "label": self.label,
            "type": self.type,
            "monthly": round(self.monthly, 2),
            "annual": round(self.annual, 2),
            "line_items": [item.to_dict() for item in self.line_items],
        }
        if self.notes:
            result["notes"] = list(self.notes)
        return result


@dataclass(frozen=True)
class ResourceError:
    """A failed resource with reason."""

    label: str
    type: str
    reason: str

    def to_dict(self) -> dict:
        return {"label": self.label, "type": self.type, "reason": self.reason}


@dataclass(frozen=True)
class ProviderEstimate:
    """Results for one provider: metadata + resource breakdowns + errors."""

    provider: str
    region: str
    pricing_date: str
    currency: str
    cache_status: str
    resources: tuple[ResourceCost, ...]
    errors: tuple[ResourceError, ...] = ()

    def to_dict(self) -> dict:
        result = {
            "provider": self.provider,
            "region": self.region,
            "pricing_date": self.pricing_date,
            "currency": self.currency,
            "cache_status": self.cache_status,
            "resources": [r.to_dict() for r in self.resources],
        }
        if self.errors:
            result["errors"] = [e.to_dict() for e in self.errors]
        return result


@dataclass(frozen=True)
class Estimate:
    """Top-level output: everything the CLI needs to serialize."""

    version: str
    timestamp: str
    status: str  # "complete" or "partial"
    providers: tuple[ProviderEstimate, ...]
    totals: dict  # {"monthly": float, "annual": float}
    errors: tuple[ResourceError, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        result: dict = {
            "estimate": {
                "version": self.version,
                "timestamp": self.timestamp,
                "status": self.status,
                "providers": [p.to_dict() for p in self.providers],
                "totals": {
                    "monthly": round(self.totals.get("monthly", 0.0), 2),
                    "annual": round(self.totals.get("annual", 0.0), 2),
                },
                "errors": [e.to_dict() for e in self.errors],
                "warnings": list(self.warnings),
            }
        }
        return result

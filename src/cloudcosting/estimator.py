"""Estimator: Transaction script that orchestrates the full estimation workflow.

Load config -> group resources by provider/region -> estimate -> aggregate -> return Estimate.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from cloudcosting import __version__
from cloudcosting.cache import PriceCache
from cloudcosting.config import load_config
from cloudcosting.domain import (
    Estimate,
    EstimationConfig,
    ProviderEstimate,
    ResourceError,
    ResourceSpec,
)
from cloudcosting.providers.registry import ProviderRegistry


def run_estimation(
    config_path: Path,
    cache: PriceCache | None = None,
    profile: str | None = None,
) -> Estimate:
    """Full estimation workflow: config -> providers -> aggregate.

    This is the main entry point for the estimation pipeline.

    Args:
        config_path: Path to YAML config file.
        cache: Optional PriceCache instance (created with defaults if None).
        profile: Optional AWS/cloud profile name. Overrides config-level profile.
    """
    if cache is None:
        cache = PriceCache()

    # Load config first (without provider validation) to extract profile
    config = load_config(config_path)

    # Resolve profile: CLI flag > config file > None
    effective_profile = profile or config.profile

    # Create registry with resolved profile, then re-load with provider validation
    registry = ProviderRegistry(cache=cache, profile=effective_profile)
    config = load_config(config_path, known_providers=registry.known_ids)

    return estimate_from_config(config, registry)


def estimate_from_config(
    config: EstimationConfig,
    registry: ProviderRegistry,
) -> Estimate:
    """Estimate costs from an already-loaded config."""
    # Group resources by (provider, region)
    groups: dict[tuple[str, str], list[ResourceSpec]] = defaultdict(list)
    global_errors: list[ResourceError] = []

    for spec in config.resources:
        provider = registry.get(spec.provider)
        if provider is None:
            global_errors.append(
                ResourceError(
                    label=spec.label or spec.type,
                    type=spec.type,
                    reason=f"No provider registered for '{spec.provider}'",
                )
            )
            continue
        groups[(spec.provider, spec.region)].append(spec)

    # Run estimation per provider/region group
    provider_estimates: list[ProviderEstimate] = []
    for (provider_id, region), specs in groups.items():
        provider = registry.get(provider_id)
        pe = provider.estimate_resources(specs, region)
        provider_estimates.append(pe)

    # Aggregate totals
    total_monthly = sum(rc.monthly for pe in provider_estimates for rc in pe.resources)
    total_annual = total_monthly * 12

    # Determine status
    all_errors = list(global_errors)
    for pe in provider_estimates:
        all_errors.extend(pe.errors)

    has_results = any(pe.resources for pe in provider_estimates)
    if all_errors and has_results:
        status = "partial"
    elif all_errors and not has_results:
        status = "failed"
    else:
        status = "complete"

    # Collect warnings
    warnings = []
    for pe in provider_estimates:
        if pe.cache_status == "stale":
            warnings.append(f"Using stale cached pricing for {pe.provider}/{pe.region}")

    return Estimate(
        version=__version__,
        timestamp=datetime.now(UTC).isoformat(),
        status=status,
        providers=tuple(provider_estimates),
        totals={"monthly": total_monthly, "annual": total_annual},
        errors=tuple(global_errors),
        warnings=tuple(warnings),
    )

"""Config Loader: reads YAML, validates structure, returns EstimationConfig.

Validates structural requirements only. Provider-specific fields pass through.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from cloudcosting.domain import ConfigError, EstimationConfig, ResourceSpec

REQUIRED_RESOURCE_FIELDS = ("provider", "region", "type")


def load_config(
    path: Path,
    known_providers: set[str] | None = None,
) -> EstimationConfig:
    """Load and validate a YAML configuration file.

    Args:
        path: Path to YAML config file.
        known_providers: If provided, validate provider IDs against this set.

    Returns:
        EstimationConfig with validated resource specs.

    Raises:
        ConfigError: On any structural validation failure.
    """
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(
            f"Configuration must be a YAML mapping, got {type(raw).__name__}"
        )

    # Extract top-level defaults
    defaults = {}
    if "provider" in raw:
        defaults["provider"] = str(raw["provider"])
    if "region" in raw:
        defaults["region"] = str(raw["region"])

    # Resources list is required
    if "resources" not in raw:
        raise ConfigError("Configuration must contain a 'resources' key")

    raw_resources = raw["resources"]
    if not isinstance(raw_resources, list):
        raise ConfigError("'resources' must be a list")

    if len(raw_resources) == 0:
        raise ConfigError("'resources' list must not be empty")

    resources = []
    for i, res in enumerate(raw_resources):
        if not isinstance(res, dict):
            raise ConfigError(
                f"Resource {i}: must be a mapping, got {type(res).__name__}"
            )

        # Apply defaults for missing fields
        effective = {**defaults, **res}

        # Check required fields
        for field in REQUIRED_RESOURCE_FIELDS:
            if field not in effective:
                raise ConfigError(f"Resource {i}: missing required field '{field}'")
            if not isinstance(effective[field], str):
                raise ConfigError(
                    f"Resource {i}: '{field}' must be a string, "
                    f"got {type(effective[field]).__name__}"
                )

        provider = effective["provider"]
        region = effective["region"]
        resource_type = effective["type"]

        # Validate provider ID if registry is available
        if known_providers is not None and provider not in known_providers:
            raise ConfigError(
                f"Resource {i}: unknown provider '{provider}'. "
                f"Known providers: {sorted(known_providers)}"
            )

        # Extract label, pass everything else as params
        label = str(effective.get("label", ""))
        params = {
            k: v
            for k, v in effective.items()
            if k not in ("provider", "region", "type", "label")
        }

        resources.append(
            ResourceSpec(
                provider=provider,
                region=region,
                type=resource_type,
                params=params,
                label=label,
            )
        )

    return EstimationConfig(resources=tuple(resources), defaults=defaults)

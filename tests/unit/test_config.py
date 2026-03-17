"""Tests for Config Loader.

Tests structural validation, defaults, passthrough, and error messages.
"""

from pathlib import Path

import pytest
import yaml

from cloudcosting.config import load_config
from cloudcosting.domain import ConfigError


@pytest.fixture
def config_file(tmp_path):
    """Helper to write a YAML config and return its path."""

    def _write(content: dict) -> "Path":
        path = tmp_path / "config.yaml"
        path.write_text(yaml.dump(content))
        return path

    return _write


# -- Valid configs parse correctly --


def test_valid_config_with_defaults(config_file):
    """Config with top-level provider/region parses all resources."""
    path = config_file(
        {
            "provider": "aws",
            "region": "us-east-1",
            "resources": [
                {
                    "type": "rds",
                    "engine": "postgres",
                    "instance_class": "db.r6g.xlarge",
                },
                {"type": "ec2", "instance_type": "t3.micro"},
            ],
        }
    )
    cfg = load_config(path)
    assert len(cfg.resources) == 2
    assert cfg.resources[0].provider == "aws"
    assert cfg.resources[0].region == "us-east-1"
    assert cfg.resources[0].type == "rds"


def test_valid_config_per_resource_provider(config_file):
    """Config with provider/region on each resource parses correctly."""
    path = config_file(
        {
            "resources": [
                {
                    "provider": "aws",
                    "region": "us-east-1",
                    "type": "rds",
                    "engine": "postgres",
                },
            ],
        }
    )
    cfg = load_config(path)
    assert len(cfg.resources) == 1
    assert cfg.resources[0].provider == "aws"


# -- Missing required fields produce ConfigError --


def test_missing_resources_key(config_file):
    """Config without 'resources' key raises ConfigError."""
    path = config_file({"provider": "aws", "region": "us-east-1"})
    with pytest.raises(ConfigError, match="'resources'"):
        load_config(path)


def test_missing_provider_field(config_file):
    """Resource without provider (and no default) raises ConfigError naming the field."""
    path = config_file(
        {
            "resources": [
                {"region": "us-east-1", "type": "rds"},
            ],
        }
    )
    with pytest.raises(ConfigError, match="'provider'"):
        load_config(path)


def test_missing_type_field(config_file):
    """Resource without type raises ConfigError naming the field."""
    path = config_file(
        {
            "provider": "aws",
            "region": "us-east-1",
            "resources": [
                {"engine": "postgres"},
            ],
        }
    )
    with pytest.raises(ConfigError, match="'type'"):
        load_config(path)


def test_file_not_found(tmp_path):
    """Nonexistent file raises ConfigError."""
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_invalid_yaml(tmp_path):
    """Malformed YAML raises ConfigError."""
    path = tmp_path / "bad.yaml"
    path.write_text(": : : not valid yaml [")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(path)


def test_empty_resources_list(config_file):
    """Empty resources list raises ConfigError."""
    path = config_file({"provider": "aws", "region": "us-east-1", "resources": []})
    with pytest.raises(ConfigError, match="must not be empty"):
        load_config(path)


# -- Provider-specific fields pass through untouched --


def test_provider_specific_fields_passthrough(config_file):
    """Fields beyond provider/region/type/label pass through as params."""
    path = config_file(
        {
            "provider": "aws",
            "region": "us-east-1",
            "resources": [
                {
                    "type": "rds",
                    "engine": "postgres",
                    "instance_class": "db.r6g.xlarge",
                    "storage_gb": 250,
                    "multi_az": True,
                },
            ],
        }
    )
    cfg = load_config(path)
    params = cfg.resources[0].params
    assert params["engine"] == "postgres"
    assert params["instance_class"] == "db.r6g.xlarge"
    assert params["storage_gb"] == 250
    assert params["multi_az"] is True


# -- Top-level defaults applied; resource-level overrides win --


def test_resource_overrides_default_region(config_file):
    """Resource-level region overrides top-level default."""
    path = config_file(
        {
            "provider": "aws",
            "region": "us-east-1",
            "resources": [
                {"type": "rds", "region": "eu-west-1"},
            ],
        }
    )
    cfg = load_config(path)
    assert cfg.resources[0].region == "eu-west-1"


def test_resource_overrides_default_provider(config_file):
    """Resource-level provider overrides top-level default."""
    path = config_file(
        {
            "provider": "aws",
            "region": "us-east-1",
            "resources": [
                {"type": "vm", "provider": "azure", "region": "eastus"},
            ],
        }
    )
    cfg = load_config(path)
    assert cfg.resources[0].provider == "azure"


# -- Provider ID validation --


def test_unknown_provider_with_registry(config_file):
    """Unknown provider ID raises ConfigError when registry is provided."""
    path = config_file(
        {
            "resources": [
                {"provider": "oracle", "region": "us-ashburn-1", "type": "db"},
            ],
        }
    )
    with pytest.raises(ConfigError, match="unknown provider 'oracle'"):
        load_config(path, known_providers={"aws", "azure"})


def test_known_provider_passes_validation(config_file):
    """Known provider ID passes validation."""
    path = config_file(
        {
            "resources": [
                {"provider": "aws", "region": "us-east-1", "type": "rds"},
            ],
        }
    )
    cfg = load_config(path, known_providers={"aws", "azure"})
    assert cfg.resources[0].provider == "aws"


def test_no_registry_skips_provider_validation(config_file):
    """Without registry, any provider ID is accepted."""
    path = config_file(
        {
            "resources": [
                {"provider": "oracle", "region": "us-ashburn-1", "type": "db"},
            ],
        }
    )
    cfg = load_config(path)  # no known_providers
    assert cfg.resources[0].provider == "oracle"

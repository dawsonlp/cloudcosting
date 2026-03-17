"""Estimator tests: full pipeline with fake pricing (no API calls)."""

import pytest
import yaml

from cloudcosting.cache import PriceCache
from cloudcosting.domain import EstimationConfig, ResourceSpec
from cloudcosting.estimator import estimate_from_config
from cloudcosting.providers.registry import ProviderRegistry


class FakePricingAdapter:
    """Returns known prices; no AWS API calls."""

    def __init__(self):
        self._pricing_date = "2026-03-16"
        self._cache_status = "fresh"

    @property
    def pricing_date(self):
        return self._pricing_date

    @property
    def cache_status(self):
        return self._cache_status

    def get_price(self, service_code, filters, region):
        if service_code == "AmazonRDS":
            if "instanceType" in filters:
                return {
                    "prices": {"hrs": {"price": 1.04}},
                    "pricing_date": "2026-03-16",
                }
            return {"prices": {"gb-mo": {"price": 0.115}}, "pricing_date": "2026-03-16"}
        if service_code == "AmazonEC2":
            if "Storage" in filters.get("productFamily", ""):
                return {
                    "prices": {"gb-mo": {"price": 0.08}},
                    "pricing_date": "2026-03-16",
                }
            return {"prices": {"hrs": {"price": 0.0104}}, "pricing_date": "2026-03-16"}
        if service_code == "AmazonS3":
            return {"prices": {"gb-mo": {"price": 0.023}}, "pricing_date": "2026-03-16"}
        if service_code == "ElasticLoadBalancing":
            return {"prices": {"hrs": {"price": 0.0225}}, "pricing_date": "2026-03-16"}
        return {"prices": {}, "pricing_date": "2026-03-16"}


@pytest.fixture
def cache(tmp_path):
    return PriceCache(cache_dir=tmp_path / "cache", ttl_seconds=3600)


@pytest.fixture
def registry(cache, monkeypatch):
    """Registry with AWS provider that uses fake pricing."""
    reg = ProviderRegistry(cache=cache)
    aws = reg.get("aws")
    # Monkey-patch to use fake adapter for all regions
    fake = FakePricingAdapter()
    monkeypatch.setattr(aws, "_get_adapter", lambda region: fake)
    return reg


def test_complete_estimation(registry):
    """Full estimation with valid resources returns complete status."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="rds",
                params={
                    "engine": "postgres",
                    "instance_class": "db.r6g.xlarge",
                    "storage_gb": 100,
                },
                label="Primary DB",
            ),
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="ec2",
                params={"instance_type": "t3.micro"},
                label="Bastion",
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    assert result.status == "complete"
    assert len(result.providers) == 1
    assert len(result.providers[0].resources) == 2
    assert result.totals["monthly"] > 0
    assert abs(result.totals["annual"] - result.totals["monthly"] * 12) < 0.01


def test_partial_estimation_with_unknown_type(registry):
    """Mix of valid and invalid resource types returns partial status."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="rds",
                params={
                    "engine": "postgres",
                    "instance_class": "db.r6g.xlarge",
                    "storage_gb": 100,
                },
                label="Primary DB",
            ),
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="unknown_service",
                params={},
                label="Mystery",
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    assert result.status == "partial"
    assert len(result.providers[0].resources) == 1
    assert len(result.providers[0].errors) == 1


def test_partial_estimation_with_validation_error(registry):
    """Resource with missing required params returns partial with error."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="rds",
                params={},
                label="Bad DB",
            ),
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="ec2",
                params={"instance_type": "t3.micro"},
                label="Good EC2",
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    assert result.status == "partial"
    assert len(result.providers[0].errors) == 1
    assert "engine" in result.providers[0].errors[0].reason


def test_estimation_output_serializable(registry):
    """Estimation output can be serialized to YAML."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="ec2",
                params={"instance_type": "t3.micro"},
                label="Bastion",
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    d = result.to_dict()
    yaml_str = yaml.dump(d, default_flow_style=False)
    loaded = yaml.safe_load(yaml_str)
    assert loaded["estimate"]["status"] == "complete"
    assert loaded["estimate"]["totals"]["monthly"] > 0


def test_conservation_totals_equal_sum_of_resources(registry):
    """Total monthly equals sum of all resource monthlies."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="rds",
                params={
                    "engine": "postgres",
                    "instance_class": "db.r6g.xlarge",
                    "storage_gb": 250,
                },
                label="DB",
            ),
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="ec2",
                params={"instance_type": "t3.micro", "count": 3},
                label="Web",
            ),
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="nat_gateway",
                params={"count": 2},
                label="NAT",
            ),
            ResourceSpec(
                provider="aws", region="us-east-1", type="alb", params={}, label="ALB"
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    resource_sum = sum(r.monthly for pe in result.providers for r in pe.resources)
    assert abs(result.totals["monthly"] - resource_sum) < 0.01


def test_multi_region_grouped(registry):
    """Resources in different regions create separate provider estimates."""
    config = EstimationConfig(
        resources=(
            ResourceSpec(
                provider="aws",
                region="us-east-1",
                type="ec2",
                params={"instance_type": "t3.micro"},
                label="East",
            ),
            ResourceSpec(
                provider="aws",
                region="eu-west-1",
                type="ec2",
                params={"instance_type": "t3.micro"},
                label="West",
            ),
        ),
    )
    result = estimate_from_config(config, registry)
    assert result.status == "complete"
    assert len(result.providers) == 2
    regions = {pe.region for pe in result.providers}
    assert regions == {"us-east-1", "eu-west-1"}

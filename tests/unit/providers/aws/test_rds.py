"""RDS calculator tests with known unit prices."""

from hypothesis import given
from hypothesis.strategies import integers

from cloudcosting.providers.aws.calculators import rds


class FakePricing:
    """Returns known prices for testing."""

    def __init__(self, hourly=1.04, gb_month=0.115):
        self.hourly = hourly
        self.gb_month = gb_month

    def get_price(self, service_code, filters, region):
        if "instanceType" in filters:
            return {"prices": {"hrs": {"price": self.hourly}}}
        return {"prices": {"gb-mo": {"price": self.gb_month}}}


def test_rds_basic_calculation():
    """RDS cost with known prices produces correct breakdown."""
    result = rds.estimate(
        params={
            "engine": "postgres",
            "instance_class": "db.r6g.xlarge",
            "storage_gb": 100,
        },
        pricing_adapter=FakePricing(hourly=1.04, gb_month=0.115),
        region="us-east-1",
        label="Test DB",
    )
    assert result.type == "rds"
    assert result.label == "Test DB"
    # Instance: 1.04 * 730 = 759.20
    assert abs(result.line_items[0].monthly - 759.20) < 0.01
    # Storage: 0.115 * 100 = 11.50
    assert abs(result.line_items[1].monthly - 11.50) < 0.01
    # Conservation
    assert abs(result.monthly - sum(i.monthly for i in result.line_items)) < 0.01
    assert abs(result.annual - result.monthly * 12) < 0.01


def test_rds_multi_az_noted():
    """Multi-AZ is noted in the output."""
    result = rds.estimate(
        params={
            "engine": "postgres",
            "instance_class": "db.r6g.xlarge",
            "storage_gb": 100,
            "multi_az": True,
        },
        pricing_adapter=FakePricing(),
        region="us-east-1",
        label="",
    )
    assert any("Multi-AZ" in n for n in result.notes)


def test_rds_validation_missing_engine():
    errors = rds.validate({"instance_class": "db.r6g.xlarge", "storage_gb": 100})
    assert any("engine" in e for e in errors)


def test_rds_validation_missing_all():
    errors = rds.validate({})
    assert len(errors) == 3


@given(storage=integers(min_value=1, max_value=10000))
def test_rds_monotonicity_storage(storage):
    """Increasing storage never decreases cost."""
    small = rds.estimate(
        params={
            "engine": "postgres",
            "instance_class": "db.r6g.xlarge",
            "storage_gb": 1,
        },
        pricing_adapter=FakePricing(),
        region="us-east-1",
        label="",
    )
    large = rds.estimate(
        params={
            "engine": "postgres",
            "instance_class": "db.r6g.xlarge",
            "storage_gb": storage,
        },
        pricing_adapter=FakePricing(),
        region="us-east-1",
        label="",
    )
    assert large.monthly >= small.monthly


def test_rds_conservation():
    """Sum of line items equals monthly total."""
    result = rds.estimate(
        params={
            "engine": "postgres",
            "instance_class": "db.r6g.xlarge",
            "storage_gb": 250,
            "backup_retention_days": 35,
        },
        pricing_adapter=FakePricing(),
        region="us-east-1",
        label="",
    )
    line_sum = sum(i.monthly for i in result.line_items)
    assert abs(result.monthly - line_sum) < 0.01

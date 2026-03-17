"""Tests for EC2, NAT Gateway, ALB, EBS, S3 calculators."""

from hypothesis import given
from hypothesis.strategies import integers

from cloudcosting.providers.aws.calculators import alb, ebs, ec2, nat_gateway, s3

HOURS = 730


class FakePricing:
    def __init__(self, hourly=0.0104, gb_month=0.08):
        self.hourly = hourly
        self.gb_month = gb_month

    def get_price(self, service_code, filters, region):
        if any(k in filters for k in ("instanceType", "productFamily")):
            if "Storage" in filters.get("productFamily", ""):
                return {"prices": {"gb-mo": {"price": self.gb_month}}}
            return {"prices": {"hrs": {"price": self.hourly}}}
        return {"prices": {"hrs": {"price": self.hourly}}}


# -- EC2 --


def test_ec2_basic():
    result = ec2.estimate(
        params={"instance_type": "t3.micro"},
        pricing_adapter=FakePricing(hourly=0.0104),
        region="us-east-1",
        label="Bastion",
    )
    assert abs(result.monthly - 0.0104 * HOURS) < 0.01
    assert abs(result.annual - result.monthly * 12) < 0.01


@given(count=integers(min_value=1, max_value=100))
def test_ec2_scaling(count):
    single = ec2.estimate(
        params={"instance_type": "t3.micro", "count": 1},
        pricing_adapter=FakePricing(hourly=0.01),
        region="us-east-1",
        label="",
    )
    multi = ec2.estimate(
        params={"instance_type": "t3.micro", "count": count},
        pricing_adapter=FakePricing(hourly=0.01),
        region="us-east-1",
        label="",
    )
    assert abs(multi.monthly - single.monthly * count) < 0.01


def test_ec2_validation():
    assert len(ec2.validate({})) == 1
    assert len(ec2.validate({"instance_type": "t3.micro"})) == 0


# -- NAT Gateway --


def test_nat_gateway_basic():
    result = nat_gateway.estimate(
        params={"count": 3},
        pricing_adapter=FakePricing(hourly=0.045),
        region="us-east-1",
        label="",
    )
    assert abs(result.monthly - 0.045 * HOURS * 3) < 0.01
    assert any("Data transfer" in n for n in result.notes)


@given(count=integers(min_value=1, max_value=20))
def test_nat_gateway_scaling(count):
    single = nat_gateway.estimate(
        params={"count": 1},
        pricing_adapter=FakePricing(hourly=0.045),
        region="us-east-1",
        label="",
    )
    multi = nat_gateway.estimate(
        params={"count": count},
        pricing_adapter=FakePricing(hourly=0.045),
        region="us-east-1",
        label="",
    )
    assert abs(multi.monthly - single.monthly * count) < 0.01


# -- ALB --


def test_alb_basic():
    result = alb.estimate(
        params={"count": 1},
        pricing_adapter=FakePricing(hourly=0.0225),
        region="us-east-1",
        label="",
    )
    assert abs(result.monthly - 0.0225 * HOURS) < 0.01
    assert any("LCU" in n for n in result.notes)


@given(count=integers(min_value=1, max_value=10))
def test_alb_scaling(count):
    single = alb.estimate(
        params={"count": 1},
        pricing_adapter=FakePricing(hourly=0.0225),
        region="us-east-1",
        label="",
    )
    multi = alb.estimate(
        params={"count": count},
        pricing_adapter=FakePricing(hourly=0.0225),
        region="us-east-1",
        label="",
    )
    assert abs(multi.monthly - single.monthly * count) < 0.01


# -- EBS --


def test_ebs_basic():
    result = ebs.estimate(
        params={"size_gb": 100, "volume_type": "gp3"},
        pricing_adapter=FakePricing(gb_month=0.08),
        region="us-east-1",
        label="",
    )
    assert abs(result.monthly - 0.08 * 100) < 0.01
    assert abs(result.annual - result.monthly * 12) < 0.01


@given(count=integers(min_value=1, max_value=20))
def test_ebs_scaling(count):
    single = ebs.estimate(
        params={"size_gb": 100, "count": 1},
        pricing_adapter=FakePricing(gb_month=0.08),
        region="us-east-1",
        label="",
    )
    multi = ebs.estimate(
        params={"size_gb": 100, "count": count},
        pricing_adapter=FakePricing(gb_month=0.08),
        region="us-east-1",
        label="",
    )
    assert abs(multi.monthly - single.monthly * count) < 0.01


def test_ebs_validation():
    assert len(ebs.validate({})) == 1
    assert len(ebs.validate({"size_gb": 100})) == 0


# -- S3 --


def test_s3_basic():
    result = s3.estimate(
        params={"size_gb": 500},
        pricing_adapter=FakePricing(gb_month=0.023),
        region="us-east-1",
        label="Docs",
    )
    assert abs(result.monthly - 0.023 * 500) < 0.01
    assert any("Request" in n for n in result.notes)


def test_s3_validation():
    assert len(s3.validate({})) == 1
    assert len(s3.validate({"size_gb": 100})) == 0

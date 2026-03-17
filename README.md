# cloudcosting

Multi-cloud infrastructure cost estimation tool. Fetches real-time pricing from cloud provider APIs (AWS Pricing API), caches results locally, and produces structured YAML/JSON cost breakdowns.

## Architecture

```
Config YAML -> Config Loader -> Estimator -> Provider Registry -> AWS Provider
                                                                    |
                                                              Calculator per resource type
                                                                    |
                                                              Pricing Adapter (API + Cache)
                                                                    |
                                                              Estimate output (YAML/JSON)
```

### Layers

| Layer | Module | Responsibility |
|-------|--------|---------------|
| Domain | `domain.py` | Dataclasses, exceptions, serialization |
| Config | `config.py` | YAML parsing, structural validation |
| Cache | `cache.py` | File-based pricing cache with TTL |
| Estimator | `estimator.py` | Transaction script: config -> providers -> aggregate |
| Provider | `providers/aws/` | AWS-specific pricing adapter and calculators |
| CLI | `cli.py` | Command-line interface |

### Supported AWS Resource Types

| Type | Calculator | Required Params |
|------|-----------|----------------|
| `rds` | RDS instances | `engine`, `instance_class`, `storage_gb` |
| `ec2` | EC2 instances | `instance_type` |
| `nat_gateway` | NAT Gateways | (none required) |
| `alb` | Application Load Balancers | (none required) |
| `ebs` | EBS Volumes | `size_gb` |
| `s3` | S3 Storage | `size_gb` |

## Setup

```bash
cd cloudcosting
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Usage

```bash
# Run estimation
python -m cloudcosting estimate config.yaml

# Output as JSON
python -m cloudcosting estimate config.yaml --format json

# Write to file
python -m cloudcosting estimate config.yaml -o costs.yaml

# Cache management
python -m cloudcosting cache status
python -m cloudcosting cache refresh aws
```

### Example Config

```yaml
provider: aws
region: us-east-1

resources:
  - type: rds
    label: Primary Database
    engine: postgres
    instance_class: db.r6g.xlarge
    storage_gb: 250
    multi_az: true

  - type: ec2
    label: Web Servers
    instance_type: t3.micro
    count: 3

  - type: nat_gateway
    label: NAT Gateways
    count: 2

  - type: alb
    label: Application Load Balancer

  - type: ebs
    label: Data Volumes
    size_gb: 500
    volume_type: gp3
    count: 3

  - type: s3
    label: Document Storage
    size_gb: 1000
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/unit/test_domain.py -v
python -m pytest tests/unit/providers/aws/test_rds.py -v

# Run with coverage
python -m pytest tests/ -v --tb=short
```

52 unit tests covering domain invariants, config validation, cache behavior, calculator arithmetic, and full estimation pipeline.

## Adding New Resource Types

1. Create a calculator module in `providers/aws/calculators/` with `validate()` and `estimate()` functions
2. Register it in `providers/aws/provider.py` `CALCULATOR_REGISTRY`
3. Add tests in `tests/unit/providers/aws/`

## Adding New Providers

1. Create a provider package under `providers/` (e.g., `providers/azure/`)
2. Implement the same interface as `AwsProvider` (with `estimate_resources()`)
3. Register it in `providers/registry.py`
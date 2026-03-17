# cloudcosting

Multi-cloud infrastructure cost estimation tool. Fetches real-time pricing from cloud provider APIs (AWS Pricing API), caches results locally, and produces structured YAML/JSON cost breakdowns. Includes a comparison command for side-by-side multi-scenario cost analysis with docsmith-compatible output for Word document generation.

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
| Formatters | `formatters.py` | Output format transformations (docsmith) |
| Composer | `composer.py` | Multi-scenario comparison document composition |
| CLI | `cli.py` | Command-line interface (estimate, cache, compare) |

### Supported AWS Resource Types

| Type | Calculator | Required Params |
|------|-----------|----------------|
| `rds` | RDS instances | `engine`, `instance_class`, `storage_gb` |
| `ec2` | EC2 instances | `instance_type` |
| `nat_gateway` | NAT Gateways | (none required) |
| `alb` | Application Load Balancers | (none required) |
| `ebs` | EBS Volumes | `size_gb` |
| `s3` | S3 Storage | `size_gb` |

## Installation

```bash
pipx install cloudcosting
```

This makes the `cloudcosting` command available globally.

### Development Setup

For contributing or local development:

```bash
cd cloudcosting
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Usage

### Estimating Costs

```bash
# Run estimation (YAML output)
cloudcosting estimate config.yaml

# Output as JSON
cloudcosting estimate config.yaml --format json

# Output as docsmith-compatible YAML (for Word document generation)
cloudcosting estimate config.yaml --format docsmith -o estimate.yaml

# Pipe directly to docsmith for Word document
cloudcosting estimate config.yaml --format docsmith | docsmith -

# Write to file
cloudcosting estimate config.yaml -o costs.yaml

# Use a specific AWS credentials profile
cloudcosting estimate config.yaml --profile production
```

### Comparing Scenarios

Compare costs across multiple infrastructure configurations. Produces a docsmith-compatible YAML document with side-by-side cost tables.

```bash
# Compare two configurations
cloudcosting compare Small:small.yaml Large:large.yaml

# With custom document title and line-item detail
cloudcosting compare Small:small.yaml Large:large.yaml \
  --title "Project Phoenix" --detail

# Write comparison to file, then generate Word document
cloudcosting compare Small:small.yaml Large:large.yaml -o comparison.yaml
docsmith comparison.yaml

# Bare paths (scenario names derived from filenames)
cloudcosting compare small.yaml large.yaml

# Multiple scenarios with a shared AWS profile
cloudcosting compare Small:s.yaml Medium:m.yaml Large:l.yaml --profile production
```

Scenario specs use the format `Name:path` or just `path`. When the name is omitted, the filename stem is used (e.g., `small.yaml` becomes scenario name `small`).

**Tip:** Label your resources in config files for meaningful comparisons. Resources are aligned across scenarios by their `label` field. Without labels, resources get auto-generated names like `EC2 t3.micro` which may not match as expected across different configurations.

### Cache Management

```bash
cloudcosting cache status
cloudcosting cache refresh aws
cloudcosting cache refresh
```

All commands can also be run via `python -m cloudcosting` (e.g., `python -m cloudcosting estimate config.yaml`).

### Output Formats

| Format | Flag | Description |
|--------|------|-------------|
| `yaml` | `--format yaml` (default) | Structured estimate with full metadata |
| `json` | `--format json` | Same structure as YAML, serialized as JSON |
| `docsmith` | `--format docsmith` | [docsmith](https://pypi.org/project/docsmith/)-compatible YAML for Word document generation |

The `compare` command always produces docsmith-compatible YAML output.

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
pytest tests/ -v

# Run specific test module
pytest tests/unit/test_domain.py -v
pytest tests/unit/test_composer.py -v
pytest tests/unit/providers/aws/test_rds.py -v
```

79 unit tests covering domain invariants, config validation, cache behavior, calculator arithmetic, full estimation pipeline, and comparison composition.

## Adding New Resource Types

1. Create a calculator module in `providers/aws/calculators/` with `validate()` and `estimate()` functions
2. Register it in `providers/aws/provider.py` `CALCULATOR_REGISTRY`
3. Add tests in `tests/unit/providers/aws/`

## Adding New Providers

1. Create a provider package under `providers/` (e.g., `providers/azure/`)
2. Implement the same interface as `AwsProvider` (with `estimate_resources()`)
3. Register it in `providers/registry.py`
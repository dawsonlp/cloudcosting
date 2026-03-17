# Cloud Cost Estimator -- Implementation Checklist

Per our standards: create checklist, get approval, implement.

Construction order follows the technical design (domain first, tests alongside, infrastructure last).

---

## Phase 1: Project Scaffolding

- [ ] **1.1** Create `cloudcosting/` project structure with `pyproject.toml` (PEP 621 + hatchling)
- [ ] **1.2** Create `src/cloudcosting/__init__.py` with version from importlib.metadata
- [ ] **1.3** Create `src/cloudcosting/__main__.py` stub
- [ ] **1.4** Set up venv, install dev dependencies, verify `python -m cloudcosting` runs
- [ ] **1.5** Create empty test directories (`tests/unit/`, `tests/integration/`, `tests/unit/providers/aws/`)

## Phase 2: Domain Objects + Domain Tests

- [ ] **2.1** `domain.py`: Exception hierarchy (CloudCostError, ConfigError, ProviderError, PricingError, CacheError)
- [ ] **2.2** `domain.py`: Input dataclasses (ResourceSpec, EstimationConfig)
- [ ] **2.3** `domain.py`: Output dataclasses (CostLineItem, ResourceCost, ResourceError, ProviderEstimate, Estimate)
- [ ] **2.4** `domain.py`: `to_dict()` methods on all output dataclasses
- [ ] **2.5** `tests/unit/test_domain.py`: Property tests -- conservation (sum of line items == monthly total), non-negative costs, to_dict round-trip produces valid YAML/JSON serializable dicts

## Phase 3: Price Cache + Cache Tests

- [ ] **3.1** `cache.py`: PriceCache class -- store, retrieve, staleness detection
- [ ] **3.2** `cache.py`: TTL expiry logic (fresh vs stale vs missing)
- [ ] **3.3** `cache.py`: Provider-scoped and global refresh (delete cached entries)
- [ ] **3.4** `cache.py`: Cache key hashing (deterministic from tuple)
- [ ] **3.5** `tests/unit/test_cache.py`: Store/retrieve returns same data
- [ ] **3.6** `tests/unit/test_cache.py`: Expired entries not returned as fresh; returned as stale when requested
- [ ] **3.7** `tests/unit/test_cache.py`: Provider-scoped refresh removes only that provider
- [ ] **3.8** `tests/unit/test_cache.py`: Global refresh removes all entries

## Phase 4: Config Loader + Config Tests

- [ ] **4.1** `config.py`: Load YAML, validate structure (resources list, required common fields)
- [ ] **4.2** `config.py`: Top-level provider/region defaults applied to resources missing those fields
- [ ] **4.3** `config.py`: Provider ID validation (optional registry parameter, skip if not provided)
- [ ] **4.4** `config.py`: Pass-through of provider-specific params without validation
- [ ] **4.5** `tests/unit/test_config.py`: Valid configs parse correctly
- [ ] **4.6** `tests/unit/test_config.py`: Missing required fields produce ConfigError naming the field
- [ ] **4.7** `tests/unit/test_config.py`: Provider-specific fields pass through untouched
- [ ] **4.8** `tests/unit/test_config.py`: Top-level defaults are applied; resource-level overrides win

## Phase 5: AWS Pricing Adapter

- [ ] **5.1** `providers/aws/__init__.py` and `providers/__init__.py`
- [ ] **5.2** `providers/aws/pricing.py`: AWS pricing adapter -- boto3 client creation (us-east-1 endpoint)
- [ ] **5.3** `providers/aws/pricing.py`: GetProducts query builder for different service codes
- [ ] **5.4** `providers/aws/pricing.py`: Response parser -- extract unit prices from nested JSON
- [ ] **5.5** `providers/aws/pricing.py`: Cache integration (check cache first, write to cache after fetch)
- [ ] **5.6** `providers/aws/pricing.py`: Fallback to stale cache on API failure

## Phase 6: AWS Resource Calculators + Tests

- [ ] **6.1** `providers/aws/calculators/__init__.py`
- [ ] **6.2** `providers/aws/calculators/rds.py`: Validate + estimate (instance, storage, backup components; Multi-AZ doubling)
- [ ] **6.3** `tests/unit/providers/aws/test_rds.py`: Correctness with known unit prices, property tests (monotonicity, conservation)
- [ ] **6.4** `providers/aws/calculators/ec2.py`: Validate + estimate (instance * count)
- [ ] **6.5** `tests/unit/providers/aws/test_ec2.py`: Correctness, scaling property
- [ ] **6.6** `providers/aws/calculators/nat_gateway.py`: Validate + estimate (fixed hourly * count, note about data transfer)
- [ ] **6.7** `tests/unit/providers/aws/test_nat_gateway.py`: Correctness, scaling property
- [ ] **6.8** `providers/aws/calculators/alb.py`: Validate + estimate (fixed hourly * count, note about LCU)
- [ ] **6.9** `tests/unit/providers/aws/test_alb.py`: Correctness, scaling property
- [ ] **6.10** `providers/aws/calculators/ebs.py`: Validate + estimate (per-GB * size * count)
- [ ] **6.11** `tests/unit/providers/aws/test_ebs.py`: Correctness, scaling property
- [ ] **6.12** `providers/aws/calculators/s3.py`: Validate + estimate (per-GB * size, note about requests)
- [ ] **6.13** `tests/unit/providers/aws/test_s3.py`: Correctness

## Phase 7: AWS Provider + Provider Registry

- [ ] **7.1** `providers/aws/provider.py`: Implements Provider Protocol -- resource type registry, validate-then-estimate delegation
- [ ] **7.2** `registry.py`: ProviderRegistry -- lookup, list, register
- [ ] **7.3** Wire Config Loader's provider ID validation to use registry

## Phase 8: Estimator + Estimator Tests

- [ ] **8.1** `estimator.py`: Group resources by provider, delegate to providers, collect results
- [ ] **8.2** `estimator.py`: Aggregate totals (monthly/annual from successful resources only)
- [ ] **8.3** `estimator.py`: Partial success handling -- complete/partial indicator, error collection
- [ ] **8.4** `estimator.py`: Wrap unexpected exceptions as ResourceError
- [ ] **8.5** `tests/unit/test_estimator.py`: All-success produces complete status with correct totals
- [ ] **8.6** `tests/unit/test_estimator.py`: Mixed success/failure produces partial status, failed in errors
- [ ] **8.7** `tests/unit/test_estimator.py`: All-failure produces output with errors, no totals

## Phase 9: CLI

- [ ] **9.1** `cli.py`: Argument parsing (estimate command, --format, -o, --refresh, --refresh-provider, --cache-dir)
- [ ] **9.2** `cli.py`: Component wiring (create cache, providers, registry, config loader, estimator)
- [ ] **9.3** `cli.py`: Output serialization (YAML/JSON) to stdout or file
- [ ] **9.4** `cli.py`: Exit codes (0 complete/partial, 1 total failure)
- [ ] **9.5** `__main__.py`: Wire to cli.main()

## Phase 10: Integration Tests + Documentation

- [ ] **10.1** `tests/integration/test_aws_pricing.py`: Real API calls for each resource type (marked @pytest.mark.integration)
- [ ] **10.2** `tests/integration/test_aws_pricing.py`: Verify prices are non-zero and reasonable
- [ ] **10.3** `tests/integration/test_aws_pricing.py`: Verify cache populated after fetch
- [ ] **10.4** Create sample configuration file (`examples/aws_infrastructure.yaml`)
- [ ] **10.5** End-to-end test: run CLI with sample config, verify output structure and cached execution completes under 2 seconds (per requirements)
- [ ] **10.6** `README.md`: Setup, usage, configuration format, output format

## Summary

- **42 implementation items** across 10 phases
- Domain first (Phase 2), infrastructure last (Phase 9-10)
- Tests written alongside each component, not after
- Integration tests are separate and optional (require AWS credentials)
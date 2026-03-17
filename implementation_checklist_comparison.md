# Implementation Checklist: Cost Comparison Command

**Based on:** technical_design_comparison.yaml v1, design_comparison.yaml v4, requirements_comparison.yaml v3

**Construction order:** Composer -> Composer tests -> argparse migration -> Compare subcommand -> Compare CLI tests -> Version bump -> README

**Testing approach:** Per RULES.md testing philosophy -- concentrate effort where risk lives. The Comparison Composer contains the domain decisions (alignment, ordering, duplicate handling, absent marking). The CLI is thin orchestration. argparse migration is low-risk and verified manually.

---

## Phase 1: Comparison Composer (Pure Function)

- [ ] Create `src/cloudcosting/composer.py`
  - [ ] `compose_comparison(scenarios, include_detail, title, subtitle, intro_text) -> dict`
  - [ ] Resource alignment: ordered dict for first-seen label ordering
  - [ ] Lookup matrix: `dict[str, dict[str, ResourceCost | None]]`
  - [ ] Duplicate label detection within a scenario (first wins, warning returned)
  - [ ] Private `_fmt(amount) -> str` for dollar formatting ($1,234.56)
  - [ ] Content blocks: intro text (if provided)
  - [ ] Content blocks: Cost Summary table (Monthly/Annual per scenario)
  - [ ] Content blocks: Resource Comparison table (per-resource monthly, '--' for absent)
  - [ ] Content blocks: Resource Details sections (when include_detail=True)
    - [ ] Line-item alignment by name across scenarios
    - [ ] Notes attributed to scenario name
  - [ ] Content blocks: Estimation Context section
    - [ ] Metadata table (provider, region, pricing date, cache, status per scenario)
    - [ ] Warnings bullets attributed to scenario
    - [ ] Errors bullets attributed to scenario
  - [ ] Return dict with title, subtitle, status, content keys

## Phase 2: Composer Tests

- [ ] Create `tests/unit/test_composer.py`
  - [ ] Create test fixtures: helper to build synthetic Estimate/ProviderEstimate/ResourceCost objects
  - [ ] Test: two identical scenarios -- all resources matched, no absent markers
  - [ ] Test: scenarios with different resource sets -- '--' for missing resources
  - [ ] Test: resource ordering follows first-seen order across scenarios
  - [ ] Test: include_detail=True adds line-item tables and notes
  - [ ] Test: include_detail=False omits line-item sections
  - [ ] Test: custom title, subtitle, intro_text appear in output
  - [ ] Test: default title when none provided
  - [ ] Test: duplicate labels within a scenario -- first wins, warning returned
  - [ ] Test: multi-provider scenario -- metadata table lists all providers
  - [ ] Test: scenario with warnings/errors -- attributed to correct scenario
  - [ ] Test: scenario with status='partial' -- noted in context section
  - [ ] Test: empty scenario (no resources, only errors) -- handled gracefully
- [ ] Run composer tests -- confirm green

## Phase 3: argparse Migration

- [ ] Rewrite `cli.py` main() to use argparse with subparsers
  - [ ] Top-level parser with --version
  - [ ] `estimate` subparser with: config_path, --format, -o, --profile
  - [ ] `cache` subparser with: subcommand (refresh/status), optional provider
  - [ ] Preserve `RawDescriptionHelpFormatter` with custom epilog for examples, workflow, links
  - [ ] Preserve all existing exit codes (0 success, 1 error; note: argparse uses 2 for parse errors)
  - [ ] Preserve stderr/stdout behavior (help to stdout, errors to stderr)
  - [ ] Preserve all summary output to stderr after estimation
- [ ] Manual verification: --help, --version, estimate, cache status all work
- [ ] Run all existing tests -- confirm green

## Phase 4: Compare Subcommand

- [ ] Add `compare` subparser to cli.py
  - [ ] Positional: scenario specs (nargs='+', format name:path or just path)
  - [ ] --title, --subtitle, --intro, --detail, -o, --profile flags
  - [ ] `_parse_scenario(spec) -> tuple[str, Path]` helper
  - [ ] Scenario count validation (minimum 2, warn >5)
  - [ ] Progress indication to stderr per scenario ("Estimating: {name}...")
  - [ ] Per-scenario `run_estimation()` call with CloudCostError handling
  - [ ] Currency validation across all ProviderEstimate objects
  - [ ] Call `compose_comparison()` with results
  - [ ] YAML serialization and output (stdout or -o file)
  - [ ] Summary to stderr (scenario count, resource count, failures)
- [ ] Update help text: epilog with compare examples, workflow, label guidance

## Phase 5: Compare CLI Tests

- [ ] Create `tests/unit/test_cli_compare.py` (compare-specific decisions only)
  - [ ] Test: scenario parsing -- 'Name:path' splits correctly, bare path uses stem
  - [ ] Test: currency validation rejects mixed currencies
- [ ] Run all tests -- confirm green

## Phase 6: Finalize

- [ ] Bump version in pyproject.toml (1.2.0 -> 1.3.0)
- [ ] Update `README.md` with compare command documentation
  - [ ] Add compare to command list
  - [ ] Add compare usage examples
  - [ ] Add compare workflow section
  - [ ] Note about labeling resources for comparison
- [ ] Run full test suite one final time
- [ ] Git commit: `feat: add compare command for multi-scenario cost comparison`
- [ ] Git tag: v1.3.0
- [ ] Push

---

## Verification Criteria

- [ ] `cloudcosting compare Small:small.yaml Large:large.yaml` produces valid docsmith YAML
- [ ] `cloudcosting compare Small:small.yaml Large:large.yaml | docsmith -` produces a Word document
- [ ] `cloudcosting estimate config.yaml` still works identically to before
- [ ] `cloudcosting --help` shows all three subcommands
- [ ] `cloudcosting compare --help` shows compare-specific help
- [ ] All unit tests pass
- [ ] No changes to domain.py, estimator.py, config.py, formatters.py, cache.py, or provider modules
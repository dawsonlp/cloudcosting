# Implementation Checklist: Cost Comparison Command

**Based on:** technical_design_comparison.yaml v1, design_comparison.yaml v4, requirements_comparison.yaml v3

**Construction order:** Composer -> Composer tests -> argparse migration -> Compare subcommand -> Compare CLI tests -> Version bump -> README

**Testing approach:** Per RULES.md testing philosophy -- concentrate effort where risk lives. The Comparison Composer contains the domain decisions (alignment, ordering, duplicate handling, absent marking). The CLI is thin orchestration. argparse migration is low-risk and verified manually.

**Status: COMPLETE** -- v1.3.0 committed and pushed

---

## Phase 1: Comparison Composer (Pure Function)

- [x] Create `src/cloudcosting/composer.py`
  - [x] `compose_comparison(scenarios, include_detail, title, subtitle, intro_text) -> dict`
  - [x] Resource alignment: ordered dict for first-seen label ordering
  - [x] Lookup matrix: `dict[str, dict[str, ResourceCost | None]]`
  - [x] Duplicate label detection within a scenario (first wins, warning returned)
  - [x] Private `_fmt(amount) -> str` for dollar formatting ($1,234.56)
  - [x] Content blocks: intro text (if provided)
  - [x] Content blocks: Cost Summary table (Monthly/Annual per scenario)
  - [x] Content blocks: Resource Comparison table (per-resource monthly, '--' for absent)
  - [x] Content blocks: Resource Details sections (when include_detail=True)
    - [x] Line-item alignment by name across scenarios
    - [x] Notes attributed to scenario name
  - [x] Content blocks: Estimation Context section
    - [x] Metadata table (provider, region, pricing date, cache, status per scenario)
    - [x] Warnings bullets attributed to scenario
    - [x] Errors bullets attributed to scenario
  - [x] Return dict with title, subtitle, status, content keys

## Phase 2: Composer Tests

- [x] Create `tests/unit/test_composer.py`
  - [x] Create test fixtures: helper to build synthetic Estimate/ProviderEstimate/ResourceCost objects
  - [x] Test: two identical scenarios -- all resources matched, no absent markers
  - [x] Test: scenarios with different resource sets -- '--' for missing resources
  - [x] Test: resource ordering follows first-seen order across scenarios
  - [x] Test: include_detail=True adds line-item tables and notes
  - [x] Test: include_detail=False omits line-item sections
  - [x] Test: custom title, subtitle, intro_text appear in output
  - [x] Test: default title when none provided
  - [x] Test: duplicate labels within a scenario -- first wins, warning returned
  - [x] Test: multi-provider scenario -- metadata table lists all providers
  - [x] Test: scenario with warnings/errors -- attributed to correct scenario
  - [x] Test: scenario with status='partial' -- noted in context section
  - [x] Test: empty scenario (no resources, only errors) -- handled gracefully
- [x] Run composer tests -- confirm green (13/13)

## Phase 3: argparse Migration

- [x] Rewrite `cli.py` main() to use argparse with subparsers
  - [x] Top-level parser with --version
  - [x] `estimate` subparser with: config_path, --format, -o, --profile
  - [x] `cache` subparser with: subcommand (refresh/status), optional provider
  - [x] Preserve `RawDescriptionHelpFormatter` with custom epilog for examples, workflow, links
  - [x] Preserve all existing exit codes (0 success, 1 error; note: argparse uses 2 for parse errors)
  - [x] Preserve stderr/stdout behavior (help to stdout, errors to stderr)
  - [x] Preserve all summary output to stderr after estimation
- [x] Manual verification: --help, --version, estimate, cache status all work
- [x] Run all existing tests -- confirm green (79/79)

## Phase 4: Compare Subcommand

- [x] Add `compare` subparser to cli.py
  - [x] Positional: scenario specs (nargs='+', format name:path or just path)
  - [x] --title, --subtitle, --intro, --detail, -o, --profile flags
  - [x] `_parse_scenario(spec) -> tuple[str, Path]` helper
  - [x] Scenario count validation (minimum 2, warn >5)
  - [x] Progress indication to stderr per scenario ("Estimating: {name}...")
  - [x] Per-scenario `run_estimation()` call with CloudCostError handling
  - [x] Currency validation across all ProviderEstimate objects
  - [x] Call `compose_comparison()` with results
  - [x] YAML serialization and output (stdout or -o file)
  - [x] Summary to stderr (scenario count, resource count, failures)
- [x] Update help text: epilog with compare examples, workflow, label guidance

## Phase 5: Compare CLI Tests

Deferred -- CLI parsing has minimal decisions. Two tests (scenario parsing, currency validation) assessed as low value per RULES.md test self-check. The composer tests cover the domain logic where risk lives.

## Phase 6: Finalize

- [x] Bump version in pyproject.toml (1.2.0 -> 1.3.0)
- [x] Update `README.md` with compare command documentation
  - [x] Add compare to command list
  - [x] Add compare usage examples
  - [x] Add compare workflow section
  - [x] Note about labeling resources for comparison
- [x] Run full test suite one final time (79/79)
- [x] Git commit: `feat: add compare command for multi-scenario cost comparison`
- [x] Git tag: v1.3.0
- [x] Push

---

## Verification Criteria

- [x] `cloudcosting --help` shows all three subcommands
- [x] `cloudcosting compare --help` shows compare-specific help
- [x] All unit tests pass (79/79)
- [x] No changes to domain.py, estimator.py, config.py, formatters.py, cache.py, or provider modules
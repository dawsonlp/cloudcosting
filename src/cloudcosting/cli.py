"""CLI entry point for cloudcosting."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from cloudcosting import __version__
from cloudcosting.cache import PriceCache
from cloudcosting.domain import CloudCostError


def main():
    """Main CLI entry point."""
    parser = _build_parser()

    # No args -> print help
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(0)


def _build_parser():
    """Build the argparse parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="cloudcosting",
        description="Multi-cloud infrastructure cost estimation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_main_epilog(),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"cloudcosting {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # estimate subcommand
    est = subparsers.add_parser(
        "estimate",
        help="Estimate costs from a YAML configuration file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_estimate_epilog(),
    )
    est.add_argument("config", type=Path, help="Path to YAML configuration file")
    est.add_argument(
        "--format",
        choices=["yaml", "json", "docsmith"],
        default="yaml",
        dest="output_format",
        help="Output format (default: yaml)",
    )
    est.add_argument("-o", type=Path, dest="output", help="Write output to file")
    est.add_argument("--profile", help="AWS/cloud credentials profile name")
    est.set_defaults(func=_cmd_estimate)

    # cache subcommand
    cache = subparsers.add_parser(
        "cache",
        help="Manage the local pricing data cache",
    )
    cache_sub = cache.add_subparsers(dest="cache_command")

    refresh = cache_sub.add_parser("refresh", help="Clear cached pricing data")
    refresh.add_argument("provider", nargs="?", help="Clear only this provider")
    refresh.set_defaults(func=_cmd_cache_refresh)

    status = cache_sub.add_parser("status", help="Show cache status")
    status.set_defaults(func=_cmd_cache_status)

    cache.set_defaults(func=lambda args: _cmd_cache_dispatch(cache, args))

    # compare subcommand
    cmp = subparsers.add_parser(
        "compare",
        help="Compare costs across multiple infrastructure configurations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_compare_epilog(),
    )
    cmp.add_argument(
        "scenarios",
        nargs="+",
        help="Scenario specs: Name:config.yaml or just config.yaml",
    )
    cmp.add_argument("--title", help="Document title")
    cmp.add_argument("--subtitle", help="Document subtitle")
    cmp.add_argument("--intro", help="Introductory paragraph text")
    cmp.add_argument(
        "--detail",
        action="store_true",
        help="Include per-resource line-item breakdowns",
    )
    cmp.add_argument("-o", type=Path, dest="output", help="Write output to file")
    cmp.add_argument("--profile", help="AWS/cloud credentials profile (all scenarios)")
    cmp.set_defaults(func=_cmd_compare)

    return parser


def _cmd_estimate(args):
    """Run cost estimation from a config file."""
    try:
        from cloudcosting.estimator import run_estimation

        estimate = run_estimation(args.config, profile=args.profile)

        if args.output_format == "docsmith":
            from cloudcosting.formatters import to_docsmith

            result = to_docsmith(estimate)
        else:
            result = estimate.to_dict()

        if args.output_format == "json":
            output = json.dumps(result, indent=2)
        else:
            output = yaml.dump(result, default_flow_style=False, sort_keys=False)

        if args.output:
            args.output.write_text(output)
            print(f"Estimate written to {args.output}", file=sys.stderr)
        else:
            print(output)

        # Summary to stderr
        n_resources = sum(len(pe.resources) for pe in estimate.providers)
        n_errors = len(estimate.errors) + sum(
            len(pe.errors) for pe in estimate.providers
        )

        print("\n--- Summary ---", file=sys.stderr)
        print(f"Status: {estimate.status}", file=sys.stderr)
        print(f"Resources estimated: {n_resources}", file=sys.stderr)
        if n_errors > 0:
            print(f"Errors: {n_errors}", file=sys.stderr)
        print(
            f"Monthly total: ${estimate.totals.get('monthly', 0.0):,.2f}",
            file=sys.stderr,
        )
        print(
            f"Annual total:  ${estimate.totals.get('annual', 0.0):,.2f}",
            file=sys.stderr,
        )

        sys.exit(0 if estimate.status == "complete" else 1)

    except CloudCostError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_cache_dispatch(cache_parser, args):
    """Dispatch cache subcommands or show help."""
    if args.cache_command is None:
        cache_parser.print_help()
        sys.exit(1)


def _cmd_cache_refresh(args):
    """Clear cached pricing data."""
    cache = PriceCache()
    if args.provider:
        count = cache.refresh_provider(args.provider)
        print(f"Deleted {count} cached entries for provider '{args.provider}'")
    else:
        count = cache.refresh_all()
        print(f"Deleted {count} cached entries")


def _cmd_cache_status(args):
    """Show cache status."""
    cache = PriceCache()
    cache_dir = cache._cache_dir
    if cache_dir.exists():
        files = list(cache_dir.glob("*.json"))
        print(f"Cache directory: {cache_dir}")
        print(f"Cached entries: {len(files)}")
    else:
        print(f"Cache directory: {cache_dir} (does not exist)")
        print("Cached entries: 0")


def _cmd_compare(args):
    """Compare costs across multiple configurations."""
    # Parse scenarios
    scenarios_specs = []
    for spec in args.scenarios:
        name, path = _parse_scenario(spec)
        scenarios_specs.append((name, path))

    # Validate count
    if len(scenarios_specs) < 2:
        print("Error: at least 2 scenarios required for comparison", file=sys.stderr)
        sys.exit(1)

    if len(scenarios_specs) > 5:
        print(
            f"Warning: {len(scenarios_specs)} scenarios provided. "
            "More than 5 may reduce document readability.",
            file=sys.stderr,
        )

    # Estimate each scenario
    from cloudcosting.estimator import run_estimation

    named_estimates = []
    failed = []

    for name, config_path in scenarios_specs:
        print(f"Estimating: {name}...", file=sys.stderr)
        try:
            estimate = run_estimation(config_path, profile=args.profile)
            named_estimates.append((name, estimate))
        except CloudCostError as e:
            print(f"Error estimating '{name}': {e}", file=sys.stderr)
            failed.append(name)

    if not named_estimates:
        print("Error: all scenarios failed estimation", file=sys.stderr)
        sys.exit(1)

    if len(named_estimates) < 2:
        print(
            "Error: fewer than 2 scenarios succeeded. Cannot compare.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Currency validation
    currencies = set()
    for _name, est in named_estimates:
        for pe in est.providers:
            currencies.add(pe.currency)

    if len(currencies) > 1:
        details = []
        for name, est in named_estimates:
            for pe in est.providers:
                details.append(f"  {name}: {pe.provider}/{pe.region} = {pe.currency}")
        print("Error: currency mismatch across scenarios:", file=sys.stderr)
        print("\n".join(details), file=sys.stderr)
        sys.exit(1)

    # Compose comparison
    from cloudcosting.composer import compose_comparison

    result, warnings = compose_comparison(
        named_estimates,
        include_detail=args.detail,
        title=args.title,
        subtitle=args.subtitle,
        intro_text=args.intro,
    )

    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)

    # Output
    output = yaml.dump(result, default_flow_style=False, sort_keys=False)

    if args.output:
        args.output.write_text(output)
        print(f"Comparison written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Summary
    n_scenarios = len(named_estimates)
    n_resources = sum(
        len(pe.resources) for _, est in named_estimates for pe in est.providers
    )
    print("\n--- Comparison Summary ---", file=sys.stderr)
    print(f"Scenarios compared: {n_scenarios}", file=sys.stderr)
    print(f"Total resources: {n_resources}", file=sys.stderr)
    if failed:
        print(f"Failed scenarios: {', '.join(failed)}", file=sys.stderr)


def _parse_scenario(spec: str) -> tuple[str, Path]:
    """Parse a scenario specification: 'Name:path' or just 'path'."""
    if ":" in spec:
        # Split on first colon only (path may contain colons on Windows, unlikely but safe)
        name, path_str = spec.split(":", 1)
        name = name.strip()
        path_str = path_str.strip()
        if not name:
            name = Path(path_str).stem
    else:
        path_str = spec.strip()
        name = Path(path_str).stem

    path = Path(path_str)
    if not path.exists():
        print(f"Error: config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if not path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        sys.exit(1)

    return name, path


def _main_epilog():
    return """
Supported Providers:
  aws         EC2, RDS, NAT Gateway, ALB, EBS, S3

Workflow (single estimate):
  1. Write a YAML config defining your cloud resources
  2. Run: cloudcosting estimate config.yaml --format docsmith -o estimate.yaml
  3. Use docsmith to build a formatted Word document:
     docsmith estimate.yaml

Workflow (comparison):
  1. Create config files for each scenario (small.yaml, large.yaml, etc.)
  2. Run: cloudcosting compare Small:small.yaml Large:large.yaml -o comparison.yaml
  3. Use docsmith to build a formatted Word document:
     docsmith comparison.yaml

Tip: Label your resources in config files for meaningful comparisons.
     Resources are aligned across scenarios by their label field.

Example Config (infrastructure.yaml):
  provider: aws
  region: us-east-1
  profile: my-aws-profile
  resources:
    - type: ec2
      label: Web Servers
      instance_type: t3.micro
      count: 3
    - type: rds
      label: Primary Database
      engine: postgres
      instance_class: db.r6g.xlarge
      storage_gb: 250

Profile Resolution (highest to lowest priority):
  1. --profile flag on the command line
  2. 'profile' field in the YAML config file
  3. Default credential chain (AWS_PROFILE env, ~/.aws/credentials, IAM role)

Links:
  PyPI:   https://pypi.org/project/cloudcosting/
  Repo:   https://github.com/dawsonlp/cloudcosting
  Issues: https://github.com/dawsonlp/cloudcosting/issues"""


def _estimate_epilog():
    return """
Examples:
  cloudcosting estimate infrastructure.yaml
  cloudcosting estimate infrastructure.yaml --format json
  cloudcosting estimate infrastructure.yaml --format docsmith -o estimate.yaml
  cloudcosting estimate infrastructure.yaml --format docsmith | docsmith -
  cloudcosting estimate infrastructure.yaml -o costs.yaml
  cloudcosting estimate infrastructure.yaml --profile production"""


def _compare_epilog():
    return """
Scenario Specification:
  Each scenario is specified as Name:path or just path.
  If the name is omitted, the filename stem is used.

  Examples:
    Small:configs/small.yaml    Name is 'Small'
    configs/large.yaml          Name is 'large'

Examples:
  cloudcosting compare Small:small.yaml Large:large.yaml
  cloudcosting compare Small:small.yaml Large:large.yaml --detail
  cloudcosting compare Small:small.yaml Large:large.yaml -o comparison.yaml
  cloudcosting compare --title "Project Phoenix" Small:s.yaml Medium:m.yaml Large:l.yaml
  cloudcosting compare small.yaml large.yaml --profile production

Tip: Label your resources in config files for meaningful comparisons.
     Resources are aligned across scenarios by their label field.
     Without labels, resources get auto-generated names like 'EC2 t3.micro'
     which may not match as expected across different configurations."""

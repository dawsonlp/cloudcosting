"""CLI entry point for cloudcosting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from cloudcosting import __version__
from cloudcosting.cache import PriceCache
from cloudcosting.domain import CloudCostError


def main():
    """Main CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _print_help()
        sys.exit(0)

    if args[0] in ("-v", "--version"):
        print(f"cloudcosting {__version__}")
        sys.exit(0)

    command = args[0]

    if command == "estimate":
        _cmd_estimate(args[1:])
    elif command == "cache":
        _cmd_cache(args[1:])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        _print_help()
        sys.exit(1)


def _cmd_estimate(args: list[str]):
    """Run cost estimation from a config file."""
    if not args:
        print(
            "Usage: cloudcosting estimate <config.yaml> [--format yaml|json] [-o output] [--profile name]",
            file=sys.stderr,
        )
        sys.exit(1)

    config_path = Path(args[0])
    output_format = "yaml"
    output_path = None
    profile = None

    i = 1
    while i < len(args):
        if args[i] == "--format" and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        elif args[i] == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        else:
            print(f"Unknown option: {args[i]}", file=sys.stderr)
            sys.exit(1)

    try:
        from cloudcosting.estimator import run_estimation

        estimate = run_estimation(config_path, profile=profile)
        result = estimate.to_dict()

        if output_format == "json":
            output = json.dumps(result, indent=2)
        else:
            output = yaml.dump(result, default_flow_style=False, sort_keys=False)

        if output_path:
            output_path.write_text(output)
            print(f"Estimate written to {output_path}", file=sys.stderr)
        else:
            print(output)

        # Print summary to stderr
        totals = result["estimate"]["totals"]
        status = result["estimate"]["status"]
        n_resources = sum(len(p["resources"]) for p in result["estimate"]["providers"])
        n_errors = len(result["estimate"]["errors"]) + sum(
            len(p.get("errors", [])) for p in result["estimate"]["providers"]
        )

        print("\n--- Summary ---", file=sys.stderr)
        print(f"Status: {status}", file=sys.stderr)
        print(f"Resources estimated: {n_resources}", file=sys.stderr)
        if n_errors > 0:
            print(f"Errors: {n_errors}", file=sys.stderr)
        print(f"Monthly total: ${totals['monthly']:,.2f}", file=sys.stderr)
        print(f"Annual total:  ${totals['annual']:,.2f}", file=sys.stderr)

        sys.exit(0 if status == "complete" else 1)

    except CloudCostError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_cache(args: list[str]):
    """Cache management commands."""
    if not args:
        print("Usage: cloudcosting cache <refresh|status>", file=sys.stderr)
        sys.exit(1)

    subcommand = args[0]
    cache = PriceCache()

    if subcommand == "refresh":
        provider = args[1] if len(args) > 1 else None
        if provider:
            count = cache.refresh_provider(provider)
            print(f"Deleted {count} cached entries for provider '{provider}'")
        else:
            count = cache.refresh_all()
            print(f"Deleted {count} cached entries")
    elif subcommand == "status":
        cache_dir = cache._cache_dir
        if cache_dir.exists():
            files = list(cache_dir.glob("*.json"))
            print(f"Cache directory: {cache_dir}")
            print(f"Cached entries: {len(files)}")
        else:
            print(f"Cache directory: {cache_dir} (does not exist)")
            print("Cached entries: 0")
    else:
        print(f"Unknown cache command: {subcommand}", file=sys.stderr)
        sys.exit(1)


def _print_help():
    print(f"""cloudcosting {__version__} -- Multi-cloud infrastructure cost estimation

Fetches real-time pricing from cloud provider APIs (AWS Pricing API),
caches results locally, and produces structured YAML/JSON cost breakdowns
from a simple resource configuration file.

Output is designed for use with docsmith (https://pypi.org/project/docsmith/)
to generate professional Word documents from YAML cost estimates.

Usage:
  cloudcosting estimate <config.yaml> [--format yaml|json] [-o output_file] [--profile name]
  cloudcosting cache refresh [provider]
  cloudcosting cache status
  cloudcosting --version
  cloudcosting --help

Commands:
  estimate    Estimate costs from a YAML configuration file.
              Reads resource definitions, fetches current pricing from
              the cloud provider API (with local caching), and outputs
              a structured cost breakdown.

  cache       Manage the local pricing data cache.
    refresh   Clear cached pricing data (optionally for one provider).
    status    Show cache directory location and entry count.

Options:
  --format      Output format: yaml (default) or json.
  -o FILE       Write output to FILE instead of stdout.
  --profile NAME  AWS/cloud credentials profile to use. Overrides the
                  'profile' field in the YAML config file. If neither is
                  set, the default credential chain is used (AWS_PROFILE
                  env var, ~/.aws/credentials default profile, IAM role).

Supported Providers:
  aws         EC2, RDS, NAT Gateway, ALB, EBS, S3

Workflow:
  1. Write a YAML config defining your cloud resources
  2. Run: cloudcosting estimate config.yaml -o estimate.yaml
  3. Use docsmith to build a formatted report:
     docsmith build estimate.yaml -o report.docx

Example Config (infrastructure.yaml):
  provider: aws
  region: us-east-1
  profile: my-aws-profile        # optional: credentials profile
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

Examples:
  cloudcosting estimate infrastructure.yaml
  cloudcosting estimate infrastructure.yaml --format json
  cloudcosting estimate infrastructure.yaml -o costs.yaml
  cloudcosting estimate infrastructure.yaml --profile production
  cloudcosting cache refresh aws
  cloudcosting cache status

Links:
  PyPI:   https://pypi.org/project/cloudcosting/
  Repo:   https://github.com/dawsonlp/cloudcosting
  Issues: https://github.com/dawsonlp/cloudcosting/issues""")

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
            "Usage: cloudcosting estimate <config.yaml> [--format yaml|json] [-o output]",
            file=sys.stderr,
        )
        sys.exit(1)

    config_path = Path(args[0])
    output_format = "yaml"
    output_path = None

    i = 1
    while i < len(args):
        if args[i] == "--format" and i + 1 < len(args):
            output_format = args[i + 1]
            i += 2
        elif args[i] == "-o" and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        else:
            print(f"Unknown option: {args[i]}", file=sys.stderr)
            sys.exit(1)

    try:
        from cloudcosting.estimator import run_estimation

        estimate = run_estimation(config_path)
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
    print(f"""cloudcosting {__version__} - Multi-cloud infrastructure cost estimation

Usage:
  cloudcosting estimate <config.yaml> [--format yaml|json] [-o output_file]
  cloudcosting cache refresh [provider]
  cloudcosting cache status
  cloudcosting --version
  cloudcosting --help

Commands:
  estimate    Run cost estimation from a YAML configuration file
  cache       Manage the pricing data cache

Examples:
  cloudcosting estimate infrastructure.yaml
  cloudcosting estimate infrastructure.yaml --format json
  cloudcosting estimate infrastructure.yaml -o costs.yaml
  cloudcosting cache refresh aws
  cloudcosting cache status""")

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dbt_semguard import __version__
from dbt_semguard.diffing import diff_contracts
from dbt_semguard.extractors import (
    extract_contract_from_git_ref,
    extract_contract_from_manifest,
    extract_contract_from_yaml_dir,
)
from dbt_semguard.models import SemanticContract
from dbt_semguard.reporting import build_report, render_report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            return _run_extract(args)
        if args.command in {"diff", "check"}:
            return _run_compare(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="semguard")
    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--source", choices=["yaml", "manifest"], required=True)
    extract_parser.add_argument("--git-ref")
    extract_parser.add_argument("--project-dir")
    extract_parser.add_argument("--manifest")
    extract_parser.add_argument("--output", required=True)

    for name in ("diff", "check"):
        compare_parser = subparsers.add_parser(name)
        compare_parser.add_argument("--base-ref")
        compare_parser.add_argument("--head-ref")
        compare_parser.add_argument("--project-dir")
        compare_parser.add_argument("--base-contract")
        compare_parser.add_argument("--head-contract")
        compare_parser.add_argument("--base-manifest")
        compare_parser.add_argument("--head-manifest")
        compare_parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
        compare_parser.add_argument("--fail-on", choices=["safe", "risky", "breaking"], default="breaking")

    return parser


def _run_extract(args: argparse.Namespace) -> int:
    if args.source == "yaml":
        if args.git_ref:
            contract = extract_contract_from_git_ref(args.project_dir or Path.cwd(), args.git_ref)
        else:
            if not args.project_dir:
                raise ValueError("YAML extraction requires either --git-ref or --project-dir.")
            contract = extract_contract_from_yaml_dir(args.project_dir)
    else:
        if not args.manifest:
            raise ValueError("Manifest extraction requires --manifest.")
        contract = extract_contract_from_manifest(args.manifest)

    output_path = Path(args.output)
    output_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    return 0


def _run_compare(args: argparse.Namespace) -> int:
    mode, base_contract, head_contract = _load_compare_inputs(args)
    report = build_report(
        diff_contracts(base_contract, head_contract),
        fail_on=args.fail_on,
        metadata={"source_mode": mode, "parser_version": __version__},
    )
    print(render_report(report, args.format))
    if args.command == "check" and report.blocking:
        return 1
    return 0


def _load_compare_inputs(args: argparse.Namespace) -> tuple[str, SemanticContract, SemanticContract]:
    if args.base_ref or args.head_ref:
        if not (args.base_ref and args.head_ref):
            raise ValueError("Git comparison requires both --base-ref and --head-ref.")
        project_dir = args.project_dir or Path.cwd()
        return (
            "git",
            extract_contract_from_git_ref(project_dir, args.base_ref),
            extract_contract_from_git_ref(project_dir, args.head_ref),
        )

    if args.base_contract or args.head_contract:
        if not (args.base_contract and args.head_contract):
            raise ValueError("Contract comparison requires both --base-contract and --head-contract.")
        return (
            "contract",
            SemanticContract.from_json_file(args.base_contract),
            SemanticContract.from_json_file(args.head_contract),
        )

    if args.base_manifest or args.head_manifest:
        if not (args.base_manifest and args.head_manifest):
            raise ValueError("Manifest comparison requires both --base-manifest and --head-manifest.")
        return (
            "manifest",
            extract_contract_from_manifest(args.base_manifest),
            extract_contract_from_manifest(args.head_manifest),
        )

    raise ValueError("Provide one input mode: refs, contracts, or manifests.")


if __name__ == "__main__":
    raise SystemExit(main())

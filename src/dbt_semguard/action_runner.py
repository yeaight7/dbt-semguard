from __future__ import annotations

import os
import re
from pathlib import Path

from dbt_semguard import __version__
from dbt_semguard.diffing import diff_contracts
from dbt_semguard.extractors import (
    extract_contract_from_git_ref,
    extract_contract_from_manifest,
)
from dbt_semguard.models import Report, SemanticContract
from dbt_semguard.reporting import build_report, render_report

DEFAULT_OUTPUT_BASENAME = "semguard-report"
VALID_FAIL_ON = ("breaking", "risky", "safe")


def execute_action(
    *,
    base_ref: str | None = None,
    head_ref: str | None = None,
    project_dir: str | Path | None = None,
    base_manifest: str | Path | None = None,
    head_manifest: str | Path | None = None,
    fail_on: str = "breaking",
    summary_path: str | Path | None = None,
    github_output_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    output_basename: str | None = None,
) -> Report:
    _validate_fail_on(fail_on)
    mode, base_contract, head_contract = _load_compare_inputs(
        base_ref=base_ref,
        head_ref=head_ref,
        project_dir=project_dir,
        base_manifest=base_manifest,
        head_manifest=head_manifest,
    )
    report = build_report(
        diff_contracts(base_contract, head_contract),
        fail_on=fail_on,
        metadata={"source_mode": mode, "parser_version": __version__},
    )
    output_root = Path(output_dir or Path.cwd())
    output_root.mkdir(parents=True, exist_ok=True)
    report_basename = _sanitize_output_basename(output_basename)
    (output_root / f"{report_basename}.json").write_text(render_report(report, "json"), encoding="utf-8")
    markdown = render_report(report, "markdown")
    (output_root / f"{report_basename}.md").write_text(markdown, encoding="utf-8")

    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary_file:
            summary_file.write(markdown)
            if not markdown.endswith("\n"):
                summary_file.write("\n")

    if github_output_path:
        _write_github_outputs(report, Path(github_output_path))

    return report


def main() -> int:
    execute_action(
        base_ref=_env("BASE_REF"),
        head_ref=_env("HEAD_REF"),
        project_dir=_env("PROJECT_DIR"),
        base_manifest=_env("BASE_MANIFEST"),
        head_manifest=_env("HEAD_MANIFEST"),
        fail_on=_env("FAIL_ON") or "breaking",
        summary_path=_env("GITHUB_STEP_SUMMARY"),
        github_output_path=_env("GITHUB_OUTPUT"),
        output_dir=_env("REPORT_DIR") or Path.cwd(),
        output_basename=_env("REPORT_BASENAME") or DEFAULT_OUTPUT_BASENAME,
    )
    return 0


def _write_github_outputs(report: Report, path: Path) -> None:
    outputs = {
        "highest-severity": report.highest_severity,
        "blocking": str(report.blocking).lower(),
        "breaking-count": str(report.summary["breaking"]),
        "risky-count": str(report.summary["risky"]),
        "safe-count": str(report.summary["safe"]),
    }
    with path.open("a", encoding="utf-8") as output_file:
        for key, value in outputs.items():
            output_file.write(f"{key}={value}\n")


def _validate_fail_on(fail_on: str) -> None:
    if fail_on not in VALID_FAIL_ON:
        expected = ", ".join(VALID_FAIL_ON)
        raise ValueError(f"Invalid fail_on '{fail_on}'. Expected one of: {expected}.")


def _sanitize_output_basename(output_basename: str | None) -> str:
    raw_name = (output_basename or DEFAULT_OUTPUT_BASENAME).strip()
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip(".-_")
    return sanitized or DEFAULT_OUTPUT_BASENAME


def _load_compare_inputs(
    *,
    base_ref: str | None,
    head_ref: str | None,
    project_dir: str | Path | None,
    base_manifest: str | Path | None,
    head_manifest: str | Path | None,
) -> tuple[str, SemanticContract, SemanticContract]:
    if base_manifest or head_manifest:
        if not (base_manifest and head_manifest):
            raise ValueError("Manifest comparison requires both BASE_MANIFEST and HEAD_MANIFEST.")
        return (
            "manifest",
            extract_contract_from_manifest(base_manifest),
            extract_contract_from_manifest(head_manifest),
        )

    if base_ref or head_ref:
        if not (base_ref and head_ref):
            raise ValueError("Git comparison requires both BASE_REF and HEAD_REF.")
        resolved_project_dir = Path(project_dir or Path.cwd())
        return (
            "git",
            extract_contract_from_git_ref(resolved_project_dir, base_ref),
            extract_contract_from_git_ref(resolved_project_dir, head_ref),
        )

    raise ValueError("Provide one input mode with refs or manifests.")


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())

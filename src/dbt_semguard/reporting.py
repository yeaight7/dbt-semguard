from __future__ import annotations

import json

from dbt_semguard.models import ChangeRecord, Report


SEVERITY_ORDER = {"safe": 0, "risky": 1, "breaking": 2}


def build_report(
    changes: list[ChangeRecord],
    *,
    fail_on: str = "breaking",
    metadata: dict[str, object] | None = None,
) -> Report:
    summary = {"breaking": 0, "risky": 0, "safe": 0}
    for change in changes:
        summary[change.severity] += 1

    highest = "safe"
    if changes:
        highest = max(changes, key=lambda item: SEVERITY_ORDER[item.severity]).severity

    blocking = SEVERITY_ORDER[highest] >= SEVERITY_ORDER[fail_on] and bool(changes)
    return Report(
        summary=summary,
        highest_severity=highest,
        blocking=blocking,
        changes=changes,
        metadata=metadata or {},
    )


def render_report(report: Report, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(report.model_dump(mode="json"), indent=2)
    if fmt == "markdown":
        return _render_markdown(report)
    if fmt == "text":
        return _render_text(report)
    raise ValueError(f"Unsupported format: {fmt}")


def _render_markdown(report: Report) -> str:
    lines = ["## dbt-semguard report", ""]
    if not report.changes:
        lines.append("No semantic changes detected.")
        lines.append("")
        lines.append("Status: passing")
        return "\n".join(lines)

    for severity in ("breaking", "risky", "safe"):
        matching = [change for change in report.changes if change.severity == severity]
        if not matching:
            continue
        lines.append(f"### {severity.capitalize()} changes")
        for change in matching:
            lines.append(f"- {change.message}")
        lines.append("")

    lines.append(f"Status: {'blocking' if report.blocking else 'passing'}")
    return "\n".join(lines)


def _render_text(report: Report) -> str:
    lines = ["dbt-semguard report", ""]
    if not report.changes:
        lines.append("No semantic changes detected.")
    else:
        for severity in ("breaking", "risky", "safe"):
            matching = [change for change in report.changes if change.severity == severity]
            if not matching:
                continue
            lines.append(f"{severity.upper()} CHANGES")
            for change in matching:
                lines.append(f"- {change.message}")
            lines.append("")
    lines.append(f"Status: {'blocking' if report.blocking else 'passing'}")
    return "\n".join(lines)

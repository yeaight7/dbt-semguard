from __future__ import annotations

import json
from collections import OrderedDict

from dbt_semguard.diffing import describe_path_title
from dbt_semguard.models import ChangeRecord, Report, Severity, coerce_severity, severity_rank

def build_report(
    changes: list[ChangeRecord],
    *,
    fail_on: str = "breaking",
    metadata: dict[str, object] | None = None,
) -> Report:
    summary = {"breaking": 0, "risky": 0, "safe": 0}
    for change in changes:
        summary[coerce_severity(change.severity).value] += 1

    highest = Severity.SAFE
    if changes:
        highest = max((coerce_severity(change.severity) for change in changes), key=severity_rank)

    blocking = False
    if fail_on != "none" and changes:
        blocking = severity_rank(highest) >= severity_rank(fail_on)
        
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

    for severity in Severity.ordered_desc():
        matching = [change for change in report.changes if change.severity == severity]
        if not matching:
            continue
        lines.append(f"### {severity.value.capitalize()} changes")
        lines.extend(_render_grouped_changes(matching, heading_level="####"))
        lines.append("")

    lines.append(f"Status: {'blocking' if report.blocking else 'passing'}")
    return "\n".join(lines)


def _render_text(report: Report) -> str:
    lines = ["dbt-semguard report", ""]
    if not report.changes:
        lines.append("No semantic changes detected.")
    else:
        for severity in Severity.ordered_desc():
            matching = [change for change in report.changes if change.severity == severity]
            if not matching:
                continue
            lines.append(f"{severity.value.upper()} CHANGES")
            lines.extend(_render_grouped_changes(matching, heading_level=None))
            lines.append("")
    lines.append(f"Status: {'blocking' if report.blocking else 'passing'}")
    return "\n".join(lines)


def _render_change_with_source(change: ChangeRecord) -> str:
    if change.source is None:
        return change.message
    return f"{change.message} (`{change.source.display()}`)"


def _render_grouped_changes(changes: list[ChangeRecord], *, heading_level: str | None) -> list[str]:
    grouped: OrderedDict[str, list[ChangeRecord]] = OrderedDict()
    for change in sorted(changes, key=lambda item: (item.path, item.code, item.message)):
        grouped.setdefault(change.path, []).append(change)

    lines: list[str] = []
    for path, path_changes in grouped.items():
        should_group = len(path_changes) > 1
        if should_group:
            title = describe_path_title(path)
            lines.append(f"{heading_level} {title}" if heading_level else title)
        for change in path_changes:
            lines.append(f"- {_render_change_with_source(change)}")
    return lines

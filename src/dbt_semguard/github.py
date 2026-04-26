from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, request


from dbt_semguard.models import Report

PR_COMMENT_MARKER = "<!-- dbt-semguard -->"

RequestFn = Callable[[str, str, str, dict[str, Any] | None], Any]


class GitHubRequestError(ValueError):
    def __init__(self, status_code: int, details: str):
        self.status_code = status_code
        self.details = details
        super().__init__(f"GitHub API request failed ({status_code}): {details}")


class GitHubPermissionError(GitHubRequestError):
    pass


def create_check_run_annotations(
    *,
    repo: str,
    head_sha: str,
    token: str,
    report: Report,
    request: RequestFn | None = None,
) -> None:
    request_fn = request or _request_json

    annotations = []
    for change in report.changes:
        if not change.source or not change.source.file:
            continue

        annotation_level = "failure" if change.severity == "breaking" else "warning"

        annotation = {
            "path": change.source.file,
            "start_line": change.source.line,
            "end_line": change.source.end_line or change.source.line,
            "annotation_level": annotation_level,
            "message": change.message,
            "title": f"dbt-semguard: {change.severity} change",
        }
        annotations.append(annotation)

    if not annotations:
        return

    for i in range(0, len(annotations), 50):
        batch = annotations[i : i + 50]

        conclusion = "failure" if report.blocking else "success"

        payload = {
            "name": "dbt-semguard-annotations",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": f"dbt-semguard found {len(report.changes)} semantic changes",
                "summary": f"Highest severity: {report.highest_severity}",
                "annotations": batch,
            },
        }

        try:
            request_fn(
                "POST",
                f"https://api.github.com/repos/{repo}/check-runs",
                token,
                payload,
            )
        except GitHubPermissionError:
            pass


def upsert_pr_comment(
    *,
    repo: str,
    pull_request_number: int,
    token: str,
    body: str,
    mode: str = "sticky",
    request: RequestFn | None = None,
) -> str:
    request_fn = request or _request_json
    comment_body = f"{PR_COMMENT_MARKER}\n{body}".strip()

    if mode == "create":
        request_fn(
            "POST",
            f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments",
            token,
            {"body": comment_body},
        )
        return "created"

    comments = request_fn(
        "GET",
        f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments?per_page=100",
        token,
        None,
    )
    existing = next((comment for comment in comments if PR_COMMENT_MARKER in comment.get("body", "")), None)
    if existing:
        request_fn(
            "PATCH",
            f"https://api.github.com/repos/{repo}/issues/comments/{existing['id']}",
            token,
            {"body": comment_body},
        )
        return "updated"

    request_fn(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments",
        token,
        {"body": comment_body},
    )
    return "created"


def _request_json(method: str, url: str, token: str, payload: dict[str, Any] | None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    github_request = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dbt-semguard",
        },
    )
    try:
        with request.urlopen(github_request) as response:
            raw = response.read()
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise GitHubPermissionError(exc.code, details) from exc
        raise GitHubRequestError(exc.code, details) from exc

    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))

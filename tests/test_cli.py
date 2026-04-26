import json
import subprocess
import sys
from pathlib import Path

import pytest

from dbt_semguard import github as github_module
from dbt_semguard import cli as cli_module
from dbt_semguard.github import GitHubPermissionError, GitHubRequestError


FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "dbt_semguard.cli", *args]
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def write_report_json(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "summary": {"breaking": 1, "risky": 0, "safe": 0},
                "highest_severity": "breaking",
                "blocking": True,
                "changes": [
                    {
                        "code": "metric_removed",
                        "severity": "breaking",
                        "message": "Metric `gross_revenue` was removed.",
                        "path": "metrics.gross_revenue",
                        "source": {"file": "models/orders.yml", "line": 21},
                    }
                ],
                "metadata": {"source_mode": "git"},
            }
        ),
        encoding="utf-8",
    )


def test_extract_command_writes_contract_json(tmp_path: Path):
    output_path = tmp_path / "contract.json"

    result = run_cli(
        "extract",
        "--source",
        "yaml",
        "--project-dir",
        str(FIXTURES / "projects" / "base"),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text())
    assert payload["semantic_models"]["orders"]["model_name"] == "fct_orders"


def test_diff_command_renders_markdown():
    result = run_cli(
        "diff",
        "--base-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--head-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--format",
        "markdown",
    )

    assert result.returncode == 0, result.stderr
    assert "## dbt-semguard report" in result.stdout
    assert "No semantic changes detected." in result.stdout


def test_check_command_exits_nonzero_for_breaking_changes():
    result = run_cli(
        "check",
        "--base-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--head-contract",
        str(FIXTURES / "contracts" / "breaking_contract.json"),
    )

    assert result.returncode == 1
    assert "Status: blocking" in result.stdout


def test_diff_command_renders_markdown_with_diagnostics(tmp_path: Path):
    repo = tmp_path / "tmp_cli_git_repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    models_dir.mkdir(exist_ok=True)
    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "base" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "breaking_change" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "head"], repo)

    base_ref = run(["git", "rev-parse", "HEAD~1"], repo).stdout.strip()
    head_ref = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    result = run_cli(
        "diff",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--project-dir",
        str(repo),
        "--format",
        "markdown",
    )

    assert result.returncode == 0, result.stderr
    assert "Simple metric `gross_revenue` changed aggregation from `sum` to `avg`." in result.stdout
    assert "models/orders.yml:21" in result.stdout


def test_comment_pr_prefers_explicit_token_over_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
            "--github-token",
            "flag-token",
        ]
    )

    assert result == 0
    assert captured["token"] == "flag-token"


def test_comment_pr_prefers_semguard_token_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    assert result == 0
    assert captured["token"] == "semguard-env-token"


def test_comment_pr_falls_back_to_github_token_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.delenv("SEMGUARD_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    assert result == 0
    assert captured["token"] == "github-env-token"


def test_comment_pr_accepts_action_annotation_arguments_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    report_json = tmp_path / "report.json"
    write_report_json(report_json)
    captured: dict[str, object] = {}

    def fake_create_check_run_annotations(**kwargs):
        captured.update(kwargs)

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setattr(github_module, "create_check_run_annotations", fake_create_check_run_annotations)

    result = cli_module.main(
        [
            "comment-pr",
            "--repo",
            "OWNER/REPO",
            "--head-sha",
            "SHA",
            "--report-json",
            str(report_json),
            "--mode",
            "sticky",
        ]
    )

    assert result == 0
    assert captured["repo"] == "OWNER/REPO"
    assert captured["head_sha"] == "SHA"
    assert captured["token"] == "semguard-env-token"
    assert captured["report"].changes[0].source.file == "models/orders.yml"


def test_comment_pr_accepts_action_comment_and_annotation_arguments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    report_json = tmp_path / "report.json"
    write_report_json(report_json)
    comment_call: dict[str, object] = {}
    annotation_call: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        comment_call.update(kwargs)
        return "created"

    def fake_create_check_run_annotations(**kwargs):
        annotation_call.update(kwargs)

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)
    monkeypatch.setattr(github_module, "create_check_run_annotations", fake_create_check_run_annotations)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "OWNER/REPO",
            "--pr-number",
            "12",
            "--head-sha",
            "SHA",
            "--report-json",
            str(report_json),
            "--mode",
            "sticky",
        ]
    )

    assert result == 0
    assert comment_call["pull_request_number"] == 12
    assert comment_call["body"] == "hello"
    assert annotation_call["head_sha"] == "SHA"


@pytest.mark.parametrize(
    ("extra_args", "message"),
    [
        ([], "Provide PR comment inputs, annotation inputs, or both."),
        (["--pr-number", "12"], "--pr-number requires --body-file."),
        (["--body-file", "body.md"], "--body-file requires --pr-number."),
        (["--head-sha", "SHA"], "--head-sha requires --report-json."),
        (["--report-json", "report.json"], "--report-json requires --head-sha."),
    ],
)
def test_comment_pr_rejects_invalid_partial_argument_combinations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra_args: list[str],
    message: str,
):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    report_json = tmp_path / "report.json"
    write_report_json(report_json)

    resolved_args = [
        str(body_file) if arg == "body.md" else str(report_json) if arg == "report.json" else arg for arg in extra_args
    ]

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")

    result = cli_module.main(["comment-pr", "--repo", "OWNER/REPO", *resolved_args])

    captured = capsys.readouterr()

    assert result == 2
    assert message in captured.err


def test_comment_pr_errors_when_no_token_is_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.delenv("SEMGUARD_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "GitHub token" in captured.err


def test_comment_pr_skips_permission_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")

    def fake_upsert_pr_comment(**kwargs):
        raise GitHubPermissionError(403, "forbidden")

    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "skipping PR comment" in captured.err


def test_comment_pr_returns_error_for_non_permission_github_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")

    def fake_upsert_pr_comment(**kwargs):
        raise GitHubRequestError(500, "server error")

    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "server error" in captured.err

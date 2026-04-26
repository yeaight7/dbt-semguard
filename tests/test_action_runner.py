import json
import subprocess
from pathlib import Path

import pytest

from dbt_semguard.action_runner import execute_action


FIXTURES = Path(__file__).parent / "fixtures"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def parse_github_output(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def init_repo_with_fixture(tmp_path: Path, fixture_name: str) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    models_dir = repo / "models"
    models_dir.mkdir(exist_ok=True)
    (models_dir / "orders.yml").write_text(
        (FIXTURES / "projects" / fixture_name / "models" / "orders.yml").read_text(encoding="utf-8")
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", fixture_name], repo)
    return repo, run(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def test_execute_action_writes_git_mode_report_summary_and_outputs(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    models_dir.mkdir(exist_ok=True)
    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "base" / "models" / "orders.yml").read_text(encoding="utf-8"))
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (models_dir / "orders.yml").write_text(
        (FIXTURES / "projects" / "breaking_change" / "models" / "orders.yml").read_text(encoding="utf-8")
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "head"], repo)

    base_ref = run(["git", "rev-parse", "HEAD~1"], repo).stdout.strip()
    head_ref = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    summary_path = tmp_path / "summary.md"
    github_output_path = tmp_path / "github-output.txt"
    report = execute_action(
        base_ref=base_ref,
        head_ref=head_ref,
        project_dir=repo,
        fail_on="breaking",
        summary_path=summary_path,
        github_output_path=github_output_path,
        output_dir=tmp_path,
    )

    json_payload = json.loads((tmp_path / "semguard-report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "semguard-report.md").read_text(encoding="utf-8")
    summary = summary_path.read_text(encoding="utf-8")
    outputs = parse_github_output(github_output_path)

    assert report.blocking is True
    assert json_payload["highest_severity"] == "breaking"
    assert "## dbt-semguard report" in markdown
    assert "## dbt-semguard report" in summary
    assert outputs == {
        "highest-severity": "breaking",
        "blocking": "true",
        "breaking-count": "3",
        "risky-count": "1",
        "safe-count": "0",
    }


def test_execute_action_writes_manifest_mode_artifacts_even_when_blocking(tmp_path: Path):
    base_manifest = tmp_path / "base-semantic-manifest.json"
    head_manifest = tmp_path / "head-semantic-manifest.json"
    base_payload = json.loads((FIXTURES / "manifest" / "base_semantic_manifest.json").read_text(encoding="utf-8"))
    head_payload = json.loads((FIXTURES / "manifest" / "base_semantic_manifest.json").read_text(encoding="utf-8"))
    head_payload["metrics"][0]["type_params"]["metric_aggregation_params"]["agg"] = "avg"
    base_manifest.write_text(json.dumps(base_payload), encoding="utf-8")
    head_manifest.write_text(json.dumps(head_payload), encoding="utf-8")

    summary_path = tmp_path / "summary.md"
    github_output_path = tmp_path / "github-output.txt"
    report = execute_action(
        base_manifest=base_manifest,
        head_manifest=head_manifest,
        fail_on="breaking",
        summary_path=summary_path,
        github_output_path=github_output_path,
        output_dir=tmp_path,
    )

    outputs = parse_github_output(github_output_path)

    assert report.blocking is True
    assert (tmp_path / "semguard-report.json").exists()
    assert (tmp_path / "semguard-report.md").exists()
    assert summary_path.exists()
    assert outputs["blocking"] == "true"
    assert outputs["highest-severity"] == "breaking"


def test_execute_action_writes_zero_change_summary_and_zero_counts(tmp_path: Path):
    repo, ref = init_repo_with_fixture(tmp_path, "base")
    summary_path = tmp_path / "summary.md"
    github_output_path = tmp_path / "github-output.txt"

    report = execute_action(
        base_ref=ref,
        head_ref=ref,
        project_dir=repo,
        fail_on="breaking",
        summary_path=summary_path,
        github_output_path=github_output_path,
        output_dir=tmp_path,
    )

    markdown = (tmp_path / "semguard-report.md").read_text(encoding="utf-8")
    json_payload = json.loads((tmp_path / "semguard-report.json").read_text(encoding="utf-8"))
    outputs = parse_github_output(github_output_path)

    assert report.blocking is False
    assert report.summary == {"breaking": 0, "risky": 0, "safe": 0}
    assert "No semantic changes detected." in markdown
    assert "Status: passing" in markdown
    assert json_payload["blocking"] is False
    assert outputs == {
        "highest-severity": "safe",
        "blocking": "false",
        "breaking-count": "0",
        "risky-count": "0",
        "safe-count": "0",
    }


def test_execute_action_rejects_invalid_fail_on_before_report_build(tmp_path: Path):
    repo, ref = init_repo_with_fixture(tmp_path, "base")

    with pytest.raises(ValueError, match="Invalid fail_on 'potato'. Expected one of: breaking, risky, safe."):
        execute_action(
            base_ref=ref,
            head_ref=ref,
            project_dir=repo,
            fail_on="potato",
            output_dir=tmp_path,
        )


def test_execute_action_supports_custom_report_basename_and_directory(tmp_path: Path):
    repo, ref = init_repo_with_fixture(tmp_path, "base")
    output_dir = tmp_path / "reports"

    execute_action(
        base_ref=ref,
        head_ref=ref,
        project_dir=repo,
        fail_on="breaking",
        output_dir=output_dir,
        output_basename="matrix-job-report",
    )

    assert (output_dir / "matrix-job-report.json").exists()
    assert (output_dir / "matrix-job-report.md").exists()
    assert not (output_dir / "semguard-report.json").exists()
    assert not (output_dir / "semguard-report.md").exists()

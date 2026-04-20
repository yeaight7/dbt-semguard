import json
import subprocess
import sys
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "dbt_semguard.cli", *args]
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


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

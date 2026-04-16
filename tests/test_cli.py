import json
import subprocess
import sys
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "dbt_semguard.cli", *args]
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


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

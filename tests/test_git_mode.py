import subprocess
import sys
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def test_git_ref_mode_reads_yaml_without_checkout(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    models_dir.mkdir()
    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "base" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "breaking_change" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "head"], repo)

    base_ref = run(["git", "rev-parse", "HEAD~1"], repo).stdout.strip()
    head_ref = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dbt_semguard.cli",
            "diff",
            "--base-ref",
            base_ref,
            "--head-ref",
            head_ref,
            "--project-dir",
            str(repo),
            "--format",
            "json",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"highest_severity": "breaking"' in result.stdout

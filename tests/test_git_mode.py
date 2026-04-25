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


def test_git_ref_mode_scopes_to_project_dir_in_monorepo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    project_a_models = repo / "dbt_project_a" / "models"
    project_b_models = repo / "dbt_project_b" / "models"
    project_a_models.mkdir(parents=True)
    project_b_models.mkdir(parents=True)

    base_yaml = """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
    metrics:
      - name: order_count
        type: simple
        agg: count
        expr: 1
"""
    (project_a_models / "orders.yml").write_text(base_yaml, encoding="utf-8")
    (project_b_models / "orders.yml").write_text(base_yaml, encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (project_b_models / "orders.yml").write_text(base_yaml.replace("count", "sum"), encoding="utf-8")
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
            str(repo / "dbt_project_a"),
            "--format",
            "json",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"highest_severity": "safe"' in result.stdout


def test_git_ref_mode_applies_default_include_exclude_filters(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    misc_dir = repo / "misc"
    models_dir.mkdir()
    misc_dir.mkdir()
    (models_dir / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
""",
        encoding="utf-8",
    )
    (misc_dir / "extra.yml").write_text(
        """metrics:
  - name: should_be_ignored
    type: simple
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (misc_dir / "extra.yml").write_text(
        """metrics:
  - name: should_be_ignored
    type: simple
    agg: sum
    expr: 1
""",
        encoding="utf-8",
    )
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
    assert '"highest_severity": "safe"' in result.stdout


def test_git_ref_mode_applies_semguard_include_exclude_overrides(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    (repo / ".semguard.yml").write_text(
        """include:
  - misc/**/*.yml
exclude:
  - models/**
""",
        encoding="utf-8",
    )

    models_dir = repo / "models"
    misc_dir = repo / "misc"
    models_dir.mkdir()
    misc_dir.mkdir()
    (models_dir / "orders.yml").write_text(
        """models:
  - name: fct_orders
    semantic_model:
      enabled: true
      name: orders
""",
        encoding="utf-8",
    )
    (misc_dir / "extra.yml").write_text(
        """metrics:
  - name: custom_metric
    type: simple
    agg: count
    expr: 1
""",
        encoding="utf-8",
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (misc_dir / "extra.yml").write_text(
        """metrics:
  - name: custom_metric
    type: simple
    agg: sum
    expr: 1
""",
        encoding="utf-8",
    )
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
    assert '"file": "misc/extra.yml"' in result.stdout


def test_git_ref_mode_uses_semguard_filters_from_each_ref(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    models_dir.mkdir()
    (models_dir / "orders.yml").write_text(
        (FIXTURES / "projects" / "base" / "models" / "orders.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo / ".semguard.yml").write_text(
        """include:
  - models/**/*.yml
exclude:
  - misc/**
""",
        encoding="utf-8",
    )
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (models_dir / "orders.yml").write_text(
        (FIXTURES / "projects" / "breaking_change" / "models" / "orders.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (repo / ".semguard.yml").write_text(
        """include:
  - misc/**/*.yml
exclude:
  - models/**
""",
        encoding="utf-8",
    )
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
    assert '"path": "semantic_models.orders"' in result.stdout

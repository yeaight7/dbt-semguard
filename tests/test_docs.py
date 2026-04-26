from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_mentions_license_and_coverage():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Coverage" in readme
    assert "## License" in readme
    assert "MIT License" in readme


def test_readme_explains_purpose_and_usage_flow():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## What Is This For?" in readme
    assert "## How It Works" in readme
    assert "## How To Use It" in readme
    assert "semantic PR guard" in readme
    assert "What changed in the meaning of this metric?" in readme
    assert "Run locally before opening a PR" in readme


def test_readme_covers_github_install_source_install_and_action_permissions():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Install From GitHub" in readme
    assert 'python -m pip install "git+https://github.com/yeaight7/dbt-semguard.git@v0.5.0"' in readme
    assert "Python 3.11 or newer" in readme
    assert "## Install From Source" in readme
    assert "python -m pip install ." in readme
    assert "## Use As A GitHub Action" in readme
    assert "contents: read" in readme
    assert "issues: write" in readme
    assert "pull-requests: read" in readme
    assert "forked pull requests" in readme
    assert "steps.semguard.outputs.highest-severity" in readme
    assert "steps.semguard.outputs.blocking" in readme


def test_changelog_v050_describes_action_hardening_and_outputs():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## v0.5.0" in changelog
    assert "shell injection" in changelog.lower()
    assert "action outputs" in changelog.lower()
    assert "artifact" in changelog.lower()
    assert "pyproject.toml" in changelog


def test_license_file_exists_and_is_mit():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Permission is hereby granted, free of charge" in license_text


def test_severity_rules_defaults_do_not_claim_v03_limitations():
    severity_rules = (ROOT / "docs" / "severity-rules.md").read_text(encoding="utf-8")

    assert "No repo-level config file in `v0.3`" not in severity_rules
    assert "No rename inference in `v0.3`" not in severity_rules
    assert "Default threshold: `--fail-on breaking`" in severity_rules
    assert ".semguard.yml" in severity_rules

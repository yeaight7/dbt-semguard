from pathlib import Path
from dbt_semguard import __version__


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

    assert "## Install From PyPI" in readme
    assert "python -m pip install dbt-semguard" in readme
    assert "## Install From GitHub" in readme
    assert readme.index("## Install From PyPI") < readme.index("## Install From GitHub")
    assert f'python -m pip install "git+https://github.com/yeaight7/dbt-semguard.git@v{__version__}"' in readme
    assert "Python 3.11 or newer" in readme
    assert "## Install From Source" in readme
    assert "python -m pip install ." in readme
    assert "## Use As A GitHub Action" in readme
    assert "contents: read" in readme
    assert "issues: write" in readme
    assert "pull-requests: write" in readme
    assert "checks: write" in readme
    assert "forked pull requests" in readme
    assert "Missing `checks: write`" in readme
    assert "steps.semguard.outputs.highest-severity" in readme
    assert "steps.semguard.outputs.blocking" in readme
    assert "pr-comment-mode" in readme
    assert "`sticky`" in readme
    assert "`create`" in readme
    assert "No semantic changes detected." in readme
    assert "docs/troubleshooting.md" in readme
    assert '"highest_severity": "breaking"' in readme
    assert "## dbt-semguard report" in readme


def test_changelog_v051_describes_docs_and_action_polish():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## v0.5.1" in changelog
    assert "security.md" in changelog.lower()
    assert "contributing.md" in changelog.lower()
    assert "troubleshooting" in changelog.lower()
    assert "requirements-dev.txt" in changelog
    assert "artifact" in changelog.lower()


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


def test_community_docs_exist_and_cover_expected_topics():
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    troubleshooting = (ROOT / "docs" / "troubleshooting.md").read_text(encoding="utf-8")

    assert "GitHub Security Advisories" in security
    assert "rivero4javier@outlook.es" in security
    assert "Python 3.11 or newer" in contributing
    assert "requirements-dev.txt" in contributing
    assert "python -m pytest" in contributing
    assert "fetch-depth: 0" in troubleshooting
    assert "YAML" in troubleshooting
    assert "forked pull requests" in troubleshooting
    assert "fail-on" in troubleshooting
    assert "semantic_manifest.json" in troubleshooting
    assert "No semantic changes detected." in troubleshooting


def test_docs_do_not_reference_previous_current_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    how_to_use = (ROOT / "docs" / "how-to-use.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = __version__

    assert f"v{version}" in readme
    assert f"v{version}" in how_to_use
    assert f"## v{version}" in changelog

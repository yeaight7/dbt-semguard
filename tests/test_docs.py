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


def test_license_file_exists_and_is_mit():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Permission is hereby granted, free of charge" in license_text

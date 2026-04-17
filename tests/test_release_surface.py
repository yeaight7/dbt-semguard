from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_action_installs_from_action_path_and_has_branding():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert action["branding"] == {"icon": "shield", "color": "blue"}
    install_step = next(step for step in action["runs"]["steps"] if step.get("name") == "Install dbt-semguard")
    assert '${{ github.action_path }}' in install_step["run"]
    assert "python -m pip install ." not in install_step["run"]


def test_action_invokes_semguard_without_eval_or_serialized_shell_args():
    action_text = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert "eval " not in action_text
    assert "diff_args=" not in action_text
    assert "semguard diff --base-ref" in action_text
    assert "semguard diff --base-manifest" in action_text
    assert "semguard check --base-ref" in action_text
    assert "semguard check --base-manifest" in action_text


def test_ci_workflow_covers_manifest_inputs_and_published_consumer_path():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    assert "action-smoke-manifest" in jobs
    assert "published-action-smoke" in jobs

    manifest_steps = jobs["action-smoke-manifest"]["steps"]
    published_steps = jobs["published-action-smoke"]["steps"]

    assert any(step.get("uses") == "./" for step in manifest_steps)
    assert any("base-manifest" in str(step.get("with", {})) for step in manifest_steps)
    assert any("head-manifest" in str(step.get("with", {})) for step in manifest_steps)
    assert any(step.get("uses") == "yeaight7/dbt-semguard@v0.1.1" for step in published_steps)


def test_readme_uses_marketplace_action_ref_and_relative_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "- uses: yeaight7/dbt-semguard@v0.1.1" in readme
    assert "uses: ./" not in readme
    assert "C:/Users/Rivero/" not in readme
    assert "(docs/contract-spec.md)" in readme
    assert "(examples/ecommerce_dbt_project)" in readme

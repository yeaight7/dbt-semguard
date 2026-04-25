from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


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
    assert "semguard comment-pr" in action_text


def test_ci_workflow_uses_only_local_action_smoke_jobs():
    workflow = load_workflow("ci.yml")
    jobs = workflow["jobs"]

    assert "published-action-smoke" not in jobs
    assert "published-action-smoke-manifest" not in jobs
    assert "action-smoke-git" in jobs
    assert "action-smoke-manifest" in jobs

    workflow_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "yeaight7/dbt-semguard@v0.4.0" not in workflow_text

    git_steps = jobs["action-smoke-git"]["steps"]
    manifest_steps = jobs["action-smoke-manifest"]["steps"]

    assert any(step.get("uses") == "./" for step in git_steps)
    assert any(step.get("uses") == "./" for step in manifest_steps)
    assert any("base-ref" in str(step.get("with", {})) for step in git_steps)
    assert any("head-ref" in str(step.get("with", {})) for step in git_steps)
    assert any("base-manifest" in str(step.get("with", {})) for step in manifest_steps)
    assert any("head-manifest" in str(step.get("with", {})) for step in manifest_steps)


def test_ci_workflow_seeds_real_git_refs_from_breaking_change_fixtures():
    workflow = load_workflow("ci.yml")
    seed_step = next(step for step in workflow["jobs"]["action-smoke-git"]["steps"] if step.get("name") == "Seed comparison refs")
    run = seed_step["run"]

    assert "tests/fixtures/projects/base" in run
    assert "tests/fixtures/projects/breaking_change" in run
    assert 'echo "BASE_SHA=$(git rev-parse HEAD)"' in run
    assert 'echo "HEAD_SHA=$(git rev-parse HEAD)"' in run
    assert "base semantic model fixture" in run
    assert "breaking semantic model fixture" in run


def test_ci_workflow_asserts_breaking_change_failure_not_just_any_failure():
    workflow = load_workflow("ci.yml")
    steps = workflow["jobs"]["action-smoke-git"]["steps"]

    semguard_step = next(step for step in steps if step.get("id") == "semguard")
    assert semguard_step["uses"] == "./"
    assert semguard_step["continue-on-error"] is True

    assertion_step = next(step for step in steps if step.get("name") == "Assert breaking-change smoke failure")
    run = assertion_step["run"]

    assert '[[ -n "$BASE_SHA" ]]' in run
    assert '[[ -n "$HEAD_SHA" ]]' in run
    assert 'git cat-file -e "${BASE_SHA}^{commit}"' in run
    assert 'git cat-file -e "${HEAD_SHA}^{commit}"' in run
    assert 'steps.semguard.outcome' in (str(assertion_step.get("if", "")) + run)
    assert "semguard-report.json" in run
    assert '"highest_severity"' in run
    assert '"blocking"' in run


def test_ci_workflow_manifest_smoke_uses_breaking_manifest_change():
    workflow = load_workflow("ci.yml")
    steps = workflow["jobs"]["action-smoke-manifest"]["steps"]

    fixture_step = next(step for step in steps if step.get("name") == "Create semantic manifest fixtures with hostile paths")
    fixture_run = fixture_step["run"]
    assert 'metric_aggregation_params' in fixture_run
    assert '"agg"' in fixture_run
    assert '"avg"' in fixture_run

    assertion_step = next(step for step in steps if step.get("name") == "Assert manifest smoke failure")
    assert "gross_revenue" in assertion_step["run"]


def test_published_action_smoke_workflow_runs_only_after_release_or_manual_dispatch():
    workflow = load_workflow("published-action-smoke.yml")
    workflow_text = (ROOT / ".github" / "workflows" / "published-action-smoke.yml").read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    triggers = workflow.get("on", workflow.get(True))

    assert "push" not in workflow
    assert "pull_request" not in workflow
    assert triggers["release"]["types"] == ["published"]
    assert "workflow_dispatch" in triggers
    assert "published-action-smoke" in jobs
    assert "published-action-smoke-manifest" in jobs
    assert "yeaight7/dbt-semguard@" in workflow_text
    assert "uses: ./" not in workflow_text

    manifest_steps = jobs["published-action-smoke-manifest"]["steps"]
    fixture_step = next(step for step in manifest_steps if step.get("name") == "Create published-consumer manifest fixtures with hostile paths")
    fixture_run = fixture_step["run"]
    assert 'metric_aggregation_params' in fixture_run
    assert '"agg"' in fixture_run
    assert '"avg"' in fixture_run


def test_action_exposes_pr_comment_input():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert "pr-comment" in action["inputs"]
    assert "github-token" in action["inputs"]


def test_readme_uses_marketplace_action_ref_and_relative_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "- uses: yeaight7/dbt-semguard@v0.4.0" in readme
    assert "uses: ./" not in readme
    assert "C:/Users/Rivero/" not in readme
    assert "(docs/contract-spec.md)" in readme
    assert "(examples/ecommerce_dbt_project)" in readme

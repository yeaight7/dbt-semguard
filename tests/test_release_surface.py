from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def load_action() -> dict:
    return yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))


def action_steps() -> list[dict]:
    return load_action()["runs"]["steps"]


def test_action_installs_from_action_path_and_has_branding():
    action = load_action()

    assert action["branding"] == {"icon": "shield", "color": "blue"}
    install_step = next(step for step in action["runs"]["steps"] if step.get("name") == "Install dbt-semguard")
    assert "python -m venv" in install_step["run"]
    assert "GITHUB_PATH" in install_step["run"]
    assert install_step["env"]["ACTION_PATH"] == "${{ github.action_path }}"
    assert '"$ACTION_PATH"' in install_step["run"]


def test_action_invokes_semguard_without_eval_or_serialized_shell_args():
    action_text = (ROOT / "action.yml").read_text(encoding="utf-8")

    assert "eval " not in action_text
    assert "diff_args=" not in action_text
    assert "python -m dbt_semguard.action_runner" in action_text
    assert "semguard comment-pr" in action_text
    assert "--github-token" not in action_text


def test_action_defines_structured_outputs_for_ci_consumers():
    action = load_action()

    assert action["outputs"]["highest-severity"]["description"]
    assert action["outputs"]["highest-severity"]["value"] == "${{ steps.generate.outputs.highest-severity }}"
    assert action["outputs"]["blocking"]["value"] == "${{ steps.generate.outputs.blocking }}"
    assert action["outputs"]["breaking-count"]["value"] == "${{ steps.generate.outputs.breaking-count }}"
    assert action["outputs"]["risky-count"]["value"] == "${{ steps.generate.outputs.risky-count }}"
    assert action["outputs"]["safe-count"]["value"] == "${{ steps.generate.outputs.safe-count }}"


def test_action_input_descriptions_document_modes_thresholds_and_artifacts():
    action = load_action()

    assert "breaking" in action["inputs"]["fail-on"]["description"]
    assert "risky" in action["inputs"]["fail-on"]["description"]
    assert "safe" in action["inputs"]["fail-on"]["description"]
    assert "sticky" in action["inputs"]["pr-comment-mode"]["description"]
    assert "create" in action["inputs"]["pr-comment-mode"]["description"]
    assert "JSON artifact" in action["inputs"]["artifact-name"]["description"]


def test_action_run_scripts_do_not_embed_github_expressions():
    for step in action_steps():
        run = step.get("run")
        if not isinstance(run, str):
            continue
        assert "${{ inputs." not in run, step.get("name")
        assert "${{ github." not in run, step.get("name")


def test_action_report_paths_are_env_driven_not_hardcoded():
    generate_step = next(step for step in action_steps() if step.get("id") == "generate")
    publish_step = next(step for step in action_steps() if step.get("name") == "Publish PR comment")
    upload_step = next(step for step in action_steps() if step.get("uses") == "actions/upload-artifact@v4")

    assert "semguard-report.json" not in generate_step["run"]
    assert "semguard-report.md" not in generate_step["run"]
    assert 'REPORT_DIR' in generate_step["env"]
    assert 'REPORT_BASENAME' in generate_step["env"]
    assert '"$REPORT_MD_PATH"' in publish_step["run"] or "body-file $REPORT_MD_PATH" in publish_step["run"]
    assert upload_step["with"]["path"] == "${{ env.REPORT_JSON_PATH }}"

def test_action_upload_artifact_always_runs():
    upload_step = next(step for step in action_steps() if step.get("uses") == "actions/upload-artifact@v4")

    assert upload_step["if"] == "always()"


def test_action_generate_step_is_single_pass_and_sets_outputs():
    generate_step = next(step for step in action_steps() if step.get("id") == "generate")
    run = generate_step["run"]

    assert "semguard diff" not in run
    assert "semguard check" not in run
    assert "python -m dbt_semguard.action_runner" in run


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


def test_ci_workflow_installs_pinned_dev_requirements():
    workflow = load_workflow("ci.yml")
    install_step = next(step for step in workflow["jobs"]["test"]["steps"] if step.get("name") == "Install package")
    run = install_step["run"]

    assert "requirements-dev.txt" in run
    assert "python -m pip install -e . --no-deps" in run


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
    assert 'steps.semguard.outputs.highest-severity' in run
    assert 'steps.semguard.outputs.blocking' in run
    assert 'steps.semguard.outputs.breaking-count' in run


def test_ci_workflow_manifest_smoke_uses_breaking_manifest_change():
    workflow = load_workflow("ci.yml")
    steps = workflow["jobs"]["action-smoke-manifest"]["steps"]

    fixture_step = next(step for step in steps if step.get("name") == "Create semantic manifest fixtures with hostile paths")
    fixture_run = fixture_step["run"]
    assert 'metric_aggregation_params' in fixture_run
    assert '"agg"' in fixture_run
    assert '"avg"' in fixture_run

    assertion_step = next(step for step in steps if step.get("name") == "Assert manifest smoke failure")
    assert 'steps.semguard.outputs.highest-severity' in assertion_step["run"]
    assert 'steps.semguard.outputs.blocking' in assertion_step["run"]


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
    assert "yeaight7/dbt-semguard@" not in workflow_text
    assert "uses: ./" in workflow_text

    manifest_steps = jobs["published-action-smoke-manifest"]["steps"]
    fixture_step = next(step for step in manifest_steps if step.get("name") == "Create published-consumer manifest fixtures with hostile paths")
    fixture_run = fixture_step["run"]
    assert 'metric_aggregation_params' in fixture_run
    assert '"agg"' in fixture_run
    assert '"avg"' in fixture_run


def test_published_action_smoke_workflow_asserts_outputs_not_workspace_report_files():
    workflow = load_workflow("published-action-smoke.yml")

    git_assertion = next(
        step for step in workflow["jobs"]["published-action-smoke"]["steps"] if step.get("name") == "Assert published git smoke failure"
    )
    manifest_assertion = next(
        step
        for step in workflow["jobs"]["published-action-smoke-manifest"]["steps"]
        if step.get("name") == "Assert published manifest smoke failure"
    )

    assert "semguard-report.json" not in git_assertion["run"]
    assert "steps.semguard.outputs.highest-severity" in git_assertion["run"]
    assert "steps.semguard.outputs.blocking" in git_assertion["run"]
    assert "semguard-report.json" not in manifest_assertion["run"]
    assert "steps.semguard.outputs.highest-severity" in manifest_assertion["run"]
    assert "steps.semguard.outputs.blocking" in manifest_assertion["run"]


def test_action_exposes_pr_comment_input():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert "pr-comment" in action["inputs"]
    assert "github-token" in action["inputs"]
    publish_step = next(step for step in action["runs"]["steps"] if step.get("name") == "Publish PR comment")
    assert publish_step["env"]["SEMGUARD_GITHUB_TOKEN"] == "${{ inputs.github-token }}"


def test_readme_uses_marketplace_action_ref_and_relative_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "- uses: yeaight7/dbt-semguard@v0.5.2" in readme
    assert "uses: ./" not in readme
    assert "C:/Users/Rivero/" not in readme
    assert "(docs/contract-spec.md)" in readme
    assert "(examples/ecommerce_dbt_project)" in readme


def test_pyproject_includes_v051_packaging_metadata():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["version"] == "0.5.2"
    assert project["authors"] == [{"name": "yeaight7", "email": "rivero4javier@outlook.es"}]
    assert "keywords" in project
    assert {"dbt", "semantic-layer", "metrics", "github-actions"}.issubset(set(project["keywords"]))
    assert "classifiers" in project
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert "Programming Language :: Python :: 3" in project["classifiers"]
    assert "Topic :: Software Development :: Quality Assurance" in project["classifiers"]
    assert project["urls"]["Repository"] == "https://github.com/yeaight7/dbt-semguard"
    assert project["urls"]["Issues"] == "https://github.com/yeaight7/dbt-semguard/issues"
    assert project["urls"]["Changelog"] == "https://github.com/yeaight7/dbt-semguard/blob/main/CHANGELOG.md"
    assert project["urls"]["Documentation"] == "https://github.com/yeaight7/dbt-semguard#readme"
    requirements_dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "PyYAML==" in requirements_dev
    assert "pytest==" in requirements_dev

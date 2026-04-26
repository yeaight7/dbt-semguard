from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath
from typing import Callable


def load_yaml_documents_from_git_ref(
    project_dir: str | Path,
    git_ref: str,
    file_filter: Callable[[str], bool] | None = None,
) -> list[tuple[str, str]]:
    root = Path(project_dir).resolve()
    repo_root = _resolve_repo_root(root)
    project_prefix = _project_prefix(repo_root, root)
    tree_ref = _resolve_tree_ref(repo_root, git_ref)

    try:
        command = ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", tree_ref]
        if project_prefix:
            command.extend(["--", project_prefix])
        listing = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or f"Failed to read git ref '{git_ref}'."
        raise ValueError(stderr) from exc

    yaml_paths = [line.strip() for line in listing.stdout.splitlines() if line.strip().endswith((".yml", ".yaml"))]

    documents: list[tuple[str, str]] = []
    for repo_relative_path in yaml_paths:
        project_relative_path = _to_project_relative_path(repo_relative_path, project_prefix)
        if project_relative_path is None:
            continue
        if file_filter is not None and not file_filter(project_relative_path):
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), "show", f"{tree_ref}:{repo_relative_path}"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (
                exc.stderr.strip()
                or exc.stdout.strip()
                or f"Failed to read '{project_relative_path or repo_relative_path}' at '{git_ref}'."
            )
            raise ValueError(stderr) from exc
        documents.append((project_relative_path, result.stdout))

    return documents


def _resolve_repo_root(project_dir: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or f"Failed to locate git repository from '{project_dir}'."
        raise ValueError(stderr) from exc
    return Path(result.stdout.strip()).resolve()


def _resolve_tree_ref(repo_root: Path, git_ref: str) -> str:
    raw_ref = str(git_ref).strip()
    if not raw_ref or raw_ref.startswith("-"):
        raise ValueError(f"Invalid git ref '{git_ref}'.")

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{raw_ref}^{{tree}}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or f"Invalid git ref '{git_ref}'."
        raise ValueError(stderr) from exc

    tree_ref = result.stdout.strip()
    if not tree_ref:
        raise ValueError(f"Invalid git ref '{git_ref}'.")
    return tree_ref


def _project_prefix(repo_root: Path, project_dir: Path) -> str:
    try:
        relative = project_dir.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Project directory '{project_dir}' is not inside git repository '{repo_root}'.") from exc
    return "" if relative == Path(".") else relative.as_posix()


def _to_project_relative_path(repo_relative_path: str, project_prefix: str) -> str | None:
    normalized = PurePosixPath(repo_relative_path).as_posix()
    if not project_prefix:
        return normalized

    prefix = project_prefix.rstrip("/")
    if normalized == prefix:
        return None
    if not normalized.startswith(f"{prefix}/"):
        return None
    return normalized[len(prefix) + 1 :]

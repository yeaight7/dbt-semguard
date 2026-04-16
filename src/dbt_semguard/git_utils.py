from __future__ import annotations

import subprocess
from pathlib import Path


def load_yaml_documents_from_git_ref(project_dir: str | Path, git_ref: str) -> list[tuple[str, str]]:
    root = Path(project_dir).resolve()
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", git_ref],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or f"Failed to read git ref '{git_ref}'."
        raise ValueError(stderr) from exc

    yaml_paths = [
        line.strip()
        for line in listing.stdout.splitlines()
        if line.strip().endswith((".yml", ".yaml"))
    ]

    documents: list[tuple[str, str]] = []
    for relative_path in yaml_paths:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "show", f"{git_ref}:{relative_path}"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip() or f"Failed to read '{relative_path}' at '{git_ref}'."
            raise ValueError(stderr) from exc
        documents.append((relative_path, result.stdout))

    return documents

"""Explicit file persistence boundary (Stage 16B)."""

from __future__ import annotations

from pathlib import Path

from .exceptions import InvalidProjectError
from .models import OriglyphProject
from .serialization import project_from_json, project_to_canonical_json

__all__ = ["save_project", "load_project"]


def save_project(project: OriglyphProject,
                 path: str | Path) -> Path:
    """Write one deterministic JSON project file (UTF-8, LF newline)."""
    if not isinstance(project, OriglyphProject):
        raise InvalidProjectError("project must be an OriglyphProject")
    target = Path(path)
    text = project_to_canonical_json(project) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def load_project(path: str | Path) -> OriglyphProject:
    """Load and verify one deterministic JSON project file."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidProjectError(
            f"project file cannot be read: {exc}") from exc
    return project_from_json(text)

"""Project-model exceptions (Stage 16B).

Fail-closed error contracts for the persisted project model. All errors
derive from :class:`OriglyphProjectError` so callers can catch the whole
project boundary with one type.
"""

from __future__ import annotations

__all__ = [
    "OriglyphProjectError",
    "InvalidProjectError",
    "UnsupportedProjectSchemaError",
    "ProjectIntegrityError",
]


class OriglyphProjectError(ValueError):
    """Base error for the persisted project model boundary."""


class InvalidProjectError(OriglyphProjectError):
    """Raised when project construction or payload content is malformed."""


class UnsupportedProjectSchemaError(OriglyphProjectError):
    """Raised when a project schema identifier is unknown or unsupported."""


class ProjectIntegrityError(OriglyphProjectError):
    """Raised when stored identity does not match content (tamper/stale)."""

"""Origlyph tolerance analysis package (Stage 15C-R).

Deterministic 1D worst-case tolerance stack analysis. This package provides
the typed domain model (:mod:`origlyph.tolerance.models`) and the
deterministic worst-case engine (:mod:`origlyph.tolerance.worst_case`).

AI does not override deterministic tolerance calculations.
"""

from .exceptions import (
    InvalidStackError,
    InvalidToleranceError,
    OriglyphToleranceError,
)
from .models import (
    StackDirection,
    ToleranceContribution,
    ToleranceStack,
    WorstCaseResult,
)
from .worst_case import worst_case

__all__ = [
    "InvalidStackError",
    "InvalidToleranceError",
    "OriglyphToleranceError",
    "StackDirection",
    "ToleranceContribution",
    "ToleranceStack",
    "WorstCaseResult",
    "worst_case",
]
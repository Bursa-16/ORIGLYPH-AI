"""Advisory recommendation and evidence types for datum/reference selection.

Deterministic selection rules and engineering judgment live here; AI
recommendation is a future provider that returns a :class:`DatumRecommendation`.
These types are **advisory only** and must never override the deterministic
calculations in :mod:`origlyph.datum.dof` or
:mod:`origlyph.datum.datum_reference_frame`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence, runtime_checkable

from .datum_reference_frame import ConstrainedResult, DatumConstraint


class ValidationState(str, Enum):
    """Advisory validation state for descriptor/recommendation records.

    Used by :class:`DatumRecommendation.validation` and
    :class:`~origlyph.cad.evaluation.CandidateEvaluation.validation`.

    Meanings (locked by the Stage 4F contract)::

        UNVALIDATED
            No advisory validation step has yet been applied.
        PASS
            The applicable deterministic validation/evaluation step
            completed successfully. It is **not** recommendation
            acceptance; engineer acceptance remains a later action.
        FAIL
            Represents a failed advisory validation result when such a path
            exists. Candidate evaluation does not currently emit FAIL.

    IMPORTANT — ``PASS`` does **not** mean any of:

    * engineer approval;
    * datum assignment;
    * recommendation acceptance;
    * structural validity of a ``BoundReference`` (owned by Stage 1/2
      binding and coherence validation);
    * DRF acceptance.

    ``PASS`` only reports completion of the applicable deterministic step.
    Engineer acceptance remains a separate, explicit, later action.
    """

    UNVALIDATED = "unvalidated"
    PASS = "pass"
    FAIL = "fail"


class RecommendationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EngineeringRationale(str, Enum):
    FLAT_SURFACE = "flat_surface"
    CYLINDRICAL_AXIS = "cylindrical_axis"
    PLANAR_EDGE = "planar_edge"
    LARGEST_FACE = "largest_face"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ManualOverride:
    applied: bool = False
    justification: str | None = None


@dataclass(frozen=True)
class DatumRecommendation:
    """An advisory recommendation; never authoritative over deterministic results."""

    constraint: DatumConstraint
    confidence: RecommendationConfidence
    rationale: EngineeringRationale | str
    validation: ValidationState = ValidationState.UNVALIDATED
    override: ManualOverride = field(default_factory=ManualOverride)

    @property
    def is_advisory(self) -> bool:
        return True


@runtime_checkable
class Recommender(Protocol):
    """Contract for future deterministic/AI recommenders.

    Returns zero or more recommendations. An empty result is a fail-closed
    signal (no recommendation -> human review required).
    """

    def recommend(
        self,
        available: Sequence[DatumConstraint],
        result: ConstrainedResult,
    ) -> Sequence[DatumRecommendation]:
        """Return candidate datum constraints, ordered best-first."""
        ...

"""Deterministic neutral-CAD to datum/reference bridge (Stage 1D).

This module is the connective tissue between the Stage 1C neutral imported
model and the Stage 1B datum/reference primitives. It is **filter-only and
non-inferring**:

* it lifts eligible POINT / PLANE / AXIS / LINE entities into the reference /
  datum-feature candidate universe (via :class:`BridgedCandidate`); a PLANE
  entity may carry a finite ``BoundedPlanarFace`` whose deterministic frame is
  derived from the face's centroid and plane normal;
* it records deterministic, technical skip reasons for ineligible entities
  (:class:`SkippedCandidate` / :class:`CandidateResult`);
* it exposes the provenance-ready identity chain
  ``SourceEntityIdentity -> NeutralEntityIdentity -> DomainIdentity``;
* it provides a single manual-selection wrapper
  (:func:`select_reference`) that records an explicit human role assignment.

It deliberately never: ranks candidates, assigns 3-2-1 roles automatically,
constructs a :class:`~origlyph.datum.Datum` or
:class:`~origlyph.datum.LocatingFeature` on its own, performs any B-Rep /
topology / kernel work, or applies any standards-specific datum-selection
rule. Coordinate frames are used verbatim or derived deterministically from
an existing ``origlyph.geometry`` value object only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from origlyph.datum import (
    ConstraintType,
    FeatureKind,
    LocatingFeature,
    PhysicalFeature,
    Reference,
    ReferencePoint,
    ReferenceSurface,
)
from origlyph.geometry import (
    BoundedPlanarFace,
    Frame,
    Line3D,
    Plane3D,
    Point3D,
    Vector3D,
)

from .identity import (
    DomainIdentity,
    NeutralEntityIdentity,
    NeutralEntityKind,
    SourceEntityIdentity,
)
from .model import NeutralEntityEntry, NeutralModel

__all__ = [
    "BridgedCandidate",
    "CandidateResult",
    "EntityEligibility",
    "SkippedCandidate",
    "domain_identity",
    "eligible_for",
    "extract_candidates",
    "identity_chain",
    "resolve_entity_frame",
    "select_reference",
]

# Neutral kinds that may be lifted as datum-feature candidates. The reference
# artifact is produced only for POINT/PLANE (ReferencePoint/ReferenceSurface).
_CANDIDATE_KINDS: frozenset[NeutralEntityKind] = frozenset(
    {
        NeutralEntityKind.POINT,
        NeutralEntityKind.LINE,
        NeutralEntityKind.AXIS,
        NeutralEntityKind.PLANE,
    }
)

# Fixed deterministic primary reference vectors used only to complete an
# orthonormal basis whose principal axis is supplied verbatim.
_REFERENCE_VECTORS: tuple[Vector3D, ...] = (
    Vector3D(0.0, 0.0, 1.0),
    Vector3D(0.0, 1.0, 0.0),
    Vector3D(1.0, 0.0, 0.0),
)
@dataclass(frozen=True)
class EntityEligibility:
    """Explicit eligibility of one neutral kind (documented classification)."""

    eligible: bool
    reference_kind: Optional[str]  # None when no reference artifact is produced
    feature_kind: Optional[str]    # None when no datum feature is produced


@dataclass(frozen=True)
class BridgedCandidate:
    """A neutral entity lifted to reference / datum-feature artifacts.

    ``reference`` is produced for POINT/PLANE only; ``datum_feature`` is
    produced for all four candidate kinds. ``entity_id`` is the domain
    identity so the CAD layer can resolve the artifact back through the chain.
    """

    domain_identity: DomainIdentity
    neutral_identity: NeutralEntityIdentity
    reference: Optional[Reference]
    datum_feature: PhysicalFeature

    @property
    def entity_id(self) -> str:
        """The domain identity value used as the artifact entity id."""
        return self.domain_identity.value


@dataclass(frozen=True)
class SkippedCandidate:
    """A neutral entity excluded from the candidate universe, with reason."""

    neutral_identity: NeutralEntityIdentity
    reason: str


@dataclass(frozen=True, init=False)
class CandidateResult:
    """Immutable deterministic result of candidate extraction."""

    candidates: tuple[BridgedCandidate, ...]
    skipped: tuple[SkippedCandidate, ...]

    def __init__(
        self,
        candidates: Optional[Sequence[BridgedCandidate]] = None,
        skipped: Optional[Sequence[SkippedCandidate]] = None,
    ) -> None:
        object.__setattr__(self, "candidates", tuple(candidates or ()))
        object.__setattr__(self, "skipped", tuple(skipped or ()))

    def references(self) -> tuple[Reference, ...]:
        """All reference artifacts lifted from candidates (POINT/PLANE)."""
        out: list[Reference] = []
        for candidate in self.candidates:
            if candidate.reference is not None:
                out.append(candidate.reference)
        return tuple(out)

    def datum_features(self) -> tuple[PhysicalFeature, ...]:
        """All datum-feature artifacts lifted from candidates."""
        return tuple(candidate.datum_feature for candidate in self.candidates)


def domain_identity(neutral: NeutralEntityIdentity) -> DomainIdentity:
    """Return the analysis/domain handle for ``neutral``.

    The domain identity is `DomainIdentity(neutral.neutral_entity_key)` —
    deterministic, opaque, and scoped to one import result (no persistence).
    """
    return DomainIdentity(neutral.neutral_entity_key)


def identity_chain(
    candidate: BridgedCandidate,
) -> tuple[
    Optional[SourceEntityIdentity],
    NeutralEntityIdentity,
    DomainIdentity,
]:
    """Return the provenance-ready identity chain for ``candidate``."""
    source = candidate.neutral_identity.source_identity
    return source, candidate.neutral_identity, candidate.domain_identity


def eligible_for(neutral_kind: NeutralEntityKind) -> EntityEligibility:
    """Return the explicit eligibility classification for ``neutral_kind``."""
    if neutral_kind is NeutralEntityKind.PLANE:
        return EntityEligibility(True, "surface", "plane")
    if neutral_kind is NeutralEntityKind.POINT:
        return EntityEligibility(True, "point", "point")
    if neutral_kind in (NeutralEntityKind.AXIS, NeutralEntityKind.LINE):
        return EntityEligibility(True, None, "axis")
    return EntityEligibility(False, None, None)
def resolve_entity_frame(entity: NeutralEntityEntry) -> Optional[Frame]:
    """Return the deterministic frame for ``entity``, or ``None`` if unset.

    Precedence (explicit, no inference):

    1. ``entity.coordinate_frame`` when present — used verbatim.
    2. Otherwise a canonical deterministic :class:`Frame` derived from an
       existing ``origlyph.geometry`` value object, if any:
       - ``Point3D`` -> world basis with origin at the point;
       - ``Plane3D`` -> z-axis == normal verbatim, x/y completed
         deterministically;
       - ``Line3D``  -> z-axis == direction verbatim, x/y completed
         deterministically;
       - ``BoundedPlanarFace`` -> z-axis == plane normal verbatim, origin ==
         face centroid, x/y completed deterministically.

    No geometry / no coordinate frame -> ``None`` (fail-closed).
    """
    coordinate_frame = entity.coordinate_frame
    if coordinate_frame is not None:
        return coordinate_frame

    geometry = entity.geometry
    if isinstance(geometry, Point3D):
        return Frame(
            origin=geometry,
            x_axis=Vector3D(1.0, 0.0, 0.0),
            y_axis=Vector3D(0.0, 1.0, 0.0),
            z_axis=Vector3D(0.0, 0.0, 1.0),
        )
    if isinstance(geometry, Plane3D):
        return _frame_with_axis(geometry.normal)
    if isinstance(geometry, Line3D):
        return _frame_with_axis(geometry.direction)
    if isinstance(geometry, BoundedPlanarFace):
        return _frame_with_axis(geometry.plane.normal, geometry.centroid)
    return None


def _frame_with_axis(axis: Vector3D, origin: Optional[Point3D] = None) -> Frame:
    """Build a deterministic right-handed frame with ``axis`` as the z-axis.

    The supplied axis is taken verbatim as the z basis. A cross product with
    the first fixed reference vector that is not parallel yields x; y is then
    ``z x x``. Pure vector math only; no hidden orientation policy. The frame
    origin defaults to the world origin unless one is supplied.
    """
    z = axis.normalize()
    if origin is None:
        origin = Point3D(0.0, 0.0, 0.0)
    for reference in _REFERENCE_VECTORS:
        if not reference.cross(z).is_zero():
            x = reference.cross(z).normalize()
            y = z.cross(x)
            return Frame(origin=origin, x_axis=x, y_axis=y, z_axis=z)
    raise ValueError("cannot complete orthonormal frame from axis")


def _reference_for(
    kind: NeutralEntityKind,
    entity_id: str,
    frame: Frame,
) -> Optional[Reference]:
    """Produce the explicit reference artifact for ``kind``, if any.

    Only PLANE -> ReferenceSurface and POINT -> ReferencePoint produce a
    reference; AXIS/LINE produce none.
    """
    if kind is NeutralEntityKind.PLANE:
        return ReferenceSurface(entity_id=entity_id, frame=frame)
    if kind is NeutralEntityKind.POINT:
        return ReferencePoint(entity_id=entity_id, frame=frame)
    return None


def _feature_for(
    eligibility: EntityEligibility,
    entity_id: str,
    frame: Frame,
) -> PhysicalFeature:
    """Build the datum-feature artifact from an eligibility classification."""
    kind = eligibility.feature_kind
    if kind == "plane":
        feature_kind = FeatureKind.PLANE
    elif kind == "point":
        feature_kind = FeatureKind.POINT
    else:
        feature_kind = FeatureKind.AXIS
    return PhysicalFeature(entity_id=entity_id, frame=frame, kind=feature_kind)


def extract_candidates(model: NeutralModel) -> CandidateResult:
    """Lift eligible entities from ``model`` into a :class:`CandidateResult`.

    Iterates ``model.entities`` in stored order (deterministic). An entity is
    a candidate iff all of:

    * its kind is in {POINT, LINE, AXIS, PLANE};
    * :func:`resolve_entity_frame` returns a frame;
    * it is not ``generated`` (i.e. carries a real source provenance).

    Every retained entry is recorded as a candidate; every skipped entry is
    recorded as a :class:`SkippedCandidate` with a deterministic technical
    reason.
    """
    if not isinstance(model, NeutralModel):
        raise TypeError("extract_candidates requires a NeutralModel")

    candidates: list[BridgedCandidate] = []
    skipped: list[SkippedCandidate] = []
    seen_domain: set[str] = set()

    for entity in model.entities:
        identity = entity.identity
        kind = identity.kind
        eligibility = eligible_for(kind)

        if not eligibility.eligible:
            skipped.append(SkippedCandidate(identity, "kind not eligible"))
            continue

        domain = domain_identity(identity)
        if domain.value in seen_domain:
            skipped.append(
                SkippedCandidate(
                    identity, "duplicate domain identity in one model"
                )
            )
            continue
        seen_domain.add(domain.value)

        if identity.generated:
            skipped.append(
                SkippedCandidate(
                    identity, "generated entity has no source provenance"
                )
            )
            continue

        frame = resolve_entity_frame(entity)
        if frame is None:
            skipped.append(
                SkippedCandidate(identity, "no resolvable coordinate frame")
            )
            continue

        entity_id = domain.value
        reference = _reference_for(kind, entity_id, frame)
        feature = _feature_for(eligibility, entity_id, frame)
        candidates.append(
            BridgedCandidate(
                domain_identity=domain,
                neutral_identity=identity,
                reference=reference,
                datum_feature=feature,
            )
        )

    return CandidateResult(candidates=candidates, skipped=skipped)


def select_reference(
    reference: Reference,
    constraint_type: ConstraintType,
    *,
    manual: bool = True,
) -> LocatingFeature:
    """Record an explicit human role assignment for ``reference``.

    This is the only path to a :class:`LocatingFeature`. It never infers a
    role; it simply records the explicit ``constraint_type`` with
    ``manual=True``. Sequence/DOF validation remains the Stage 1B
    :class:`~origlyph.datum.DatumReferenceFrame`'s responsibility.
    """
    return LocatingFeature(
        reference=reference, constraint_type=constraint_type, manual=manual
    )
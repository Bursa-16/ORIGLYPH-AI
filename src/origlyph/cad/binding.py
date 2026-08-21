"""Deterministic CAD-to-datum binding (Stage 2B).

This module is the single, fail-closed boundary that commits a Stage 1D
:class:`~origlyph.cad.bridge.BridgedCandidate` into the datum/reference
domain as a provenance-traced :class:`BoundReference`.

The binding does not construct datums or reference frames; it pairs the
artifacts already produced by :mod:`origlyph.cad.bridge` and validates the
locked coherence contract before yielding them to downstream consumers.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

from origlyph.cad.bridge import BridgedCandidate
from origlyph.cad.identity import (
    DomainIdentity,
    NeutralEntityIdentity,
    SourceEntityIdentity,
)
from origlyph.datum import (
    FeatureKind,
    PhysicalFeature,
    Reference,
    ReferencePoint,
    ReferenceSurface,
)

__all__ = [
    "BoundReference",
    "bind_reference",
    "bind_references",
]


@dataclass(frozen=True)
class BoundReference:
    """A validated, provenance-traced CAD-to-datum binding.

    ``BoundReference`` pairs the datum/reference artifacts lifted from a
    :class:`~origlyph.cad.bridge.BridgedCandidate` into one immutable,
    value-comparable handle. Equality and hashing include full provenance
    (neutral identity, domain identity, source identity) so that two
    bindings are equal only when they describe the same entity with the same
    origin in exactly the same way.
    """

    reference: Optional[Reference]
    datum_feature: PhysicalFeature
    neutral_identity: NeutralEntityIdentity
    domain_identity: DomainIdentity
    source_identity: Optional[SourceEntityIdentity]

    @property
    def entity_id(self) -> str:
        """The domain identity value used as the artifact entity id."""
        return self.domain_identity.value


def _validate_coherence(
    reference: Optional[Reference],
    datum_feature: PhysicalFeature,
    domain_identity: DomainIdentity,
) -> None:
    """Enforce the locked reference/feature/identity coherence contract."""
    if reference is not None:
        # Identity triple must agree: reference == feature == domain.
        if (
            reference.entity_id != datum_feature.entity_id
            or datum_feature.entity_id != domain_identity.value
        ):
            raise ValueError(
                "reference, datum_feature and domain_identity entity ids "
                "must all agree"
            )
        # The feature and its reference must share one resolved frame.
        if reference.frame != datum_feature.frame:
            raise ValueError("reference and datum_feature frames must agree")
        # Kind alignment: surface<->PLANE, point<->POINT, axis<->None.
        if isinstance(reference, ReferenceSurface):
            if datum_feature.kind is not FeatureKind.PLANE:
                raise ValueError("ReferenceSurface binds FeatureKind.PLANE only")
        elif isinstance(reference, ReferencePoint):
            if datum_feature.kind is not FeatureKind.POINT:
                raise ValueError("ReferencePoint binds FeatureKind.POINT only")
        else:
            raise ValueError(
                "unsupported reference type: %r" % type(reference).__name__
            )
    else:
        # Axis (LINE) features legitimately carry no reference.
        if datum_feature.kind is not FeatureKind.AXIS:
            raise ValueError(
                "reference-less features must be FeatureKind.AXIS"
            )


def bind_reference(candidate: BridgedCandidate) -> BoundReference:
    """Bind a single :class:`BridgedCandidate` into a validated
    :class:`BoundReference`.

    Raises
    ------
    TypeError
        If ``candidate`` is not a :class:`BridgedCandidate`.
    ValueError
        If the candidate violates the locked coherence contract.
    """
    if not isinstance(candidate, BridgedCandidate):
        raise TypeError("bind_reference requires a BridgedCandidate")
    reference = candidate.reference
    datum_feature = candidate.datum_feature
    domain_identity = candidate.domain_identity
    neutral_identity = candidate.neutral_identity
    _validate_coherence(reference, datum_feature, domain_identity)
    return BoundReference(
        reference=reference,
        datum_feature=datum_feature,
        neutral_identity=neutral_identity,
        domain_identity=domain_identity,
        source_identity=neutral_identity.source_identity,
    )


def bind_references(
    candidates: Sequence[BridgedCandidate],
) -> tuple[BoundReference, ...]:
    """Bind a sequence of candidates in order, preserving input order.

    Binding is fail-closed: if any candidate is invalid the call raises and
    no partial result is returned. Output order matches input order and the
    result is deterministic.
    """
    if not isinstance(candidates, Sequence):
        raise TypeError("bind_references requires a sequence of BridgedCandidate")
    return tuple(bind_reference(candidate) for candidate in candidates)

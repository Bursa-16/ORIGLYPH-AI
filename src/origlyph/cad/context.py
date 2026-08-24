"""Engineer functional-relevance declaration for source CAD entities.

Stage 6B. A :class:`FunctionalRelevanceDeclaration` records exactly one
statement: an identified engineer explicitly declares a source CAD entity
functionally relevant *for datum consideration*.

The declaration carries no authority beyond that statement. It does not make
a candidate eligible, assign a datum role, imply PRIMARY/SECONDARY/TERTIARY
ordering, rank or score anything, override confidence, accept a
recommendation, or create any datum or datum reference frame. Those remain
exclusive to the deterministic Stage 3 domain and the human review boundary.

Identity contract: the target is the durable :class:`SourceEntityIdentity`
(document + CAD-native key + hierarchy path). No cross-revision persistence
is claimed; resolution into a concrete import result uses the existing
neutral-model lookup contracts.

Provenance is reached through ``target`` only — source document, entity key,
and hierarchy path are never duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .identity import SourceEntityIdentity

__all__ = ["FunctionalRelevanceDeclaration"]


@dataclass(frozen=True)
class FunctionalRelevanceDeclaration:
    """An identified engineer declares a source entity functionally relevant.

    Stored state is exactly ``(target, declarer, rationale)``. See the module
    docstring for the complete semantic boundary of this record.
    """

    target: SourceEntityIdentity
    declarer: str
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.target, SourceEntityIdentity):
            raise TypeError("declaration target must be a SourceEntityIdentity")
        object.__setattr__(
            self,
            "declarer",
            _normalized_required_text(self.declarer, "declarer"),
        )
        object.__setattr__(
            self,
            "rationale",
            _normalized_required_text(self.rationale, "rationale"),
        )


def _normalized_required_text(value: object, field_name: str) -> str:
    """Strip ``value``, requiring a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped
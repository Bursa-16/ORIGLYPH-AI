"""CAD topology adapter protocol for Origlyph (Stage 22C).

Defines the minimal adapter boundary that isolates a future kernel-specific
backend object from the Origlyph domain.  The protocol converts a
backend-specific representation into a :class:`CanonicalTopologyModel`.

No concrete adapter implementation is provided in Stage 22C: there is no
B-Rep kernel available, and providing a fake default would mask the absence
of real STEP/B-Rep support.  Any attempt to use a non-existent backend raises
:class:`UnsupportedCadTopologyBackendError` explicitly.

Stage 22C does not implement production STEP import.
Stage 22C does not introduce a B-Rep CAD kernel dependency.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .exceptions import OriglyphCadError
from .identity import SourceDocumentIdentity
from .topology import CanonicalTopologyModel

__all__ = [
    "CadTopologyAdapter",
    "UnsupportedCadTopologyBackendError",
]


class UnsupportedCadTopologyBackendError(OriglyphCadError):
    """Raised when no B-Rep/CAD topology backend is available.

    This exception makes it impossible to accidentally claim STEP/B-Rep
    support: any code path that would require a real kernel but has none
    should raise this explicitly rather than returning a fake result.
    """


@runtime_checkable
class CadTopologyAdapter(Protocol):
    """Protocol for CAD topology backend adapters.

    A conforming adapter converts a backend-specific representation of a
    CAD source into a :class:`CanonicalTopologyModel`.  The adapter is
    responsible for all kernel-specific parsing; it must never expose kernel
    objects beyond this boundary.

    A ``runtime_checkable`` protocol: ``isinstance(obj, CadTopologyAdapter)``
    checks for the presence of ``to_canonical_topology`` but does NOT verify
    the signature.  Full structural conformance is verified only at static
    analysis time (Pyright).

    Implementations that encounter an error during conversion must raise
    :class:`~origlyph.cad.exceptions.CadImportError` or a subclass; they
    must never return a partially valid :class:`CanonicalTopologyModel`.

    Stage 22C provides no concrete implementation: the first real adapter
    will be introduced when a STEP/B-Rep backend is authorised in a later
    stage.
    """

    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel:
        """Convert the backend-specific source into a canonical topology model.

        Parameters
        ----------
        source:
            The :class:`~origlyph.cad.identity.SourceDocumentIdentity` of the
            CAD document being converted.  This carries format, unit system,
            and fingerprint but NOT the binary file bytes.

        Returns
        -------
        CanonicalTopologyModel
            A fully validated, kernel-independent topology model.

        Raises
        ------
        CadImportError
            On any fatal conversion failure.
        UnsupportedCadTopologyBackendError
            When called on a no-backend stub (see note above).
        """
        ...

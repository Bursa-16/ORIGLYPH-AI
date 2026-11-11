"""Unit tests for origlyph.cad.topology_adapter (Stage 22C).

Covers section J of the Stage 22C test specification:

J  Adapter protocol/contract, valid adapter result, malformed output
   rejection, unsupported backend behaviour.
"""

from __future__ import annotations

import pytest

from origlyph.cad.exceptions import CadImportError, OriglyphCadError
from origlyph.cad.identity import CadFormat, SourceDocumentIdentity, SourceUnitSystem
from origlyph.cad.topology import (
    CanonicalTopologyModel,
    DanglingTopologyReferenceError,
    TopologyEdge,
    TopologyEntityId,
    TopologyVertex,
)
from origlyph.cad.topology_adapter import (
    CadTopologyAdapter,
    UnsupportedCadTopologyBackendError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tid(value: str) -> TopologyEntityId:
    return TopologyEntityId(value)


def _source_doc(sid: str = "adapter-doc") -> SourceDocumentIdentity:
    return SourceDocumentIdentity(
        source_id=sid,
        format=CadFormat.STEP,
        unit_system=SourceUnitSystem(),
    )


def _empty_model() -> CanonicalTopologyModel:
    return CanonicalTopologyModel()


def _minimal_model() -> CanonicalTopologyModel:
    v0 = TopologyVertex(entity_id=_tid("v0"))
    v1 = TopologyVertex(entity_id=_tid("v1"))
    e0 = TopologyEdge(
        entity_id=_tid("e0"),
        start_vertex_id=_tid("v0"),
        end_vertex_id=_tid("v1"),
    )
    return CanonicalTopologyModel(vertices=[v0, v1], edges=[e0])


# ---------------------------------------------------------------------------
# Stub conforming adapter
# ---------------------------------------------------------------------------


class _StubAdapter:
    """Minimal stub that satisfies the CadTopologyAdapter protocol."""

    def __init__(self, model: CanonicalTopologyModel) -> None:
        self._model = model

    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel:
        return self._model


# ---------------------------------------------------------------------------
# Stub raising adapter (simulates backend error)
# ---------------------------------------------------------------------------


class _ErrorAdapter:
    """Stub adapter that raises CadImportError on conversion."""

    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel:
        raise CadImportError("simulated backend failure")


# ---------------------------------------------------------------------------
# Stub no-backend adapter (simulates missing kernel)
# ---------------------------------------------------------------------------


class _NoBackendAdapter:
    """Stub adapter representing a kernel that is not installed."""

    def to_canonical_topology(
        self, source: SourceDocumentIdentity
    ) -> CanonicalTopologyModel:
        raise UnsupportedCadTopologyBackendError(
            "no B-Rep kernel available; Stage 22C does not provide one"
        )


# ---------------------------------------------------------------------------
# Section J: Adapter tests
# ---------------------------------------------------------------------------


def test_j_stub_adapter_satisfies_protocol() -> None:
    """_StubAdapter satisfies the CadTopologyAdapter runtime-checkable protocol."""
    assert isinstance(_StubAdapter(_empty_model()), CadTopologyAdapter)


def test_j_valid_adapter_returns_canonical_model() -> None:
    """A conforming adapter returns a CanonicalTopologyModel."""
    adapter = _StubAdapter(_minimal_model())
    result = adapter.to_canonical_topology(_source_doc())
    assert isinstance(result, CanonicalTopologyModel)


def test_j_valid_adapter_result_has_correct_entity_counts() -> None:
    """The returned model carries the expected entity counts."""
    adapter = _StubAdapter(_minimal_model())
    result = adapter.to_canonical_topology(_source_doc())
    assert len(result.vertices) == 2
    assert len(result.edges) == 1


def test_j_adapter_source_passed_through() -> None:
    """The source SourceDocumentIdentity passed to the adapter is accepted."""
    doc = _source_doc("step-part-99")
    adapter = _StubAdapter(CanonicalTopologyModel(source=doc))
    result = adapter.to_canonical_topology(doc)
    assert result.source is not None
    assert result.source.source_id == "step-part-99"


def test_j_malformed_model_rejected_at_model_construction() -> None:
    """Malformed adapter output (dangling ref) fails at model construction."""
    with pytest.raises(DanglingTopologyReferenceError):
        _v = TopologyVertex(entity_id=_tid("v0"))
        _e = TopologyEdge(
            entity_id=_tid("e0"),
            start_vertex_id=_tid("v0"),
            end_vertex_id=_tid("MISSING"),
        )
        CanonicalTopologyModel(vertices=[_v], edges=[_e])


def test_j_error_adapter_raises_cad_import_error() -> None:
    """An adapter signalling a backend failure raises CadImportError."""
    adapter = _ErrorAdapter()
    with pytest.raises(CadImportError):
        adapter.to_canonical_topology(_source_doc())


def test_j_no_backend_adapter_raises_unsupported_error() -> None:
    """An adapter with no kernel raises UnsupportedCadTopologyBackendError."""
    adapter = _NoBackendAdapter()
    with pytest.raises(UnsupportedCadTopologyBackendError):
        adapter.to_canonical_topology(_source_doc())


def test_j_unsupported_backend_error_is_cad_error() -> None:
    """UnsupportedCadTopologyBackendError is a subclass of OriglyphCadError."""
    assert issubclass(UnsupportedCadTopologyBackendError, OriglyphCadError)


def test_j_cad_topology_adapter_is_runtime_checkable() -> None:
    """CadTopologyAdapter is a runtime_checkable Protocol."""
    class _Bare:
        pass

    assert not isinstance(_Bare(), CadTopologyAdapter)


def test_j_adapter_protocol_requires_to_canonical_topology() -> None:
    """An object without to_canonical_topology does not satisfy the protocol."""
    class _Missing:
        def wrong_method(self) -> None:
            pass

    assert not isinstance(_Missing(), CadTopologyAdapter)


def test_j_empty_model_accepted_by_adapter() -> None:
    """An adapter returning an empty CanonicalTopologyModel is valid."""
    adapter = _StubAdapter(_empty_model())
    result = adapter.to_canonical_topology(_source_doc())
    assert isinstance(result, CanonicalTopologyModel)
    assert len(result.vertices) == 0

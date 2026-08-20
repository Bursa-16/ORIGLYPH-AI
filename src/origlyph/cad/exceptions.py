"""CAD import-domain exceptions for Origlyph.

All CAD import-domain failures derive from :class:`OriglyphCadError` so callers
can catch the whole domain with one base type while still discriminating
specific failure classes. This hierarchy is intentionally minimal. It does not
modify the geometry exception hierarchy (``origlyph.geometry.exceptions``).

Failure classes are not warnings: raising one of these aborts the import or
construction. Non-fatal issues are represented by warning/unsupported value
objects in :mod:`origlyph.cad.model` instead.
"""


class OriglyphCadError(Exception):
    """Base class for all Origlyph CAD import-domain errors."""


class CadImportError(OriglyphCadError):
    """A fatal CAD import failure; no neutral model is produced."""


class UnsupportedCadFormatError(CadImportError):
    """Raised when a source document format is not supported at import."""


class UnsupportedSourceUnitError(OriglyphCadError):
    """Raised for an unknown or unsupported source unit.

    Origlyph never guesses source units: an unknown unit is a failure, not a
    silent assumption of millimetres/radians.
    """


class InvalidSourceIdentityError(OriglyphCadError):
    """Raised when a source document/entity identity is invalid or empty."""


class DuplicateSourceEntityError(OriglyphCadError):
    """Raised when a mapping/model contains a duplicate source entity key."""


class DuplicateNeutralEntityError(OriglyphCadError):
    """Raised when a model/mapping contains a duplicate neutral identity."""
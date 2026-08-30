# Origlyph v0.3.0-alpha.2

## Summary

v0.3.0-alpha.2 is a documentation/release-snapshot refresh. It publishes a
corrected and current release snapshot of the v0.3 alpha line: the v0.3.0
capability set is unchanged, and the README on this snapshot now reflects the
actual v0.3 capability.

## What changed

- documentation/release-snapshot refresh
- the current README reflects the actual v0.3 capability
- package version 0.3.0a1 → 0.3.0a2
- no other content changes

## Engineering runtime

- no new engineering runtime feature beyond v0.3.0-alpha.1
- the STL importer implementation is unchanged
- the datum/reference workflow implementation is unchanged

## Validation

- validated baseline: 501 passing tests
- Ruff: all checks passed
- Pyright: 0 errors and 0 warnings

## Tag immutability

- v0.3.0-alpha.1 remains immutable and continues to point at its original
  release commit
- alpha.2 exists to publish a corrected and current release snapshot; it does
  not replace, move, or rewrite alpha.1

## Artifacts

- artifact scope is GitHub-generated source archives only
- no wheel, sdist, binary, or additional artifact is published

## Explicitly not included

- no new engineering runtime features
- no dependency changes
- no workflow/CI changes
- no production-readiness, certification, or ASME/ISO compliance claims

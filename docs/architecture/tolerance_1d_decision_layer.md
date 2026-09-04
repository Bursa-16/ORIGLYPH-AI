# 1D Tolerance Decision Layer (Stage 15K)

## Purpose

Stage 15K is a deterministic high-level tolerance decision layer that
orchestrates the existing tolerance-analysis engines into a single
coherent, traceable engineering decision.

It answers questions such as:

- Is the stack compliant with the specified tolerance requirement?
- Does worst-case analysis pass?
- Does statistical analysis pass?
- Is the allocation plan respected?
- Which contributors are controlling the result?
- Is the result robust or marginal?
- Are worst-case and statistical conclusions consistent?
- Does covariance materially affect the statistical conclusion?
- What is the deterministic overall engineering decision?
- What deterministic reasons explain that decision?

The decision layer is **not** an AI recommendation engine.  It is
deterministic, explainable, traceable, fail-closed, formula-driven,
and reproducible.

It does **not** implement health scores, confidence scores, or any
probabilistic text generation.  Every observation is a typed enum
with structured numeric evidence.

## Architecture

The decision layer **does not** reimplement any of the underlying
math.  It calls the authoritative engines and combines their outputs
under deterministic decision rules.

Authoritative engines reused:

- ``worst_case`` (Stage 15C-R)
- ``statistical`` (Stage 15D)
- ``worst_case_sensitivity`` (Stage 15F)
- ``statistical_sensitivity`` (Stage 15F)
- ``worst_case_budget`` (Stage 15G)
- ``statistical_budget`` (Stage 15G)
- ``validate_allocation`` (Stage 15H)
- ``reconcile_allocation`` (Stage 15I)
- ``reconcile_statistical_allocation`` (Stage 15J)

The decision layer is the only new piece of logic; it adds
orchestration, deterministic decision rules, and structured
explainability on top of these engines.

## API

```python
from origlyph.tolerance import evaluate_tolerance_decision

result = evaluate_tolerance_decision(
    worst_case_stack=wc_stack,
    statistical_stack=stat_stack,
    allowed_worst_case_span=0.50,
    allowed_combined_sigma=0.20,
    sigma_multiplier=3.0,
    correlations=(Correlation("A", "B", 0.5),),
    worst_case_allocation=wc_plan,           # optional
    statistical_allocation=stat_plan,        # optional
    require_complete=True,                    # optional
)
```

The function accepts:

- At least one of ``worst_case_stack`` or ``statistical_stack``.
- Optionally one or both allowed windows
  (``allowed_worst_case_span`` / ``allowed_combined_sigma``).
- Optionally an allocation plan for each kind of stack.
- Optionally a sequence of ``Correlation`` objects for the
  statistical analysis.  The same correlation map is used by the
  decision-layer independent reference for the covariance-effect
  classification.

It returns a single ``ToleranceDecisionResult`` with explicit
dimension states, controlling contributors, covariance effect,
and a structured reason list.

## Decision statuses

``ToleranceDecisionStatus`` is a small explicit enum with four
members:

- ``PASS`` — all required deterministic criteria pass with no
  boundary condition.
- ``MARGINAL`` — the design technically passes but is at the
  deterministic decision boundary according to the established
  equality policy (``1e-12``).  MARGINAL requires explicit
  engineering review; it is not a PASS.
- ``FAIL`` — a mandatory engineering criterion is violated.  The
  decision layer never silently downgrades a FAIL.
- ``INCOMPLETE`` — the decision cannot be safely completed because
  mandatory deterministic inputs are absent.

These statuses are intentionally distinct from the existing
``BudgetStatus``, ``AllocationStatus``, and ``ReconciliationStatus``
enums, which describe single-dimension compliance.

## Per-dimension evaluation states

Each individual evaluation dimension reports one of:

- ``PASS`` — dimension passes the deterministic criterion.
- ``AT_BOUNDARY`` — dimension is at the equality boundary.
- ``FAIL`` — dimension violates the criterion.
- ``NOT_REQUESTED`` — no criterion was supplied.
- ``INCOMPLETE`` — a criterion was supplied but a required input
  was missing.

## Worst-case policy

Worst-case remains the deterministic hard-bound analysis.  The
decision layer preserves the exact result of the existing
worst-case engine and treats a worst-case FAIL as a hard FAIL.

## Statistical policy

The decision layer uses the authoritative ``statistical`` engine
and supports both independent RSS and caller-supplied
correlations.  The same correlation map is used for both the
actual statistical analysis and the allocation-side variance.
No two competing correlation maps are maintained; invalid rho
values are not silently repaired.

## Correlation / covariance policy

When correlations are supplied, the decision layer makes the
effect visible via ``ToleranceDecisionCovarianceEffect``:

- ``NOT_REQUESTED`` — no correlations supplied.
- ``INCREASES`` — correlated sigma > independent sigma, beyond
  the equality tolerance.
- ``DECREASES`` — correlated sigma < independent sigma, beyond
  the equality tolerance.
- ``NEUTRAL`` — within the equality tolerance.

The independent reference is computed by calling the same
authoritative ``statistical`` engine with the same stack and
multiplier, but with no correlations.

## Allocation reconciliation policy

- If a worst-case allocation plan is supplied, the decision layer
  calls the existing ``reconcile_allocation`` engine (Stage 15I).
- If a statistical allocation plan is supplied, the decision
  layer calls ``reconcile_statistical_allocation`` (Stage 15J).
- If no plan is supplied, no allocation dimension is fabricated.
  The ``worst_case_reconciliation_passed`` and
  ``statistical_reconciliation_passed`` convenience booleans
  report ``None`` to indicate that the dimension was not
  evaluated.

## Sensitivity / controlling-contributor policy

The decision layer calls the existing
``worst_case_sensitivity`` and ``statistical_sensitivity``
engines.  Controlling contributors are sorted by descending
fraction.  Ties are broken by contributor name ascending to
guarantee determinism.

No machine-learning importance score is invented.  The decision
layer reuses the actual sensitivity metric already established
in Origlyph.

## Margin / boundary policy

Boundary classification uses the established equality policy of
``1e-12``.  A dimension that is at or within this tolerance of
the allowed value is classified as ``AT_BOUNDARY``.  The decision
layer distinguishes:

- clearly within requirement
- at deterministic boundary
- beyond requirement

without introducing a new epsilon.

## Equality policy

The same deterministic engineering equality tolerance of
``1e-12`` is reused from Stage 15G / 15H / 15I / 15J.  No new or
contradictory epsilon is introduced.

## Completeness / fail-closed behaviour

The decision layer is fail-closed:

- Neither stack supplied → ``InvalidToleranceDecisionError`` raised.
- An allowed window supplied without the corresponding stack →
  the dimension is reported as ``INCOMPLETE``; the decision
  becomes ``INCOMPLETE`` or ``FAIL`` depending on the
  failure-severity rules.
- Incomplete allocation plans are flagged with
  ``INCOMPLETE_ALLOCATION`` reason code.
- Invalid sigma multipliers or allowed windows are rejected with
  ``InvalidToleranceDecisionError``.

The function never silently produces PASS for an absent mandatory
input.

## Traceability model

Every observation is a ``ToleranceDecisionReason``:

- ``code`` — stable reason code (e.g. ``WC_REQUIREMENT_EXCEEDED``).
- ``severity`` — ``INFO``, ``BOUNDARY``, or ``FAILURE``.
- ``scope`` — optional scope identifier (contributor name,
  dimension name, ``"consistency"``, etc.).
- ``detail`` — optional deterministic numeric / short-string
  evidence.

Stable reason codes include:

- ``WC_REQUIREMENT_EXCEEDED`` / ``WC_REQUIREMENT_AT_BOUNDARY``
- ``STAT_REQUIREMENT_EXCEEDED`` / ``STAT_REQUIREMENT_AT_BOUNDARY``
- ``WC_ALLOCATION_EXCEEDED`` / ``WC_ALLOCATION_AT_BOUNDARY``
- ``STAT_ALLOCATION_EXCEEDED`` / ``STAT_ALLOCATION_AT_BOUNDARY``
- ``INCOMPLETE_ALLOCATION``
- ``CORRELATION_INCREASES_SIGMA``
- ``CORRELATION_DECREASES_SIGMA``
- ``CORRELATION_EFFECTIVELY_NEUTRAL``
- ``WC_STAT_INCONSISTENT``
- ``NO_STACK_PROVIDED``
- ``NO_REQUIREMENT_PROVIDED``

## Result model

``ToleranceDecisionResult`` exposes:

- ``overall_status`` — ``ToleranceDecisionStatus``
- ``dimensions`` — ordered ``ToleranceDecisionDimension`` list
- ``worst_case_passed`` — ``True`` / ``False`` / ``None``
- ``statistical_passed`` — ``True`` / ``False`` / ``None``
- ``worst_case_reconciliation_passed`` — ``True`` / ``False`` / ``None``
- ``statistical_reconciliation_passed`` — ``True`` / ``False`` / ``None``
- ``sensitivity`` — ``ToleranceDecisionSensitivity`` with
  controlling contributors in deterministic order
- ``covariance_effect`` — ``ToleranceDecisionCovarianceEffect``
- ``evidence`` — ``ToleranceDecisionEvidence`` with structured
  numeric evidence
- ``reasons`` — ordered ``ToleranceDecisionReason`` list
- ``is_complete`` — ``True`` when no dimension is ``INCOMPLETE``

## Examples

### Simple PASS

```python
result = evaluate_tolerance_decision(
    worst_case_stack=wc_stack,            # span 0.45
    statistical_stack=stat_stack,        # combined sigma 0.07
    allowed_worst_case_span=0.50,
    allowed_combined_sigma=0.20,
)
assert result.overall_status is ToleranceDecisionStatus.PASS
assert result.worst_case_passed is True
assert result.statistical_passed is True
```

### Hard worst-case FAIL

```python
result = evaluate_tolerance_decision(
    worst_case_stack=wc_stack,
    allowed_worst_case_span=0.40,
)
assert result.overall_status is ToleranceDecisionStatus.FAIL
assert result.worst_case_passed is False
assert any(
    r.code is ToleranceDecisionReasonCode.WC_REQUIREMENT_EXCEEDED
    for r in result.reasons
)
```

### Boundary / MARGINAL

```python
result = evaluate_tolerance_decision(
    worst_case_stack=wc_stack,            # span 0.45
    allowed_worst_case_span=0.45,         # exact boundary
)
assert result.overall_status is ToleranceDecisionStatus.MARGINAL
assert result.worst_case_passed is True   # at boundary
assert any(
    r.code is ToleranceDecisionReasonCode.WC_REQUIREMENT_AT_BOUNDARY
    for r in result.reasons
)
```

### WC FAIL + Stat PASS preserved

```python
result = evaluate_tolerance_decision(
    worst_case_stack=wc_stack,            # span 0.45
    statistical_stack=stat_stack,        # combined sigma 0.07
    allowed_worst_case_span=0.40,
    allowed_combined_sigma=0.20,
)
assert result.overall_status is ToleranceDecisionStatus.FAIL
assert result.worst_case_passed is False
assert result.statistical_passed is True
assert any(
    r.code is ToleranceDecisionReasonCode.WC_STAT_INCONSISTENT
    for r in result.reasons
)
```

### Covariance effect

```python
result = evaluate_tolerance_decision(
    statistical_stack=stat_stack,
    correlations=(Correlation("A", "B", 0.5),),
)
assert (
    result.covariance_effect
    is ToleranceDecisionCovarianceEffect.INCREASES
)
```

## Non-goals

The decision layer does **not**:

- replace the underlying deterministic engines
- implement any kind of AI recommendation, scoring, or ranking
- invent tolerance allocation plans
- infer manufacturing capability
- modify tolerance values
- perform optimization, redistribution, or design recommendation
- introduce a new equality epsilon
- swallow exceptions silently
- fabricate data when required inputs are missing

## Authority statement

> Stage 15K does not replace the underlying deterministic engines.
> It orchestrates their outputs into a deterministic engineering
> decision.

> AI does not override deterministic tolerance calculations.


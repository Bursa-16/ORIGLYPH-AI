"""Deterministic 1D worst-case tolerance stack engine.

This engine computes the worst-case minimum, maximum, deviations, and total
span for a :class:`ToleranceStack`. The calculation is based on interval
propagation: each contribution contributes an admissible interval to the
stack, and the stack extremes are the sums of the interval bounds.

For a FORWARD contribution the interval in stack space is::

    [nominal + lower_deviation, nominal + upper_deviation]

For an INVERSE contribution the interval is reversed because the contribution
is subtracted from the stack::

    [-(nominal + upper_deviation), -(nominal + lower_deviation)]

The engine is deterministic: identical inputs always produce identical
outputs. No random behavior, timestamps, network calls, or AI participation
is involved.
"""

from __future__ import annotations

from .exceptions import InvalidStackError
from .models import ToleranceStack, WorstCaseResult


def worst_case(stack: ToleranceStack) -> WorstCaseResult:
    """Compute the deterministic 1D worst-case result for a tolerance stack.

    Parameters
    ----------
    stack:
        The ordered tolerance stack to analyse. Must contain at least one
        contribution.

    Returns
    -------
    WorstCaseResult
        The deterministic worst-case analysis result.

    Raises
    ------
    InvalidStackError
        If the stack is empty.
    """
    if not stack.contributions:
        raise InvalidStackError("cannot analyse an empty tolerance stack")

    nominal_total = 0.0
    lower_total = 0.0
    upper_total = 0.0

    for contribution in stack.contributions:
        lower, upper = contribution.interval()
        if contribution.direction.value == "forward":
            nominal_total += contribution.nominal
        else:
            nominal_total -= contribution.nominal
        lower_total += lower
        upper_total += upper

    lower_deviation = lower_total - nominal_total
    upper_deviation = upper_total - nominal_total
    total_span = upper_total - lower_total

    return WorstCaseResult(
        nominal=nominal_total,
        minimum=lower_total,
        maximum=upper_total,
        lower_deviation=lower_deviation,
        upper_deviation=upper_deviation,
        total_span=total_span,
    )

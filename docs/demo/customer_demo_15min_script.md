# Origlyph AI — 15-Minute Demo Script

**Purpose:** Full customer demo — golden workflow
**Duration:** 15 minutes
**Pre-requisite:** `DEMO_READINESS: PASS` from `scripts\check_demo_readiness.ps1`
**Reference:** `docs/demo/customer_demo_runbook.md` for detailed talking points

---

## 0–2 min — Problem and Platform Introduction

**SCREEN:** Terminal / blank — demo not yet launched

**ACTION:** Speak first. Launch the demo at the end of this segment.

**WHAT TO SAY:**
> "Most engineering teams manage tolerance analysis in spreadsheets —
> manually maintained, difficult to trace, and fragile under change.
> When a tolerance decision is reviewed six months later, the reasoning
> is often unclear, the calculation history is gone, and repeating it
> means starting over.
>
> Origlyph AI is built around a different model: every tolerance input
> is explicit, every analysis is deterministic, and every project state
> is uniquely identified. The goal is not to replace the engineer's
> judgement — it is to make that judgement visible, traceable, and reproducible."

**ACTION:** Launch the demo:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```

**WHAT TO SAY:**
> "This is the Origlyph tolerance workspace. Today we are working through
> a bracket-mounting assembly — a representative three-contributor stack
> that exercises the full workflow."

**KEY VALUE:** Structured, traceable, deterministic engineering.

---

## 2–4 min — Tolerance Chain and Contributors

**SCREEN:** Tolerance chain editor — three rows visible

**ACTION:** Point to each contributor row in turn.

**WHAT TO SAY:**
> "The chain has three contributors.
>
> Bracket depth: nominal 25 mm, tolerance ±0.10, forward contributor —
> it adds to the stack.
>
> Pin length: nominal 5 mm, tolerance ±0.08, also forward.
>
> Shim thickness: nominal 2.5 mm, tolerance ±0.05, inverse —
> it reduces the stack. This is a common physical scenario: a compensating
> element that partially cancels out variation from other contributors.
>
> Nothing is inferred from geometry. Every value is entered by the engineer.
> The system never auto-sets a tolerance or assumes a direction."

**KEY VALUE:** Explicit, controlled input — no hidden inference.

---

## 4–6 min — Worst Case and RSS Statistical Analysis

**SCREEN:** Analysis results

**ACTION:** Confirm mode = `worst_case`. Click **Run Analysis**.

**WHAT TO SAY:**
> "Worst-case analysis computes the arithmetic sum of all contributor spans.
> It assumes every part sits at its worst possible dimension simultaneously —
> the most conservative approach.
>
> Total span: 0.46. That is 0.20 from Bracket depth, 0.16 from Pin length,
> and 0.10 from Shim thickness."

**ACTION:** Switch mode to `rss_statistical`. Click **Run Analysis**.

**WHAT TO SAY:**
> "RSS statistical analysis combines the variances quadratically.
> For independent contributors, this is a statistically sound and
> less conservative estimate.
>
> Combined sigma: approximately 0.137 — considerably smaller than 0.46.
>
> Both results are correct. They answer different questions:
> worst-case tells you the theoretical maximum exposure;
> RSS tells you the expected statistical performance."

**KEY VALUE:** Two complementary analysis modes, both deterministic.

---

## 6–8 min — Specification and Decision

**SCREEN:** Specification limits and Decision sections

**ACTION:** Point to Specification: WC span = 0.40, combined sigma = 0.15.

**WHAT TO SAY:**
> "The specification comes from the design requirement — not from the analysis.
> The system never auto-sets a limit. Allowed worst-case span is 0.40.
> Allowed combined sigma is 0.15.
>
> These were entered by the engineer. A blank field means no specification
> exists for that mode — the system does not substitute a default."

**ACTION:** Evaluate Decision in worst-case mode (switch back, Run Analysis, Evaluate Decision).

**WHAT TO SAY:**
> "In worst-case mode: the 0.46 span exceeds the 0.40 limit. The decision is FAIL.
> This is intentional — the demo shows a real engineering situation, not a
> pre-cooked pass. The current tolerances do not meet the worst-case requirement."

**ACTION:** Switch to RSS, Run Analysis, Evaluate Decision.

**WHAT TO SAY:**
> "In RSS statistical mode: combined sigma 0.137 is within the 0.15 allowance.
> The decision is PASS. Same chain, different analysis mode, different outcome —
> and both are correct and traceable."

**KEY VALUE:** Explicit decision surface — not a probability estimate, a deterministic comparison.

---

## 8–10 min — Sensitivity Analysis

**SCREEN:** Sensitivity section

**ACTION:** Switch back to worst-case, Run Analysis, Run Sensitivity.

**WHAT TO SAY:**
> "Sensitivity analysis quantifies each contributor's fractional impact on the
> total span.
>
> Bracket depth: 43.5% — the dominant contributor.
> Pin length: 34.8%.
> Shim thickness: 21.7%.
>
> If we need to reduce the worst-case span to meet the 0.40 specification,
> Bracket depth is where design effort pays off most. A 10% reduction in
> Bracket depth tolerance has more than twice the impact of the same
> reduction in Shim thickness.
>
> This makes sensitivity a design-direction tool, not just an audit output."

**KEY VALUE:** Actionable contributor ranking for design improvement.

---

## 10–11.5 min — Budget Analysis

**SCREEN:** Budget section

**ACTION:** Run Budget (still in worst-case mode).

**WHAT TO SAY:**
> "Budget inspection compares each contributor's actual span against
> the allowed specification.
>
> Status: over-budget. Actual span 0.46, allowed 0.40 — we are 0.06 over.
>
> The per-contributor breakdown shows how each contributor consumes
> the available budget:
> Bracket depth 43.5%, Pin length 34.8%, Shim thickness 21.7%.
>
> This is a read-only view. Budget inspection measures the current state —
> it does not change the tolerances."

**KEY VALUE:** Quantified gap between current state and requirement.

---

## 11.5–13 min — Allocation Plan and Validation

**SCREEN:** Allocation Plan section

**ACTION:** Point to the pre-loaded allocation plan.

**WHAT TO SAY:**
> "The allocation plan is the target tolerance distribution —
> what the contributors should become after design optimisation.
>
> The plan sets a total budget of 0.30 — tighter than the specification's 0.40,
> to give design margin. The budget is distributed:
> Bracket depth 0.12, Pin length 0.10, Shim thickness 0.08.
> Sum: exactly 0.30.
>
> Allocation is entered manually by the engineer. It is a target, not an
> automatic calculation."

**ACTION:** Apply Allocation Plan. Then click Validate Allocation.

**WHAT TO SAY:**
> "Applying the plan is an explicit action — nothing happens automatically.
>
> Validation then confirms structural consistency:
> the allocated spans are correctly assigned, the sum matches the budget,
> and nothing is left unassigned.
>
> Result: FULLY ALLOCATED. Remaining unallocated: zero."

**KEY VALUE:** Explicit allocation target + deterministic structural validation.

---

## 13–14 min — Save and Open

**SCREEN:** Project File section

**ACTION:** Click Save Project — save to a known path (e.g. Desktop).

**WHAT TO SAY:**
> "The full workspace state — chain, specification, allocation plan —
> saves to a single project file.
>
> Analysis results are not stored, because they can always be recomputed
> deterministically from the same inputs. The saved file captures engineering
> intent; results are recomputed on demand."

**ACTION:** Click Open Project — reopen the saved file.

**WHAT TO SAY:**
> "On reopen, the chain, specification, and allocation plan are restored
> exactly as saved. The configuration fingerprint is identical — this is the
> same engineering state.
>
> Re-run worst-case analysis and the result is 0.46, FAIL — as expected.
> Deterministic persistence means any colleague, on any machine, can
> open this project and reproduce the same results."

**KEY VALUE:** Reproducible project state — traceability across time and teams.

---

## 14–15 min — Closing and Q&A Transition

**SCREEN:** Demo window (close it now or leave visible for reference)

**ACTION:** Summarise and invite questions.

**WHAT TO SAY:**
> "What you have seen is a complete, structured tolerance-engineering
> workflow — from chain definition, through worst-case and statistical
> analysis, specification comparison, decision, sensitivity, budget,
> allocation plan, and traceable project persistence.
>
> Every result is computed deterministically. Every decision is explicit
> and traceable. The project identity is unique per engineering state.
>
> This release is focused on 1D tolerance-chain analysis. The platform
> architecture is designed to extend toward audit and governance workflows,
> richer analysis modes, and broader engineering integration as requirements develop.
>
> I am happy to answer questions about what you have seen, or to discuss
> how this fits your current tolerance engineering process."

**KEY VALUE:** Complete traceable workflow + honest scope statement + open discussion.

---

*For detailed talking points at each step, refer to `docs/demo/customer_demo_runbook.md`.*
*For expected values, refer to `docs/demo/customer_demo_cheat_sheet.md`.*

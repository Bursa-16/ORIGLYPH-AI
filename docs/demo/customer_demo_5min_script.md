# Origlyph AI — 5-Minute Demo Script

**Purpose:** Executive or introductory demo
**Duration:** 5 minutes
**Pre-requisite:** `DEMO_READINESS: PASS` from `scripts\check_demo_readiness.ps1`

---

## 00:00–00:30 — The Problem

**SCREEN:** Blank / terminal only — demo window not yet open

**ACTION:** Speak before launching. Do not open the window yet.

**WHAT TO SAY:**
> "Tolerance analysis in most engineering teams runs in spreadsheets.
> Every change means manually updating a formula, re-checking limits,
> and hoping the logic is still correct. The results are not traceable,
> the decisions are not reproducible, and there is no structured way to
> communicate what changed and why.
>
> What I am about to show you is a different approach."

**KEY VALUE:** Frame the pain — fragmented, non-traceable, spreadsheet-driven.

---

## 00:30–01:00 — The Project and Tolerance Chain

**SCREEN:** Launch the demo

**ACTION:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```
Point to the **Tolerance chain editor** section showing three contributors.

**WHAT TO SAY:**
> "This is the Origlyph tolerance workspace. The project is a bracket-mounting
> assembly — three contributing features: Bracket depth, Pin length, and Shim
> thickness. Every contributor has an explicit nominal value, tolerance, and
> stack direction. Nothing is inferred. The engineer defines every entry."

**KEY VALUE:** Explicit, structured input — no hidden assumptions.

---

## 01:00–02:00 — Analysis: Worst Case and RSS

**SCREEN:** Analysis results section

**ACTION:** Run Worst Case (mode = worst_case → Run Analysis), then switch to
RSS Statistical and Run Analysis again.

**WHAT TO SAY:**
> "Worst-case analysis gives us the arithmetic sum of all spans — 0.46.
> This is the most conservative approach.
>
> RSS statistical analysis combines the variances quadratically —
> a more realistic view when contributors are independent.
> Combined sigma is approximately 0.137.
>
> Same chain. Same inputs. Two different analysis modes. Both computed
> deterministically — the same inputs will always give the same outputs."

**KEY VALUE:** Two analysis modes, both deterministic and traceable.

---

## 02:00–03:00 — Decision and Sensitivity

**SCREEN:** Decision and Sensitivity sections

**ACTION:** Evaluate Decision (worst-case mode shows FAIL, RSS shows PASS).
Switch back to worst-case, Run Analysis, Run Sensitivity.

**WHAT TO SAY:**
> "The decision engine compares the result against the specification.
> Worst-case fails — the 0.46 span exceeds the 0.40 limit.
> RSS passes — sigma 0.137 is within the 0.15 allowance.
>
> Sensitivity tells us where to focus: Bracket depth drives 43.5% of
> the total span. If we need to reduce the worst-case result, that is
> where design effort pays off most."

**KEY VALUE:** Explicit PASS/FAIL decision + actionable sensitivity ranking.

---

## 03:00–04:00 — Budget and Allocation

**SCREEN:** Budget and Allocation Plan sections

**ACTION:** Run Budget. Point to Allocation Plan (pre-loaded).

**WHAT TO SAY:**
> "Budget inspection shows the current state: over-budget by 0.06.
> We are using 0.46 of the 0.40 allowed.
>
> The allocation plan is the target — what the tolerances should become
> after redesign. Budget 0.30, distributed across the three contributors.
> Validation confirms the plan is structurally consistent:
> fully allocated, nothing left unassigned."

**KEY VALUE:** Budget visibility + explicit allocation target — not automatic, but structured.

---

## 04:00–04:30 — Save and Open

**SCREEN:** Project File section

**ACTION:** Save Project (save to Desktop). Open Project (reopen it).

**WHAT TO SAY:**
> "The entire project state — chain, specification, allocation plan —
> saves to a single file. Reopen it and the state is restored exactly.
> Re-run any analysis and the results are identical. The project has a
> unique configuration fingerprint — every meaningful change creates
> a new identifiable state."

**KEY VALUE:** Deterministic persistence — traceability across time and teams.

---

## 04:30–05:00 — Closing Value Proposition

**SCREEN:** Demo window (can close now or leave open)

**ACTION:** Summarise verbally.

**WHAT TO SAY:**
> "What you have seen is a structured, deterministic tolerance-engineering
> workflow — from chain definition, through analysis, decision, sensitivity,
> budget, and allocation, to a saved project anyone can reopen and verify.
>
> Every result is traceable. Every decision is explicit. And the platform is
> designed to grow — toward audit, governance, and richer tolerance workflows
> as your requirements develop.
>
> This is Origlyph AI."

**KEY VALUE:** Deterministic foundation + structured growth path.

# Origlyph AI — Customer Demo Cheat Sheet

**Version:** v0.4.0-alpha.7  |  **Duration:** 10–15 min

---

## Opening line

> "Origlyph AI turns tolerance analysis from isolated calculations
> into a deterministic, traceable engineering workflow."

---

## Demo flow

```
Chain
  → Analyze (Worst Case)       FAIL  (0.46 > spec 0.40)
  → Analyze (RSS Statistical)  PASS  (sigma 0.137 < spec 0.15)
  → Decide
  → Sensitivity                bracket_depth 43.5% | pin_length 34.8%
  → Budget                     over_budget (0.46 / 0.40)
  → Allocation Plan            budget 0.30 = 0.12 + 0.10 + 0.08
  → Validate Allocation        FULLY ALLOCATED, remaining = 0
  → Save Project
  → Reopen Project             state restored exactly
```

---

## Launch

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```

Or double-click `scripts\run_tolerance_demo.cmd`.

---

## Key differentiators

| Claim | Status |
|---|---|
| Deterministic calculation | YES — same inputs, same outputs, always |
| Explicit engineering inputs | YES — nothing inferred or auto-set |
| Traceable project identity | YES — SHA-256 fingerprint per state |
| Fail-closed validation | YES — blank/invalid = explicit error |
| Auth. state vs. derived results | YES — chain/spec/plan persisted; results recomputed |
| Sensitivity ranking | YES — per-contributor impact quantified |
| Budget utilisation | YES — actual vs. allowed span |
| Allocation plan validation | YES — structural consistency check |
| Deterministic persistence | YES — save/reload reproduces exact state |

---

## Known limitations (be honest)

| Feature | Status |
|---|---|
| Automatic allocation optimisation | NOT implemented — manual entry |
| Correlated RSS (covariance) | Engine done; not yet in workspace UI |
| CAD / STEP import | Not implemented (STL only) |
| Full GD&T evaluation | Not implemented |
| Company standards library | Not implemented |
| Audit / governance UI | Engine done; workspace UI is future work |

---

## Expected demo values

| Step | Key result |
|---|---|
| Worst Case | total span = **0.46**, decision = **FAIL** |
| RSS Statistical | combined sigma = **0.137**, decision = **PASS** |
| Sensitivity #1 | bracket_depth, share = **43.5%** |
| Budget | status = **over_budget** (0.46 / 0.40) |
| Allocation Validate | status = **FULLY ALLOCATED**, remaining = **0** |
| Fingerprint | `6b95f5e9...` (stable for this dataset) |

---

## One-sentence answers

**Is it deterministic?** Yes — always.

**Does AI change the numbers?** No — AI is advisory only.

**Can we save and reload?** Yes — exact state restored.

**Can it auto-optimise allocation?** Not in this release.

---

## Quick reset

Close window → re-run launcher → dataset reloads deterministically.
No git state changes. No repository mutation.

---

*Full runbook: `docs/demo/customer_demo_runbook.md`*

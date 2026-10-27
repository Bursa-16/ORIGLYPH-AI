# Origlyph AI — Golden Demo Baseline

**Stage:** 18D — Demo Freeze & Customer Presentation Baseline
**Status:** CUSTOMER_DEMO_READY

---

## Baseline metadata

| Field | Value |
|---|---|
| Project | Origlyph AI |
| Demo baseline commit | `7fc11129ca63d09d0054ceb8afe241ea894ca93a` |
| Version | 0.4.0a7 |
| Release line | v0.4.0-alpha.7 |
| Demo status | CUSTOMER_DEMO_READY |
| Validation stage | 18C — Manual GUI Launch Validation |
| Validation result | PASS (all GUI validation items confirmed) |

This baseline is the authoritative record of the approved customer-demo state.
No demo should be delivered from an uncommitted or unvalidated revision.

---

## Approved demo launcher paths

**Primary (presenter use):**

```
scripts\run_tolerance_demo.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```

**Secondary (double-click):**

```
scripts\run_tolerance_demo.cmd
```

No other launcher path is approved for customer use.

---

## Approved demo entry point

```
examples/tolerance_workspace_demo.py
```

The demo dataset is defined exclusively in this file.
Do not substitute, patch, or override it for customer presentations.

---

## Approved demo flow

The following 16-step sequence is the golden customer-demo workflow.
Deliver steps in this order. Do not skip or reorder.

| Step | Action |
|---|---|
| 1 | Launch demo via approved launcher |
| 2 | Show tolerance chain (3 contributors) |
| 3 | Show contributor details (nominal, tolerance, direction) |
| 4 | Run Worst Case analysis |
| 5 | Run RSS Statistical analysis |
| 6 | Show Specification limits |
| 7 | Evaluate Decision (both modes) |
| 8 | Run Sensitivity analysis |
| 9 | Run Budget inspection |
| 10 | Show Allocation Plan |
| 11 | Apply Allocation Plan |
| 12 | Validate Allocation |
| 13 | Save Project |
| 14 | Open Project |
| 15 | Confirm state restoration |
| 16 | Close cleanly |

---

## Expected demo results

These values are produced deterministically by the approved demo dataset.
They do not change between runs. Any deviation indicates an environment problem.

**Demo dataset:** bracket-mounting-assembly

| Contributor | Nominal | Tolerance | Direction |
|---|---|---|---|
| bracket_depth | 25.0 | ±0.10 | forward |
| pin_length | 5.0 | ±0.08 | forward |
| shim_thickness | 2.5 | ±0.05 | inverse |

**Specification:**

| Limit | Value |
|---|---|
| Allowed worst-case span | 0.40 |
| Allowed combined sigma | 0.15 |

**Worst-case analysis:**

| Result | Value |
|---|---|
| Total span | 0.46 |
| Decision | FAIL (0.46 > 0.40) |

This FAIL is intentional. It reflects a real engineering situation where the
current tolerances exceed the worst-case specification.

**RSS statistical analysis:**

| Result | Value |
|---|---|
| Combined sigma | ≈ 0.1375 |
| Decision | PASS (0.1375 < 0.15) |

**Sensitivity (worst-case):**

| Rank | Contributor | Span | Share |
|---|---|---|---|
| 1 | bracket_depth | 0.20 | 43.5% |
| 2 | pin_length | 0.16 | 34.8% |
| 3 | shim_thickness | 0.10 | 21.7% |

**Budget (worst-case):**

| Result | Value |
|---|---|
| Status | over_budget |
| Actual span | 0.46 |
| Allowed span | 0.40 |

**Allocation plan:**

| Contributor | Allocated span |
|---|---|
| bracket_depth | 0.12 |
| pin_length | 0.10 |
| shim_thickness | 0.08 |
| **Budget** | **0.30** |

**Allocation validation:**

| Result | Value |
|---|---|
| Status | FULLY ALLOCATED |
| Remaining unallocated | 0 |

**Configuration fingerprint (demo dataset, deterministic):**

```
6b95f5e9299d20e5fd48d018c423cc94295decb658953a95b121ad53b56777fb
```

---

## Demo narrative

Origlyph AI demonstrates a deterministic, traceable tolerance-engineering
workflow. The current customer demo covers:

```
Tolerance Chain
  → Analysis
  → Specification
  → Decision
  → Sensitivity
  → Budget
  → Allocation Plan
  → Allocation Validation
  → Save / Open Traceability
```

Every result is computed by a deterministic engineering engine.
Nothing is inferred, estimated, or AI-generated behind the scenes.
The same inputs always produce the same outputs.

---

## Approved claims

Presenters may assert the following, as they are fully implemented
and demonstrated in this baseline:

- Deterministic tolerance analysis
- Worst-case analysis
- RSS / statistical analysis
- Explicit specification handling
- Deterministic decision surface
- Sensitivity analysis (worst-case, per-contributor ranking)
- Tolerance budget analysis
- Allocation plan input
- Allocation validation (structural consistency)
- Deterministic project persistence (save / open)
- Project identity and reproducibility (configuration fingerprint)
- Fail-closed validation (blank / invalid input raises explicit error)
- Save / open state restoration

---

## Prohibited demo claims

Presenters MUST NOT claim the following features unless they have been
implemented and validated in a future stage:

- Automatic allocation optimisation
- Automatic tolerance optimisation
- AI-generated engineering decisions
- Fully autonomous engineering
- Reconciliation UI
- Audit / governance UI
- Full STEP / B-Rep production workflow
- Full CAD workstation
- Full GD&T authoring
- CAD-to-tolerance automatic binding

---

## Known limitations

These are planned scope, not defects.

| Area | Current state |
|---|---|
| Allocation optimisation | Not implemented — manual entry only |
| Correlated RSS (covariance) | Engine implemented; not yet exposed in workspace UI |
| Reconciliation UI | Engine implemented; workspace UI is future work |
| Audit / governance UI | Engine implemented; workspace UI is future work |
| STEP / B-Rep workflow | Not implemented |
| Full GD&T authoring | Not implemented |
| Company standards library | Not implemented |
| Some Stage 15 capabilities | Backend only; no workspace UI surface yet |
| Demo dataset | Deterministic example dataset only; not a full workstation |

---

## Demo freeze policy

Once Stage 18D is committed, the following policy applies:

1. Customer demos must use the frozen baseline (commit `7fc1112`) until
   a later baseline is explicitly validated.
2. A new baseline requires a Stage 18C-style manual GUI validation pass.
3. A new `golden_demo_baseline.md` must supersede this file explicitly.
4. No ad-hoc feature changes may be introduced before a customer demo
   without repeating the full validation cycle.

---

## Presenter pre-flight

Before any customer session, a presenter must:

1. Run the readiness script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\check_demo_readiness.ps1
   ```
2. Confirm output reads `DEMO_READINESS: PASS`.
3. If FAIL: resolve each listed reason before proceeding.
4. Launch the demo:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
   ```
5. Follow the step-by-step runbook:
   `docs/demo/customer_demo_runbook.md`
6. Keep the cheat sheet visible during the session:
   `docs/demo/customer_demo_cheat_sheet.md`

---

## Demo reset

To restart the demo from a clean state at any point:

1. Close the demo window (or press Ctrl+C in the terminal).
2. Re-run the launcher: `scripts\run_tolerance_demo.ps1`
3. The dataset reloads deterministically.

This reset does **not** modify repository files, change git state, delete
saved project files, or mutate the Python environment.

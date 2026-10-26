# Origlyph AI — Customer Demo Runbook

**Product:** Origlyph AI Tolerance Workspace
**Version:** v0.4.0-alpha.7
**Target duration:** 10–15 minutes
**Stage:** 18B — Demo Runbook + Launcher + Presenter Package

---

## A. Pre-demo checklist

Run this checklist before any customer session.

- [ ] On branch `main`, commit `014aec8` (or later)
- [ ] Version reads `0.4.0a7`:
  `py -c "import origlyph; print(origlyph.__version__)"`
- [ ] Demo entry point exists:
  `examples\tolerance_workspace_demo.py`
- [ ] Launcher available:
  `scripts\run_tolerance_demo.ps1`
- [ ] Python 3.10+ available: `py --version`
- [ ] `origlyph` importable: `py -c "import origlyph"`
- [ ] Headless smoke test passes:
  `py examples\tolerance_workspace_demo.py --headless`
- [ ] Know where you will save the demo project file (e.g. Desktop)
- [ ] Screen resolution visible to audience — window opens at 960 × 800
- [ ] No unrelated terminal windows, IDE, or code visible
- [ ] Presentation display zoom set so text is readable from audience distance
- [ ] Optional: take a screenshot of the expected output for fallback reference

---

## B. Demo launch

Open a PowerShell terminal in the repository root and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```

Or double-click `scripts\run_tolerance_demo.cmd`.

The launcher will:
1. Print the startup banner
2. Verify Python and the origlyph package
3. Open the Origlyph Tolerance Workspace window

The window opens with the bracket-mounting-assembly demo project
pre-loaded: three contributors, specification limits, and allocation
plan already set.

---

## C. Opening narrative

> "What you are looking at is Origlyph AI's tolerance workspace —
> a deterministic engineering environment where every analysis step
> is explicit, traceable, and reproducible.
>
> Today's demo traces a bracket-mounting assembly through the full
> tolerance workflow: from defining the chain, through analysis,
> decision, sensitivity, budget, and allocation plan — and finally
> saving the complete project state.
>
> Every number you see was computed by a deterministic engineering
> engine. Nothing is inferred, estimated, or AI-generated behind
> the scenes."

---

## D. Step-by-step live flow

---

### Step 1 — Launch

**ACTION:** Run the launcher. Point to the opened window.

**WHAT TO SAY:**
> "The workspace opens with a pre-seeded demo project. The title bar
> shows Origlyph · Tolerance Workspace. The chain, specification, and
> allocation plan are already loaded — we can walk through the full
> flow immediately."

**EXPECTED RESULT:** Window at 960 × 800, title
`Origlyph  ·  Tolerance Workspace`.

**WHAT TO HIGHLIGHT:** The 10 labelled sections visible by scrolling.

---

### Step 2 — Project context

**ACTION:** Point to the **Project context** section at the top.

**WHAT TO SAY:**
> "The chain name is `bracket-mounting-assembly` and the mode is
> `worst_case`. Every analysis action uses the mode shown here.
> We can switch to RSS statistical at any time."

**EXPECTED RESULT:** Chain = `bracket-mounting-assembly`,
Mode = `worst_case`.

**WHAT TO HIGHLIGHT:** The mode dropdown — it drives which engine runs.

---

### Step 3 — Tolerance chain editor

**ACTION:** Point to the **Tolerance chain editor** treeview.

**WHAT TO SAY:**
> "The chain has three contributors: Bracket depth, Pin length, and
> Shim thickness. Each has an explicit nominal, tolerance (half-span),
> and stack direction. Forward contributors add to the stack;
> the inverse shim subtracts. Nothing is inferred from geometry —
> the engineer controls every entry."

**EXPECTED RESULT:** Three rows visible.

| Id | Name | Nominal | Tolerance | Direction |
|---|---|---|---|---|
| bracket_depth | Bracket depth | 25.0 | 0.1 | forward |
| pin_length | Pin length | 5.0 | 0.08 | forward |
| shim_thickness | Shim thickness | 2.5 | 0.05 | inverse |

**WHAT TO HIGHLIGHT:** The direction column — inverse contributor
reduces the stack, which is a common physical scenario (compensating
shim or gap element).

---

### Step 4 — Specification limits

**ACTION:** Point to the **Specification limits** section.

**WHAT TO SAY:**
> "The specification sets the engineering requirement. Allowed WC span
> is 0.4 — that is the maximum acceptable worst-case total span from
> the design requirement. Allowed combined sigma is 0.15 for RSS.
> These come from the design requirement, not from the analysis —
> the system never auto-sets a limit."

**EXPECTED RESULT:** Allowed WC Span = `0.4`, Allowed σ = `0.15`.

**WHAT TO HIGHLIGHT:** The `(leave blank = unspecified)` hint —
limits are optional; a blank field means no spec exists for that mode.

---

### Step 5 — Run worst-case analysis

**ACTION:** Click **Run Analysis** (mode = `worst_case`).

**WHAT TO SAY:**
> "The worst-case analysis computes the arithmetic sum of all
> contributor spans. It is the most conservative approach —
> it assumes every part sits at its worst possible dimension
> simultaneously."

**EXPECTED RESULT:**
```
Worst Case  —  total span: 0.46
```

**WHAT TO HIGHLIGHT:** Total span 0.46. The specification allows 0.40.
This will FAIL — that is intentional; the demo shows a real engineering
situation, not a pre-cooked pass.

---

### Step 6 — Evaluate decision (worst-case)

**ACTION:** Click **Evaluate Decision**.

**WHAT TO SAY:**
> "The decision engine compares the 0.46 span against the 0.40 limit.
> The result is FAIL. The margin is negative — the current tolerances
> exceed the engineering requirement in worst-case mode.
> This is a deterministic outcome, not a risk estimate."

**EXPECTED RESULT:** Decision = **FAIL**.

**WHAT TO HIGHLIGHT:** The status label and the margin detail.
Point out that the decision is explicit and traceable — not a
probability or recommendation.

---

### Step 7 — Switch to RSS and re-run

**ACTION:** Change **Mode** to `rss_statistical` in Project context.
Click **Run Analysis**.

**WHAT TO SAY:**
> "RSS statistical combines variances quadratically rather than
> arithmetically. For independent contributors, this is statistically
> sound and gives a more realistic picture of the likely variation.
> The combined sigma is approximately 0.137."

**EXPECTED RESULT:**
```
RSS Statistical  —  combined sigma: 0.137
```

**WHAT TO HIGHLIGHT:** Combined sigma = 0.137 is significantly
smaller than the worst-case 0.46.

---

### Step 8 — Evaluate decision (RSS)

**ACTION:** Click **Evaluate Decision** (still in RSS mode).

**WHAT TO SAY:**
> "In RSS statistical mode, the decision compares combined sigma
> 0.137 against the specified 0.15 limit. The result is PASS —
> the assembly is statistically capable even though it fails
> worst-case. This contrast is the key engineering insight:
> worst-case tells you the theoretical maximum exposure;
> RSS tells you the expected statistical performance."

**EXPECTED RESULT:** Decision = **PASS**.

**WHAT TO HIGHLIGHT:** The contrast with the worst-case FAIL.
The same chain, different analysis mode, different outcome —
and both results are correct and traceable.

---

### Step 9 — Sensitivity inspection

**ACTION:** Switch back to **Mode = `worst_case`**. Click **Run Analysis**.
Click **Run Sensitivity**.

**WHAT TO SAY:**
> "Sensitivity tells us how much each contributor influences the
> total span. Bracket depth dominates at 43.5%, followed by Pin
> length at 34.8%, and Shim thickness at 21.7%.
> If we need to reduce the worst-case span, bracket depth is
> where re-design effort pays off most."

**EXPECTED RESULT:**

| Rank | Contributor | Impact | Share |
|---|---|---|---|
| 1 | bracket_depth | 0.20 | 43.5% |
| 2 | pin_length | 0.16 | 34.8% |
| 3 | shim_thickness | 0.10 | 21.7% |

**WHAT TO HIGHLIGHT:** The rank ordering — design engineers can
prioritise tolerance tightening based on quantified impact.

---

### Step 10 — Budget inspection

**ACTION:** Click **Run Budget** (still in worst-case mode).

**WHAT TO SAY:**
> "Budget inspection compares each contributor's actual span against
> the allowed span. Status is over-budget — the assembly uses 0.46
> of the 0.40 allowed. This is a read-only view; it does not change
> the tolerances. It quantifies the gap between current state and
> the engineering requirement."

**EXPECTED RESULT:**
- Status: `over_budget`
- Actual span: 0.46, Allowed span: 0.40

**WHAT TO HIGHLIGHT:** The per-contributor breakdown showing how much
budget each contributor consumes.

---

### Step 11 — Allocation plan

**ACTION:** Scroll down to **Allocation Plan**. The plan is pre-loaded.

**WHAT TO SAY:**
> "The allocation plan is a target tolerance budget — what the
> tolerance should become after design optimisation. Each contributor
> gets an allocated span. The budget here is 0.30 — tighter than
> the allowed 0.40 — to give margin. The sum of allocated spans
> equals exactly the budget."

**EXPECTED RESULT:**

| Contributor | Allocated Span |
|---|---|
| bracket_depth | 0.12 |
| pin_length | 0.10 |
| shim_thickness | 0.08 |

Budget = 0.30; sum = 0.30.

**WHAT TO HIGHLIGHT:** Show editing a span — click `bracket_depth`
in the treeview, change **Allocated Span for Selected** to `0.14`,
click **Set Span** (row updates), then restore to `0.12`.
This demonstrates the explicit entry workflow.

---

### Step 12 — Apply Allocation Plan

**ACTION:** Click **Apply Allocation Plan**.

**WHAT TO SAY:**
> "Apply Allocation Plan is an explicit action — it writes the plan
> into the authoritative workspace state. Nothing is applied
> automatically. After applying, the configuration fingerprint
> rotates, marking this as a new identifiable project state."

**EXPECTED RESULT:** No error message. The Allocation Plan treeview
remains populated.

**WHAT TO HIGHLIGHT:** The explicit action model — the plan is a
target, not an automatic update to tolerances.

---

### Step 13 — Validate Allocation

**ACTION:** Click **Validate Allocation**.

**WHAT TO SAY:**
> "Validation checks that the allocated spans are consistent with
> the budget and the contributor set. The result is PASS —
> sum of allocated spans equals the allowed budget of 0.30.
> Remaining unallocated is zero. This is a deterministic structural
> check, not a statistical simulation."

**EXPECTED RESULT:**
- Status: **PASS / FULLY ALLOCATED**
- Remaining unallocated: 0

**WHAT TO HIGHLIGHT:** Validate Allocation is independent of
Run Analysis. Changing the analysis does not retrigger validation.
This isolation is intentional — each action is explicit.

---

### Step 14 — Save Project

**ACTION:** Scroll to **Project File** section. Click **Save Project**.
Choose a save location (e.g. Desktop). Save.

**WHAT TO SAY:**
> "The full workspace state — chain, specification, allocation plan —
> is saved in a single project file. The result evidence is not
> stored because it is runtime-derived and can always be recomputed
> deterministically from the same inputs."

**EXPECTED RESULT:** File dialog opens, file saves without error.

**WHAT TO HIGHLIGHT:** The `.origlyph.json` extension — structured,
human-readable project format.

---

### Step 15 — Reopen Project

**ACTION:** Click **Open Project**. Select the file just saved.

**WHAT TO SAY:**
> "On reopen, the chain, specification, and allocation plan are
> restored exactly. The configuration fingerprint is stable —
> this is the same project state. Re-running any analysis from
> the same inputs produces the same results."

**EXPECTED RESULT:** Chain, specification, and allocation plan
restored identically. Results section shows `No result` — waiting
for an explicit Run Analysis action.

**WHAT TO HIGHLIGHT:** The explicit re-run model. Saved state is
authoritative; results are computed on demand — not cached in the file.

---

## E. Key talking points

**Deterministic engineering core**
Every analysis, decision, sensitivity, budget, and allocation
validation uses a fixed deterministic algorithm. The same inputs
always produce the same outputs. There is no stochastic element,
no sampling, and no hidden inference.

**Explicit engineering inputs**
Every tolerance value, specification limit, and allocation span
is entered by the engineer. No value is inferred from geometry,
automatically set from a default, or generated by AI.

**Traceability**
Each workspace state has a configuration fingerprint (SHA-256).
Analysis results carry a result ID. The fingerprint rotates when
any authoritative input changes — the project identity tracks
every meaningful state change.

**Fail-closed validation**
Blank or invalid inputs raise an explicit error. There are no
silent defaults, no fallback to zero, and no automatic substitution.
The system fails loudly rather than silently producing incorrect results.

**Separation of authoritative state vs derived results**
The chain, specification, and allocation plan are authoritative and
persisted. Analysis results, decision, sensitivity, budget, and
allocation validation are runtime-derived. They are not stored —
they are recomputed from authoritative inputs.

**Sensitivity visibility**
Sensitivity analysis quantifies each contributor's fractional impact
on the total span. This directs design effort to the highest-leverage
contributors.

**Budget visibility**
Budget inspection shows how current tolerances utilise the allowed
span budget. It does not modify tolerances — it measures them.

**Allocation-plan validation**
The allocation plan is a target tolerance distribution. Validation
checks structural consistency: correct contributors, non-negative
spans, sum within budget. It does not automatically redesign the
component or retighten tolerances.

**Deterministic persistence**
The project file captures the full engineering intent. Reopening a
saved project restores authoritative state exactly. Results can be
reproduced by re-running the same analysis on the same inputs.

**Engineering authority separated from UI**
The Stage 15 engineering engines (worst-case, statistical, sensitivity,
budget, allocation validation) are architecturally separated from the
workspace UI. The UI orchestrates explicit actions; the engines perform
all calculations. No engineering formula exists in the UI layer.

---

## F. Expected outputs (deterministic reference)

These values are produced by the demo dataset every time.

**Demo dataset:** bracket-mounting-assembly
- bracket_depth: nominal 25.0, tolerance ±0.10, forward
- pin_length: nominal 5.0, tolerance ±0.08, forward
- shim_thickness: nominal 2.5, tolerance ±0.05, inverse

**Specification:**
- Allowed WC span: 0.40
- Allowed combined sigma: 0.15

**Worst-case analysis:**
- Total span: 0.46 (= 0.20 + 0.16 + 0.10)
- Decision: **FAIL** (0.46 > 0.40)

**RSS statistical analysis:**
- Combined sigma: ≈ 0.1375
- Decision: **PASS** (0.1375 < 0.15)

**Sensitivity (worst-case):**
- bracket_depth: span 0.20, share 43.5%
- pin_length: span 0.16, share 34.8%
- shim_thickness: span 0.10, share 21.7%

**Budget (worst-case):**
- Status: over_budget
- Actual: 0.46 / Allowed: 0.40

**Allocation plan:**
- Budget: 0.30
- bracket_depth: 0.12, pin_length: 0.10, shim_thickness: 0.08
- Sum: 0.30

**Allocation validation:**
- Status: FULLY ALLOCATED (PASS)
- Remaining unallocated: 0

**Configuration fingerprint (demo dataset):**
`6b95f5e9299d20e5fd48d018c423cc94295decb658953a95b121ad53b56777fb`

---

## G. Common customer questions

**Is this calculation deterministic?**
Yes. Every result is computed from explicit inputs using fixed
mathematical rules. The same inputs always produce the same outputs.
There is no sampling, estimation, or probabilistic element in the
worst-case or RSS engines.

**Does AI change the engineering results?**
No. The AI boundary in Origlyph is advisory only. No AI component
modifies, overrides, or substitutes a deterministic engineering result.
The engines used in this demo are purely deterministic.

**Can projects be saved and reopened?**
Yes. The project file (workspace v3 schema) persists the chain,
specification, and allocation plan. Analysis results are runtime-derived
and recomputed from saved inputs on demand.

**Does changing a tolerance affect the project identity?**
Yes. The configuration fingerprint (SHA-256) rotates whenever any
authoritative input changes — contributor, specification, or allocation
plan. This makes every meaningful project state uniquely identifiable.

**Can allocation be automatically optimised?**
Not in this release. The allocation plan must be constructed manually
by the engineer. Automatic balance, optimal-span calculation, and
constraint-based generation are future work.

**Does the system support correlated RSS?**
The Stage 15 covariance-aware statistical engine is implemented and
supports correlated contributors. The workspace demo uses the standard
RSS (independent) mode. Covariance input is not yet exposed in the
workspace UI.

**Does it support CAD or STEP import?**
This release supports ASCII and binary STL import only.
STEP, IGES, DXF, and B-Rep topology are not yet implemented.

**Does it support full GD&T evaluation?**
A GD&T assistance module boundary exists in the architecture.
Full GD&T compliance evaluation, automatic standards interpretation,
and automatic GD&T assignment are not yet implemented.

**Can company tolerance standards be integrated?**
Not in this alpha. Standard library integration, standards-bound
limits, and enterprise authorization are future work.

**Can this be expanded to audit and governance workflows?**
Yes. The Stage 15 audit chain (decision evidence, decision report,
audit package, change impact, approval readiness, governed acceptance)
is fully implemented in the engineering layer. The workspace UI surface
for audit and governance is planned as future work.

---

## H. Recovery / fallback

### H-A. Wrong input entered

**Symptom:** A field contains an incorrect value (wrong nominal,
wrong tolerance).

**Recovery:**
1. Click the row in the treeview to select the contributor.
2. Edit the fields in the tolerance chain editor.
3. Click **Update Contributor** to apply.
4. Click **Run Analysis** again to recompute.

**Do NOT:** Delete and re-add the contributor unless necessary —
the identifier links to the allocation plan.

---

### H-B. Validation error shown

**Symptom:** An error dialog appears (e.g. "enter a valid number").

**Recovery:**
1. Read the message — it names the specific field and expected format.
2. Clear the field and enter a valid value (e.g. `0.12` not `0,12`).
3. Retry the action.

**Do NOT:** Dismiss the error and continue — the action did not
complete. Correct the input first.

---

### H-C. Result not available / "No result"

**Symptom:** Results section shows `No result`.

**Recovery:**
1. Click **Run Analysis**.
2. If analysis requires sensitivity/budget: Run Analysis first,
   then Run Sensitivity or Run Budget.

**Context:** Results reset when the chain or mode changes.
This is intentional — stale results are not shown.

---

### H-D. Project save path issue

**Symptom:** File dialog fails or the wrong path is selected.

**Recovery:**
1. Click **Save Project** again.
2. Navigate to a known writable location (e.g. Desktop).
3. Enter a filename without special characters.

**Do NOT:** Save into the repository directory — use the Desktop
or a known scratch location for demo files.

---

### H-E. Demo window too small

**Symptom:** Sections are clipped, text is unreadable.

**Recovery:**
1. Resize the window manually — minimum usable size is 820 × 640.
2. Use the scroll bar on the right to navigate sections.
3. If screen resolution is too low, zoom out in display settings
   before relaunching.

**Do NOT:** Reduce font size in system settings during the demo.

---

### H-F. Demo accidentally closed

**Symptom:** The workspace window disappears.

**Recovery:**
Re-run the launcher:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
```
or double-click `scripts\run_tolerance_demo.cmd`.

The demo dataset reloads from scratch deterministically.
Any unsaved project state is lost — restart the demo flow from Step 1.

**Do NOT:** Try to recover state from a terminal that is no longer
running the demo process.

---

### H-G. Environment / import failure

**Symptom:** Launcher prints `ERROR: origlyph package not importable.`

**Recovery:**
1. Open a new terminal in the repository root.
2. Run: `py -m pip install -e ".[dev]"`
3. Relaunch the demo.

If `py` is not found: install Python 3.10+ from python.org and
ensure the Windows launcher is on PATH.

---

## I. Quick reset

To restart the demo from a clean state:

1. Close the demo window (or press Ctrl+C in the launcher terminal).
2. Re-run the launcher:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
   ```
3. The demo dataset reloads deterministically.
4. Begin again from Step 1.

**This process is safe.** It does not:
- modify repository files
- change git state
- delete any saved project files
- mutate the Python environment

---

## Closing message

> "What you have seen is a deterministic tolerance engineering
> workflow — from chain definition through analysis, decision,
> sensitivity, budget, and allocation plan validation, to a saved
> project file that can be reopened and reproduced exactly.
>
> Every result is traceable to explicit inputs. Every action
> is engineering-authoritative, not AI-generated. And the
> foundation is designed to extend to audit, governance, and
> multi-dimensional tolerance analysis as the platform matures.
>
> This is Origlyph AI."

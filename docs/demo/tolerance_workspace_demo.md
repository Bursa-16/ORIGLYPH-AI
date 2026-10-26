# Tolerance Workspace â€” Customer Demo Script

**Version:** v0.4.0-alpha.7
**Demo file:** `examples/tolerance_workspace_demo.py`
**Estimated time:** 8â€“12 minutes

---

## Overview

This script walks through the full tolerance workspace feature set using a
three-contributor bracket-mounting assembly scenario. The demo covers:

1. Project setup and chain definition
2. Specification entry
3. Worst-case and RSS analysis
4. Decision evaluation (PASS/FAIL)
5. Sensitivity inspection
6. Budget inspection
7. Allocation plan creation and validation
8. Project save and reload

---

## Pre-demo: Launch the workspace

```
py examples/tolerance_workspace_demo.py
```

The window opens with the three-contributor chain and specification
pre-loaded. The title bar reads **Origlyph Â· Tolerance Workspace**.

---

## Step-by-step demo script

### Step 1 â€” Project context

Point to the **Project context** section at the top:

- **Chain:** `bracket-mounting-assembly`
- **Mode:** `worst_case`

*"The chain name and analysis mode appear here. The mode controls which
engine runs when you press Run Analysis."*

---

### Step 2 â€” Specification limits

Point to the **Specification limits** section:

- **Allowed WC Span:** `0.4`
- **Allowed Ïƒ:** `0.15`

*"These limits come from the engineering requirement. When a result is
available, Evaluate Decision compares the actual stack span against the
allowed WC span for worst-case mode, or the combined sigma against the
allowed sigma for RSS mode."*

---

### Step 3 â€” Tolerance chain editor

Point to the **Tolerance chain editor** treeview with the three contributors:

| Id | Name | Nominal | Tolerance | Direction |
|---|---|---|---|---|
| bracket_depth | Bracket depth | 25.0 | 0.10 | forward |
| pin_length | Pin length | 5.0 | 0.08 | forward |
| shim_thickness | Shim thickness | 2.5 | 0.05 | inverse |

*"Each contributor has a stable id, a display name, a nominal dimension,
a tolerance (half-span), and a stack direction. Nothing is inferred â€”
every value is entered explicitly."*

---

### Step 4 â€” Run worst-case analysis

Click **Run Analysis** (mode = `worst_case`).

The **Results** section shows:
```
Worst Case  â€”  total span: 0.46
```

*(Wait for audience to read the result.)*

*"The worst-case total span is 0.46 â€” the arithmetic sum of all
contributor spans (0.20 + 0.16 + 0.10)."*

> Note: span = 2 Ã— tolerance. Each contributor's span is double its
> tolerance value.

---

### Step 5 â€” Evaluate decision (worst-case)

Click **Evaluate Decision**.

The **Decision** section shows the PASS/FAIL status and the margin line.

*"The decision compares 0.46 against the specification limit of 0.40.
The result is FAIL â€” the actual span exceeds the allowed span."*

---

### Step 6 â€” Switch to RSS and re-run

Change **Mode** to `rss_statistical` in the Project context section.

Click **Run Analysis**.

The **Results** section shows:
```
RSS Statistical  â€”  combined sigma: <value>
```

Click **Evaluate Decision** again.

*"RSS statistical combines contributor variances quadratically, giving
a significantly smaller combined sigma. In most practical stacks, RSS
shows headroom that worst-case analysis obscures."*

---

### Step 7 â€” Sensitivity inspection

Switch back to **Mode = `worst_case`**, click **Run Analysis**.

Click **Run Sensitivity**.

The **Sensitivity** treeview shows each contributor ranked by impact:

| Rank | Contributor | Impact | Share % |
|---|---|---|---|
| 1 | Bracket depth | 0.20 | 43.5 % |
| 2 | Pin length | 0.16 | 34.8 % |
| 3 | Shim thickness | 0.10 | 21.7 % |

*"Sensitivity tells us where to focus re-design effort. Bracket depth
dominates â€” tightening it yields the most headroom per unit of change."*

---

### Step 8 â€” Budget inspection

Click **Run Budget**.

The **Budget** section shows overall status and per-contributor utilisation.

*"Budget inspection compares each contributor's actual span against the
total allowed span, showing how much of the budget each contributor
consumes. This is read-only â€” it reflects the current tolerances."*

---

### Step 9 â€” Allocation plan

Scroll down to the **Allocation Plan** section. The treeview is already
populated from the pre-loaded plan:

| Contributor | Current Span | Allocated Span |
|---|---|---|
| bracket_depth | 0.20 | 0.12 |
| pin_length | 0.16 | 0.10 |
| shim_thickness | 0.10 | 0.08 |

**Allocation Budget:** `0.3`

*"The allocation plan is the target tolerance budget. Each contributor
gets an allocated span â€” what it should achieve after design optimisation.
Budget = 0.30, which is tighter than the current 0.46."*

Show how to edit a span:

1. Click a row in the treeview (e.g. `bracket_depth`).
2. Type `0.14` in the **Allocated Span for Selected** field.
3. Click **Set Span** â€” the treeview row updates immediately.
4. Restore `0.12` and click **Set Span** again.

Click **Apply Allocation Plan** to write the plan to the workspace.

---

### Step 10 â€” Validate allocation

Click **Validate Allocation**.

The **Allocation Validation Result** section shows:

- **Status:** PASS (sum of allocated spans â‰¤ allowed budget)
- A per-contributor treeview: Allocated / Current Span / Delta / % of Budget

*"Validation is explicit and fail-closed. It checks that allocated spans
are consistent with the budget and the contributor set. It does NOT
automatically recompute the tolerance analysis â€” that remains a separate
explicit action."*

---

### Step 11 â€” Save and reload

Click **Save Project**. Choose a location and save.

Click **Open Project**. Select the file you just saved.

Verify the chain, spec, and allocation plan are restored exactly.

*"The workspace persists in schema v3. Specification and allocation plan
round-trip faithfully. Result evidence is runtime-derived and not stored."*

---

### Step 12 â€” Key messages (closing)

Summarise:

- **Deterministic** â€” every result is derived from explicit inputs, no
  hidden inference.
- **Fail-closed** â€” blank or invalid inputs are rejected loudly; no
  silent defaults.
- **Feature-isolated** â€” analysis, decision, sensitivity, budget, and
  allocation validation are independent explicit actions.
- **Traceable** â€” the configuration fingerprint rotates on any state
  change; results carry their own result_id.
- **Extensible** â€” engineering engines (Stage 15) are separate from the
  workspace UI; all math lives in the engine layer.

---

## Headless verification

Run without a display to verify all stages pass deterministically:

```
py examples/tolerance_workspace_demo.py --headless
```

Expected output sections: Specification, Contributors, Worst Case,
RSS Statistical, Sensitivity, Budget, Allocation validation, fingerprint.

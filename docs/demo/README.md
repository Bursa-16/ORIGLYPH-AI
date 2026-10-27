# Origlyph AI — Demo Package Index

**Version:** v0.4.0-alpha.7
**Golden baseline commit:** `b68ab0e664805ef8c8c94a667c80b08706d13a30`
**Demo status:** CUSTOMER_DEMO_READY

This directory contains the complete customer demo delivery kit.

---

## Before every demo

Run the readiness check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_demo_readiness.ps1
```

Required: `DEMO_READINESS: PASS`

---

## Package Contents

### Technical / Internal

| File | Description |
|---|---|
| `golden_demo_baseline.md` | Authoritative frozen demo baseline — commit, version, approved workflow, expected values, freeze policy |
| `demo_baseline_manifest.json` | Machine-readable baseline metadata — commit SHA, version, launcher paths, validation stage |
| `tolerance_workspace_demo.md` | Technical documentation of the tolerance workspace demo |

### Presenter-Only

| File | Description |
|---|---|
| `customer_demo_delivery_checklist.md` | Operational checklist — 24h before, 1h before, 10min before, during, after |
| `customer_demo_runbook.md` | Step-by-step demo runbook with full talking points — 10–15 min flow |
| `customer_demo_cheat_sheet.md` | One-page quick reference — demo flow, expected values, key differentiators |
| `customer_demo_5min_script.md` | 5-minute executive demo script — compressed golden workflow |
| `customer_demo_15min_script.md` | 15-minute full demo script — complete golden workflow with timing |
| `customer_demo_positioning.md` | What to say confidently / with qualification / not at all — avoids overclaiming |
| `customer_demo_faq.md` | 16 common customer questions with concise factual answers |
| `customer_demo_fallback.md` | Recovery guide for 6 failure scenarios — launcher fail, GUI fail, time cut, etc. |
| `customer_discovery_questions.md` | 30 discovery questions grouped by topic — use during/after demo |

### Customer-Facing

| File | Description |
|---|---|
| `origlyph_customer_one_pager.md` | One-page product overview — capabilities, use cases, honest scope statement |
| `customer_demo_followup_email.md` | Follow-up email template — send within 24 hours of demo |
| `customer_pilot_outline.md` | Pilot evaluation framework — objective, scope, workflow, success criteria |

### Launchers

| Path | Description |
|---|---|
| `scripts/run_tolerance_demo.ps1` | **Primary launcher** — run before every demo |
| `scripts/run_tolerance_demo.cmd` | Secondary launcher — Windows double-click |
| `scripts/check_demo_readiness.ps1` | Pre-demo readiness check — must return PASS |

### Demo Entry Point

| Path | Description |
|---|---|
| `examples/tolerance_workspace_demo.py` | Approved demo dataset and launch entry point — do not modify |

---

## Approved Demo Flow (golden workflow)

```
1.  Launch via scripts\run_tolerance_demo.ps1
2.  Show tolerance chain (3 contributors)
3.  Show contributor details
4.  Run Worst Case analysis       → span 0.46
5.  Run RSS Statistical analysis  → sigma ≈ 0.137
6.  Show Specification limits     → WC 0.40 / sigma 0.15
7.  Evaluate Decision             → WC FAIL / RSS PASS
8.  Run Sensitivity               → bracket_depth 43.5% rank 1
9.  Run Budget                    → over_budget
10. Show Allocation Plan          → budget 0.30
11. Apply Allocation Plan
12. Validate Allocation           → FULLY ALLOCATED
13. Save Project
14. Open Project
15. Confirm state restoration
16. Close cleanly
```

---

## Demo Freeze Policy

This demo package is frozen at commit `b68ab0e664805ef8c8c94a667c80b08706d13a30`.
Customer demos must use this baseline until a later baseline is explicitly validated
by a Stage 18C-style manual GUI validation and a new `golden_demo_baseline.md` supersedes this one.

---

## Quick Links

- Full runbook: `customer_demo_runbook.md`
- Exact expected values: `customer_demo_cheat_sheet.md`
- Readiness check: `scripts/check_demo_readiness.ps1`
- Positioning guide: `customer_demo_positioning.md`
- Fallback plan: `customer_demo_fallback.md`

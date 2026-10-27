# Origlyph AI — Demo Fallback and Recovery Guide

**Purpose:** Handle unexpected situations during a live customer demo
**Version:** v0.4.0-alpha.7

Keep this document accessible during the demo session.

---

## Scenario A — Launcher Fails

**SYMPTOM:** Running `scripts\run_tolerance_demo.ps1` produces an error
(e.g. `ERROR: origlyph package not importable`, `ERROR: Demo entry point not found`,
or a Python traceback).

**ACTION:**
1. Do not panic — stay calm and professional.
2. Read the error message exactly — it names the specific problem.
3. If `origlyph not importable`:
   Open a second terminal and run:
   ```powershell
   py -m pip install -e ".[dev]"
   ```
   Then re-run the launcher.
4. If `py` not found: Python launcher is not on PATH — open a fresh terminal
   as administrator, or use the `python` command directly:
   ```powershell
   python examples/tolerance_workspace_demo.py
   ```
5. If the error persists: move to the headless fallback (see below).

**WHAT TO SAY:**
> "We have a brief environment issue — let me resolve it in a moment.
> While I do that, let me share a quick overview of what we are about to see."
> (Use the one-pager or cheat sheet to fill 60–90 seconds.)

**DO NOT:** Run `git reset`, `git checkout`, or any destructive command.
Do not attempt to reinstall Python or the operating system.

---

## Scenario B — GUI Fails to Open or Crashes

**SYMPTOM:** The launcher completes without error but the window does not appear,
or the window opens and then immediately closes.

**ACTION:**
1. Close any visible window.
2. Run the headless smoke test to confirm the demo logic works:
   ```powershell
   py examples/tolerance_workspace_demo.py --headless
   ```
3. If headless passes: a display or Tkinter issue exists.
   Try relaunching once after closing other applications.
4. If headless fails: a deeper environment problem exists — move to verbal walkthrough.
5. If neither works within 2 minutes: stop the live demo attempt and move to fallback.

**WHAT TO SAY:**
> "The demo environment is not cooperating today. Rather than spending our
> session troubleshooting, let me walk you through the workflow and results
> directly — I have everything here."
> (Use cheat sheet + one-pager to walk through the workflow verbally.)

**DO NOT:** Spend more than 2 minutes attempting to fix a live GUI problem.

---

## Scenario C — Save or Open Fails

**SYMPTOM:** The Save Project or Open Project dialog does not open,
or a file error appears after saving/opening.

**ACTION:**
1. If the dialog fails to open: try clicking the button again once.
2. If saving fails: try a different save path — use the Desktop if the
   current path has permission issues.
3. If opening fails: confirm the file extension is `.json` and the path is valid.
4. If the issue persists: skip the save/open step and explain it verbally.

**WHAT TO SAY:**
> "We have a minor file dialog issue. I will describe the save/open behaviour:
> the workspace saves the full engineering state — chain, specification,
> allocation plan — to a single project file. Reopening it restores the state
> exactly, and re-running the same analysis produces identical results."

**DO NOT:** Attempt to save into the repository directory.
Do not try to open a file from an unknown source.

---

## Scenario D — Meeting Time Is Shortened

**SYMPTOM:** The meeting is cut short — you have 5 minutes instead of 15.

**ACTION:**
1. Switch immediately to the 5-minute script:
   `docs/demo/customer_demo_5min_script.md`
2. Prioritise: Analysis → Decision → Sensitivity → close.
   Skip Budget and Allocation if necessary.
3. Offer to complete the full demo in a follow-up session.

**WHAT TO SAY:**
> "I understand we have limited time. Let me focus on the most important
> parts — the analysis, the decision engine, and the sensitivity view —
> and we can arrange a follow-up for the full workflow."

**DO NOT:** Try to rush through 15 minutes in 5 — compress intelligently.

---

## Scenario E — Customer Asks About an Unsupported Feature

**SYMPTOM:** Customer asks about a capability not in the current release
(e.g. STEP import, automatic optimisation, GD&T evaluation, CAD binding).

**ACTION:**
1. Do not invent or imply capability.
2. Answer directly and honestly.
3. Refer to the positioning guide: `docs/demo/customer_demo_positioning.md`

**WHAT TO SAY:**
> "That is not in the current release. It is identified as future scope,
> and it is something we would want to understand better in the context
> of your specific requirements. Can I note that as a follow-up item?"

**DO NOT:** Say "yes, we can do that" unless you are certain it is in section A
of the positioning guide.

---

## Scenario F — The Live Demo Should Be Stopped

**SYMPTOM:** The demo environment is completely unresponsive, a critical error
appears that cannot be resolved quickly, or the situation clearly warrants stopping
the live demo to preserve the meeting's value.

**ACTION:**
1. Close the demo window and terminal.
2. Do not attempt further fixes.
3. Pivot immediately to verbal walkthrough using:
   - `docs/demo/customer_demo_cheat_sheet.md` (expected values)
   - `docs/demo/origlyph_customer_one_pager.md` (capabilities overview)
4. Offer to schedule a dedicated demo session at a later date.

**WHAT TO SAY:**
> "I want to make the best use of your time, so let me shift to walking you
> through the workflow and capabilities directly. I can show you the exact
> analysis results and what the workspace produces — and we will arrange
> a clean demo session where you can see it live."

**DO NOT:** Run `git reset --hard`, `git clean -f`, or any destructive command.
Do not uninstall or reinstall software during the customer meeting.
Do not apologise excessively — acknowledge it once and move forward.

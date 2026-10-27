# Origlyph AI — Customer Demo Delivery Checklist

**Version:** v0.4.0-alpha.7
**Use before:** every customer demo session

---

## A. 24 Hours Before Meeting

- [ ] Confirm meeting time, duration, and attendees
- [ ] Know the customer company name and primary contact role
- [ ] Know the expected audience (engineering manager, quality, product dev, etc.)
- [ ] Confirm screen-sharing method (Teams, Zoom, in-person projector)
- [ ] Confirm laptop will be used for the demo (not a shared/unfamiliar machine)
- [ ] Ensure laptop is charged and charger is packed
- [ ] Ensure Python 3.10+ and origlyph 0.4.0a7 are installed on the demo machine
- [ ] Run readiness check on the demo machine:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\check_demo_readiness.ps1
  ```
  Required result: `DEMO_READINESS: PASS`
- [ ] Run the demo end-to-end once to confirm all steps work
- [ ] Note a known writable save path (e.g. Desktop\origlyph_demo.json)
- [ ] Print or have open on a second device:
  - `docs/demo/customer_demo_cheat_sheet.md`
  - `docs/demo/customer_demo_runbook.md`
- [ ] Decide which script to use: 5-minute or 15-minute
- [ ] Review the FAQ: `docs/demo/customer_demo_faq.md`
- [ ] Review positioning guide: `docs/demo/customer_demo_positioning.md`
- [ ] Review discovery questions: `docs/demo/customer_discovery_questions.md`
- [ ] Prepare follow-up email draft: `docs/demo/customer_demo_followup_email.md`

---

## B. 1 Hour Before Meeting

- [ ] Run readiness check again on the demo machine:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\check_demo_readiness.ps1
  ```
  Required result: `DEMO_READINESS: PASS`
- [ ] Confirm internet connectivity status (demo does not require internet, but note this)
- [ ] Set display resolution to a level readable from audience distance
- [ ] Close unrelated applications, terminals, IDE windows, and browser tabs
- [ ] Disable notifications (Slack, email, Teams pop-ups)
- [ ] Disable screen lock / sleep during presentation
- [ ] Test screen sharing at the intended resolution — confirm text is readable
- [ ] Launch demo once more and confirm window opens cleanly:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
  ```
- [ ] Close the demo window (it will be reopened live)
- [ ] Have the fallback plan available: `docs/demo/customer_demo_fallback.md`
- [ ] Have the one-pager ready to share: `docs/demo/origlyph_customer_one_pager.md`

---

## C. 10 Minutes Before Meeting

- [ ] Open a clean PowerShell terminal at the repository root
- [ ] Confirm branch is `main` and worktree is clean:
  ```powershell
  git status --short
  ```
  Expected: no output (clean)
- [ ] Cheat sheet is visible (second screen or printed)
- [ ] Runbook is open and ready
- [ ] Save path is confirmed (Desktop or known location)
- [ ] Demo window is NOT open yet — launch it live at the start
- [ ] Any screen-sharing software is connected and tested
- [ ] You know the first line you will say

---

## D. During Meeting

- [ ] Launch demo live in front of the audience:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\run_tolerance_demo.ps1
  ```
- [ ] Follow the runbook or script step-by-step — do not improvise the workflow
- [ ] Use exact expected values from cheat sheet when narrating
- [ ] Do not claim unsupported features — refer to positioning guide
- [ ] If a question is outside current scope: answer honestly ("that is planned future work")
- [ ] Note any customer-specific questions for follow-up
- [ ] Save the demo project to the known save path during the demo
- [ ] Reopen the saved project to demonstrate state restoration
- [ ] Close the demo cleanly at the end (do not leave window open during Q&A)
- [ ] Record key customer questions and pain points for discovery notes

---

## E. Immediately After Meeting

- [ ] Send follow-up email within 24 hours (template: `docs/demo/customer_demo_followup_email.md`)
- [ ] Record any customer-specific requirements, pain points, or questions raised
- [ ] Note any demo issues for future improvement
- [ ] Delete demo project files saved during the session (they are not repository files)
- [ ] If a pilot or next step was discussed, log it and assign an owner

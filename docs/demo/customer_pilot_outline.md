# Origlyph AI — Customer Pilot Outline

**Purpose:** Framework for a structured customer pilot evaluation
**Version:** v0.4.0-alpha.7
**Note:** This is an outline only. No pricing or contractual terms are included.

---

## Objective

Evaluate Origlyph AI against a real customer tolerance engineering case to:

- Confirm that the workflow maps to the customer's actual engineering process
- Identify gaps between current Origlyph capabilities and customer requirements
- Establish a shared baseline for a requirements-driven development conversation
- Demonstrate that deterministic, traceable tolerance analysis is practical
  in the customer's domain

---

## Scope

The pilot covers a defined, bounded assembly or tolerance case provided by the customer.

**In scope:**
- Tolerance chain definition for the selected assembly
- Worst-case and RSS statistical analysis
- Specification evaluation and PASS/FAIL decision
- Sensitivity and budget analysis
- Allocation plan definition and validation
- Project save, open, and state restoration
- Joint review of results against the customer's existing analysis (if available)

**Out of scope for this pilot:**
- CAD geometry import or binding
- GD&T evaluation
- Automatic allocation optimisation
- Report generation
- Integration with PLM, PDM, or ERP systems
- Multi-assembly or multi-chain scope

---

## Customer Inputs

The following are required from the customer to run the pilot:

- Selection of one representative assembly or tolerance case
- Contributor list: identifiers, nominal dimensions, tolerance values, stack directions
- Specification limits (allowed worst-case span and/or allowed sigma)
- Existing analysis results (Excel or other) for comparison, if available
- Contact / engineering lead to participate in the review session

---

## Origlyph Inputs

Origlyph provides:

- Installed and configured Origlyph AI v0.4.0-alpha.7
- Pre-demo readiness check and confirmed launcher
- Facilitation of the pilot session
- Joint review and discussion of the results
- Written summary of findings and identified gaps

---

## Pilot Workflow

1. **Kick-off:** Agree on the assembly, input data format, and session schedule
2. **Data input:** Origlyph team enters the customer's tolerance case into the workspace
3. **Analysis session:** Walk through the full workflow with the customer
   (worst-case, RSS, decision, sensitivity, budget, allocation)
4. **Comparison:** Compare Origlyph results against customer's existing analysis
5. **Gap identification:** Note any workflow requirements not covered by the current release
6. **Review meeting:** Joint debrief — findings, gaps, and next-step discussion

---

## Success Criteria

The pilot is considered successful if:

- The customer's tolerance case can be entered and analysed in the workspace
- Origlyph results match or are explainable relative to the customer's existing analysis
- At least one concrete gap or requirement is identified and documented
- Both parties have a clear picture of fit and next steps

---

## Deliverables

- Saved Origlyph project file for the pilot assembly
- Written summary: what worked, what gaps were identified, what would be needed next
- Documented customer requirements for future development prioritisation

---

## Exclusions

- No contractual commitments are implied by this pilot
- No pricing, licensing terms, or SLAs are discussed in this phase
- The pilot does not represent a production deployment or a commercial agreement
- Origlyph makes no warranty that the pilot assembly represents all customer use cases

---

## Estimated Phases

| Phase | Activity | Estimated effort |
|---|---|---|
| 1 | Kick-off and data collection | 1 session, ≤ 1 hour |
| 2 | Data entry and internal validation | Origlyph team, 1–2 days |
| 3 | Pilot analysis session with customer | 1–2 hours |
| 4 | Results comparison and gap review | 1 session, 1 hour |
| 5 | Written summary | Origlyph team, 1–2 days |

Estimates are indicative and depend on assembly complexity.

---

## Next-Step Decision

At the end of the pilot, both parties agree on one of:

- **Proceed to requirements engagement:** Define a scoped development roadmap
  based on the gap analysis
- **Further pilot:** Run a second case with a different assembly or wider scope
- **Hold:** No immediate next step — customer takes the findings internally
- **No fit at this time:** Documented clearly, door remains open for future engagement

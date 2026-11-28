# Progress Report: Controlled-Drug Monitoring System

**Report date:** 18 November 2026 · **Phase:** Proposal / proof of concept · **Pilot:** Nairobi County
**Related:** [01 Research](01-research-and-ideation.md) · [02 Requirements](02-mvp-requirements.md) · [03 Architecture](03-architecture.md) · [04 Data models](04-data-models.md)

---

## 1. Summary

The project has moved from idea to a **working proof of concept**. A prescriber or pharmacist can look up any patient and see their controlled-drug history across every facility in the county. The system flags misuse at the point of care, and a county regulator can see patterns on a dashboard.

| Area | Status |
|---|---|
| Research and positioning | ✅ Complete |
| MVP requirements | ✅ Complete (decisions confirmed) |
| Architecture | ✅ Complete (modular monolith, Django + React + PostgreSQL) |
| Working proof of concept | ✅ Built; full demo flow verified in a browser |
| Data models | 🟡 Generic version built; specifics awaiting team input |
| Deployment / hosting | 🔴 Not started (Docker setup written but not yet tested) |

**Overall:** all must-have requirements for the hackathon demo are in place. The main remaining work is (1) confirming real-world data rules with stakeholders, (2) testing the Docker / PostgreSQL setup, and (3) preparing the pitch.

---

## 2. What has been done

### 2.1 Research and ideation ([doc 01](01-research-and-ideation.md))
- Studied comparable systems: US prescription drug monitoring programs (Bamboo Health PMP AWARxE / NarxCare), Australia's SafeScript, South Africa's planned codeine tracking, and Kenya's existing PPB and Digital Health Agency systems.
- Found the gap: Kenya tracks **products** (track-and-trace, import permits) but not **patients**. No patient-level monitoring system was found anywhere in East Africa.
- Defined the positioning: *a real-time controlled-substance monitoring layer on Kenya's national health data exchange.*
- Main differentiator: comparing **stock received** against **stock dispensed** at each pharmacy, to expose diversion.

### 2.2 Requirements ([doc 02](02-mvp-requirements.md))
- Defined 5 user roles, about 50 functional requirements (prioritised must / should / could) and the non-functional requirements (security, privacy law, interoperability, performance).
- Confirmed decisions:

| Decision | Outcome |
|---|---|
| Country / pilot | Kenya / Nairobi County |
| First buyer | Government / Digital Health Agency |
| Platform | Web app first; architecture ready for mobile and USSD later |
| Patient portal | Deferred to after the MVP |
| Team | About 5 people, one lead builder |

### 2.3 Architecture ([doc 03](03-architecture.md))
- **Modular monolith:** one backend made of 12 separated modules. It runs as 3 containers (web, API, database) and can be split into microservices later without rewriting business logic.
- **Stack:** Django + Django REST Framework, React + Vite, PostgreSQL.
- Data is shaped to the **FHIR** standard used by Kenya's national shared health record, so connecting to it later is straightforward.

### 2.4 Proof of concept (built)

**Backend:** about 4,500 lines of Python across 12 modules.

| Capability | What it does |
|---|---|
| Accounts and roles | Login; registration checked against the practitioner register (mocked); admin approval; 5 roles with permissions |
| Patient lookup | Searches local records, then the national Client Registry (mocked). Every lookup must state a purpose and is logged |
| E-prescribing | Prescription with a unique code and QR; safety check before issuing |
| Dispensing | Against an e-prescription or a paper prescription. A prescription cannot be dispensed twice (hard block) |
| Alert rules (7) | Early refill, duplicate therapy, multiple prescribers, multiple pharmacies, opioid + benzodiazepine, high daily opioid dose, unknown prescriber licence. Each explains itself in plain language; thresholds are editable by the admin |
| Acknowledgement | Clinicians must give a reason to proceed past an alert, and can record a referral for support |
| Regulator dashboard | Headline numbers, weekly trends, prescriber and pharmacy outliers, hotspots by sub-county, flagged patients (pseudonymised; revealing an identity needs a reason), supply vs dispensed, CSV export |
| Audit log | Append-only and tamper-evident (each entry is chained to the previous one); integrity check button |
| Interoperability | Read-only FHIR endpoints; Swagger API documentation |

**Front end:** about 1,900 lines of React. There are screens for every role, a supply timeline chart, the alert review screen, the dashboard, the audit log and admin pages. It works at phone width and in dark mode.

**Demo data:** synthetic Nairobi data: 12 facilities, 38 users, 17 drugs, 200+ patients, and 6 months of history (about 400 prescriptions and 540 dispenses), generated through the real system. It includes planted stories for the demo: a "doctor shopper", a high-volume tramadol prescriber, a high-dose patient about to receive a benzodiazepine, and a pharmacy dispensing far more than it received.

### 2.5 Data models ([doc 04](04-data-models.md))
- Listed every entity the system stores (about 15), grouped by module.
- Each section has a **"To confirm"** list of questions for the team to take to stakeholders.

---

## 3. Requirements coverage

| Group | Must-have | Delivered | Notes |
|---|---|---|---|
| A. Accounts and access | 5 | 5 | Two-factor login (should-have) not built |
| B. Patient identification | 3 | 3 | Duplicate detection (should-have) also built |
| C. Patient history | 2 | 2 | Supply timeline (should-have) built; date/class filter available in the API only |
| D. E-prescribing | 4 | 4 | Cancel available in the API only, no button yet |
| E. Dispensing | 5 | 5 | Void available in the API only; QR is typed, not camera-scanned |
| F. Alert rules | 9 | 9 | Referral recording (should-have) built |
| G. Regulator dashboard | 3 | 3 | All should-haves and the supply-vs-dispensed preview also built |
| H. Administration | 4 | 4 | Drug catalogue is view-only in the app (edit via Django admin) |
| I. Patient portal | — | — | Deferred by decision |

**All must-have requirements are delivered.** Most should-have items are done too.

---

## 4. Verification

| Check | Result |
|---|---|
| Automated tests (unit test per alert rule + end-to-end demo flow) | ✅ 11 of 11 pass (re-run 18 Nov 2026) |
| Full 6-step demo walked through in a real browser | ✅ All steps pass |
| Dark mode and phone-width layout | ✅ Checked with screenshots |
| Docker Compose with PostgreSQL | 🔴 **Not yet tested.** Docker was not running on the dev machine. Everything so far was tested on the SQLite fallback |

Problems found and fixed during testing:
- The database locked when the patient page loaded several things at once (SQLite only).
- Refills collected a day early were wrongly counted as an overlapping dose.
- The "already dispensed" block did not appear in the browser because of a form validation issue.
- The trend chart rendered empty.
- Duplicate rule names appeared in the flagged-patients list.

---

## 5. Not done yet / known limitations

| Item | Why it matters | Effort |
|---|---|---|
| Test `docker compose up` with PostgreSQL | The demo should run on the production-like setup | Small |
| Commit the code to git | Only the research doc is committed; the code, the other docs and the README are untracked | Small |
| Login tokens kept in browser storage | Acceptable for a demo; move to secure cookies before any real pilot | Small |
| HTTPS, encryption at rest, hosting | Needed for any shared or online demo | Medium |
| One medicine per prescription | Real prescriptions can list several medicines | Medium |
| No camera QR scanning, no cancel/void buttons in the UI | Nice for the demo, not essential | Small |
| Data models are generic placeholders | Real rules (schedules, validity periods, conversion factors) are unconfirmed | Depends on stakeholder answers |
| No Swahili interface | Later; text is not yet separated for translation | Medium |

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| The government extends its own systems (DHA shared health record, PPB track-and-trace) to cover this | Product becomes redundant | Position as a layer *on* the national exchange; FHIR-ready design; offer the regulator analytics they don't have |
| Uptake by pharmacies if participation is voluntary | Thin data, weak alerts | Pitch mandatory use through PPB licence conditions or SHA claim rules |
| Patient identity (fake or duplicate IDs, minors, refugees) | Alerts miss people or wrongly merge them | Client Registry matching now; biometrics later |
| Privacy concerns (Data Protection Act 2019) | Blocks adoption | Purpose-of-use logging, tamper-evident audit, pseudonymised regulator views (already built) |
| Unconfirmed clinical thresholds | Too many alerts (alert fatigue) or too few | Get clinical sign-off; thresholds are already admin-configurable |

---

## 7. Next steps

| # | Task | Owner | Target |
|---|---|---|---|
| 1 | Commit all code and docs to git | Lead builder | This week |
| 2 | Test the Docker / PostgreSQL setup end to end | Lead builder | This week |
| 3 | Gather answers to the "To confirm" questions in doc 04 (PPB schedules, prescription validity, refills, MME factors) | Team | Next 2 weeks |
| 4 | Update the data models with confirmed rules | Lead builder | After step 3 |
| 5 | Prepare the pitch deck and rehearse the 6-step demo script (in the README) | Team | Before the hackathon |
| 6 | Host the demo online (single VM or Render/Railway) | Lead builder | Before the hackathon |
| 7 | Should-haves if time allows: two-factor login, camera QR scanning, cancel/void buttons | Lead builder | Optional |

---

## 8. Decisions needed from the team

1. **Product name**: "CDMS" is a placeholder.
2. **Hosting**: run the demo from a laptop, or host it online for judges to try?
3. **Stakeholder contacts**: who will approach PPB, a pharmacist and a clinician for the "To confirm" questions?

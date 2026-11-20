# MVP Requirements: Controlled-Drug Monitoring System (Web App)

**Status:** Draft v1 · **Date:** 6 November 2026 · **Pilot:** One Kenyan county (to be decided) · **Related:** [01-research-and-ideation.md](01-research-and-ideation.md)

**Priority key:** **M** = must-have for the demo · **S** = should-have · **C** = could-have if time allows

---

## 0. MVP goal

Show one complete story in one county:

1. A doctor writes a prescription for a high-risk drug.
2. A pharmacist looks up the patient, sees their history and gets an alert that explains itself.
3. Every dispense is recorded in real time.
4. The county regulator sees the patterns on a dashboard.

All of this should clearly plug into Kenya's national digital health infrastructure.

**What the MVP must prove:**

1. Looking up a patient takes seconds and shows every dispense of a monitored drug, from every facility in the county.
2. The system catches misuse patterns automatically and explains each one.
3. Regulators get insight that is impossible today.
4. The system is secure, audited and respects privacy, which is the first concern of any government buyer.

---

## 1. Users and roles

| Role | Who | Core need |
|---|---|---|
| **Prescriber** | Doctor or clinical officer at a hospital or clinic | Check patient history, write electronic prescriptions |
| **Pharmacist / pharm tech** | Hospital pharmacy or retail chemist | Check history, dispense against a prescription, see alerts |
| **Facility admin** | Facility in-charge | Manage their facility's staff accounts |
| **County regulator** | County pharmacist or PPB inspector | Dashboards, outlier reports, investigations |
| **System admin** | Project team or DHA operations | Facilities, drug list, alert thresholds, user approval |
| **Patient** *(could-have)* | Citizen | See their own history and who has accessed it |

---

## 2. Functional requirements

### A. Accounts, identity and access

| ID | Requirement | Pri |
|---|---|---|
| FR-A1 | Users register with their professional licence number (KMPDC for doctors, PPB for pharmacists) and their facility. Validated against a **mocked practitioner registry**. | M |
| FR-A2 | An admin approves accounts before first use. Accounts can be suspended. | M |
| FR-A3 | Role-based access control. Each role sees only its own screens and data. | M |
| FR-A4 | Two-factor login (OTP via email or authenticator app; SMS later). | S |
| FR-A5 | Sessions time out after inactivity. | M |
| FR-A6 | Facility registry: name, type (hospital, clinic, retail pharmacy), sub-county, licence number. Seeded from a **mocked facility registry**. | M |

### B. Patient identification

| ID | Requirement | Pri |
|---|---|---|
| FR-B1 | Look up a patient by national ID, Maisha Namba, birth certificate number (minors), passport or refugee ID, through a **mocked Client Registry** that returns one Client Registry ID (CR-ID). | M |
| FR-B2 | If the patient is not found, register a minimal patient record (name, date of birth, sex, ID type and number, phone) and mark it "unverified." | M |
| FR-B3 | Detect possible duplicates during registration (same name, DOB and phone but a different ID) and warn the user. | S |
| FR-B4 | Every patient lookup requires a **reason** (dispensing, prescribing, consultation) and is written to the audit log. | M |

### C. Patient history view (core screen)

| ID | Requirement | Pri |
|---|---|---|
| FR-C1 | Timeline of all monitored-drug prescriptions and dispenses across the county: drug, strength, quantity, days' supply, prescriber, dispensing facility, date. | M |
| FR-C2 | Summary panel at the top: active medicines, total daily opioid dose (in morphine-equivalent terms), number of prescribers and pharmacies in the last 90 days, open alerts. | M |
| FR-C3 | Filter by date range and drug class. | S |
| FR-C4 | Visual timeline with bars showing how days' supply overlaps. | S |
| FR-C5 | Printable or PDF summary for the clinical record. | C |

### D. Electronic prescribing

| ID | Requirement | Pri |
|---|---|---|
| FR-D1 | A prescriber creates a prescription for a monitored drug: drug (from the catalogue), strength, dose, frequency, quantity, days' supply, number of refills allowed, notes. | M |
| FR-D2 | Each prescription gets a unique code and a QR code that the patient takes to any pharmacy. | M |
| FR-D3 | Alert rules run **before** the prescription is saved, so the prescriber sees warnings such as "patient already has active tramadol from another prescriber." | M |
| FR-D4 | The prescriber can cancel a prescription that has not been dispensed yet. | S |
| FR-D5 | Prescriptions expire after a set period (default 30 days) if not dispensed. | M |

### E. Dispensing

| ID | Requirement | Pri |
|---|---|---|
| FR-E1 | The pharmacist pulls up an electronic prescription by code or QR, or by patient ID to see the patient's open prescriptions. | M |
| FR-E2 | Record a dispense: quantity, batch number (optional, for future track-and-trace), date, pharmacist. Full or partial dispense. | M |
| FR-E3 | **Paper prescription entry:** record a dispense against a paper prescription, capturing prescriber name, prescriber licence number and prescription date. Most prescriptions in Kenya are still on paper, so this is essential. | M |
| FR-E4 | A prescription cannot be dispensed beyond its quantity or refill limit. Redeeming the same prescription twice is **blocked**: it is a hard rule, not a clinical judgement. | M |
| FR-E5 | Alert rules run before the dispense is confirmed (see section F). | M |
| FR-E6 | Corrections are made by voiding a dispense with a reason. Records are never deleted. | M |

### F. Alert rules engine (key feature)

All alert rules are **advisory** and never block dispensing. The only hard block is FR-E4 (redeeming the same prescription twice). Every alert shows the reasons it fired in plain language. Every threshold can be configured by the admin.

| ID | Rule | Default logic | Severity |
|---|---|---|---|
| FR-F1 | **Early refill** | New supply of the same drug or class while more than 25% of the previous days' supply should remain | Warning |
| FR-F2 | **Duplicate therapy** | Two active prescriptions for the same drug class from different prescribers | Warning |
| FR-F3 | **Multiple prescribers** | 3 or more prescribers of monitored drugs in 30 days | Warning, or Critical at 4 or more |
| FR-F4 | **Multiple pharmacies** | 3 or more dispensing pharmacies in 30 days | Warning, or Critical at 4 or more |
| FR-F5 | **Dangerous combination** | Opioid and benzodiazepine supplies overlap (combination list can be extended) | Critical |
| FR-F6 | **High daily dose** | Opioid daily dose of 90 morphine-equivalent mg or more | Critical (Warning at 50 or more) |
| FR-F7 | **Paper prescription anomaly** | Prescriber licence number on a paper prescription is not in the registry | Warning |

| ID | Behaviour | Pri |
|---|---|---|
| FR-F8 | To proceed past an alert, the user must **acknowledge it and choose a reason** (for example "clinically justified," "patient lost medication," "verified with prescriber"), with an optional note. The override is logged. | M |
| FR-F9 | The user can record that they referred the patient for support (counselling or addiction treatment), in keeping with the patient-safety framing. | S |
| FR-F10 | All alerts and overrides are stored and feed the regulator dashboard. | M |

### G. Regulator dashboard (county)

| ID | Requirement | Pri |
|---|---|---|
| FR-G1 | Headline numbers for a chosen period: dispenses, patients, alerts by type, overrides. | M |
| FR-G2 | Trend charts of dispenses by drug class over time. | M |
| FR-G3 | **Outlier tables:** top prescribers and pharmacies by volume and by alert rate compared with their peers. | M |
| FR-G4 | Patients with repeated critical alerts. Identities stay hidden until the regulator clicks to reveal one, and each reveal is logged. | S |
| FR-G5 | Map or chart by sub-county showing hotspots. | S |
| FR-G6 | Drill down from a prescriber or facility to its individual records. | S |
| FR-G7 | Export reports as CSV or PDF. | C |
| FR-G8 | **Supply vs. dispensed** panel, using mocked stock-received data per pharmacy, to preview the track-and-trace reconciliation feature on the roadmap. | C (strong demo moment) |

### H. Administration

| ID | Requirement | Pri |
|---|---|---|
| FR-H1 | Manage the **drug catalogue**: name, generic name, drug class, strength, form, morphine-equivalent conversion factor, monitored yes/no. | M |
| FR-H2 | Manage alert thresholds without changing code. | M |
| FR-H3 | User and facility management, approvals and suspensions. | M |
| FR-H4 | Audit log viewer: who accessed which patient, when, and why. | M |

### I. Patient transparency

| ID | Requirement | Pri |
|---|---|---|
| FR-I1 | Patient portal: log in with ID and OTP to see own dispense history and an **access log of who viewed it**. | C |
| FR-I2 | Patient can raise a dispute ("this dispense wasn't me"), which goes to the regulator's queue. | C |

---

## 3. Starter drug list (general, configurable later)

| Class | Drugs |
|---|---|
| **Opioids** | Morphine, pethidine, fentanyl, codeine (including combination products), tramadol, oxycodone, methadone |
| **Benzodiazepines** | Diazepam, lorazepam, alprazolam, midazolam, clonazepam |
| **Others** | Ketamine, phenobarbital, methylphenidate, pregabalin |

Each entry needs a drug class (the alert rules work at class level) and, for opioids, a morphine-equivalent conversion factor.

---

## 4. Non-functional requirements

| Area | Requirement |
|---|---|
| **Security** | HTTPS only. Data encrypted at rest. Passwords hashed. Protection against the OWASP Top 10 web vulnerabilities. Least-privilege roles. |
| **Audit** | Every read and write of patient data is logged. The log is append-only and cannot be edited. |
| **Privacy and legal** | Designed to satisfy the **Data Protection Act 2019** and the **Digital Health Act 2023**: collect only what is needed, require a reason for access, define data retention, publish a privacy notice. Document this, because judges and government buyers will ask. |
| **Interoperability** | Data modelled on **FHIR R4** resources (Patient, Practitioner, Organization, Medication, MedicationRequest, MedicationDispense, AuditEvent) to match Kenya's national shared health record. |
| **API-first** | The web app uses the same API as future clients (mobile, USSD, pharmacy point-of-sale integrations). No logic is built only for the web. |
| **Performance** | Patient lookup and history load in under 2 seconds. Alert rules are evaluated in under 1 second. |
| **Usability** | A dispense with no alerts takes 4 clicks or fewer. Responsive layout that works in a tablet or phone browser, since many chemists only have a phone. |
| **Reliability** | No silent data loss. A failed dispense submission is retried clearly, without creating a duplicate. |
| **Multi-county readiness** | All data is tagged by county from day one, so scaling from one county to 47 is a configuration change, not a rewrite. |
| **Language** | English for the MVP. Interface text is kept separate from code so Swahili can be added later. |
| **Explainability** | Every alert stores the rule, the inputs and the thresholds that triggered it. |

---

## 5. Mocks and seed data (for the hackathon)

- **Mock registries:** Client Registry, practitioner registry (KMPDC/PPB) and facility registry. Build them behind the same interface the real APIs would use, so they can be swapped for the real services later.
- **Seed data for one county:** about 10 facilities, 20 prescribers, 15 pharmacists, 200 patients and 6 months of dispensing history. Include these planted scenarios:
  - a "doctor shopper" visiting 4 prescribers and 4 pharmacies
  - an opioid and benzodiazepine overlap
  - a high-volume tramadol prescriber
  - a pharmacy dispensing more than it received
- **Demo accounts** for each role.

---

## 6. Out of scope for the MVP (roadmap)

- Real integration with DHA, SHA or PPB (mocked for now)
- SMS, USSD and mobile apps
- Biometric patient verification
- Real track-and-trace reconciliation (only the mocked panel in FR-G8)
- Machine-learning risk scores (rules only, by design, since explainable rules are a selling point)
- Rollout to multiple counties, payments and billing

---

## 7. Hackathon demo script

The requirements above should support this flow from start to finish:

1. **Dr. A** prescribes tramadol. No alerts.
2. The patient visits **Dr. B**. A "Duplicate therapy" warning appears, with its reasons.
3. **Pharmacy X** dispenses. A "Multiple pharmacies" critical alert fires. The pharmacist overrides it or refers the patient, and the reason is logged.
4. Someone tries to redeem the same prescription again at **Pharmacy Y**. It is **blocked**.
5. Switch to the **county regulator dashboard**. The prescriber outlier, the hotspot sub-county and the supply-vs-dispensed gap are visible.
6. Show the **audit log** and the patient's view of who accessed their record. This answers the privacy question before the judges ask it.

---

## 8. Business considerations built in now

| Built into the MVP | Why it matters commercially |
|---|---|
| County tagging and configurable rules | Allows licensing per county to government |
| FHIR-based API | Enables integration fees from point-of-sale and EMR vendors, and a path to DHA certification |
| Regulator dashboard | The product government pays for. Clinicians use the lookup for free. |

---

## 9. Decisions

| # | Decision | Outcome |
|---|---|---|
| 1 | **Pilot county** | **Nairobi.** Seed data uses Nairobi sub-counties (Westlands, Embakasi, Kasarani, Starehe, etc.). |
| 2 | **Patient portal (FR-I1/I2)** | **Out of the MVP.** Kept on the roadmap; the architecture leaves room for it. |
| 3 | **Team size and timeline** | **About 5 people, one lead builder.** Project is at the proposal stage, so the goal is a working proof of concept: focus on the **M** items and the demo script, and add **S** items only where they strengthen the demo. |

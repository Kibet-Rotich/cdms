# Data Models: What We Store

**Status:** Draft v1 (generic placeholders in the proof of concept) · **Date:** 6 November 2026 · **Related:** [03-architecture.md](03-architecture.md)

This lists every entity the system stores, grouped by the module that owns it. The proof of concept already implements a generic version of each. The **"To confirm"** column lists the questions the team needs answered (from regulators, pharmacists, clinicians and DHA documentation) before the models are finalised.

Conventions for every model unless stated otherwise:

- **ID:** UUID.
- **Timestamps:** `created_at` and `updated_at`.
- **County code:** a `county_code` field (Nairobi = `047`) on every patient-related or facility-related record.
- **No links across modules.** A model never holds a foreign key into another module. It stores the other record's ID only.

---

## 1. Identity & Access (IAM)

### User

| Field | Purpose |
|---|---|
| email, password (hashed), full_name, phone | Login and contact |
| role | PRESCRIBER, PHARMACIST, FACILITY_ADMIN, REGULATOR, SYSTEM_ADMIN |
| licence_number, cadre | Professional licence. Also used as the prescriber's identity in alert rules |
| facility_id | Where the user works (one facility in the MVP) |
| status | PENDING → ACTIVE → SUSPENDED |
| approved_by, approved_at | Who approved the account, and when |

**To confirm**
- Can a practitioner work at more than one facility? This is common for locums. If so, the user needs a link to several facilities.
- Which cadres may prescribe controlled drugs? For example, can clinical officers prescribe every schedule?
- Do pharmaceutical technologists dispense controlled drugs, or only pharmacists?
- How and how often are licences renewed? We need to know when to re-verify.
- Is MFA required, and which method: SMS OTP or an authenticator app?

---

## 2. Registry (master data)

### Facility

| Field | Purpose |
|---|---|
| kmhfl_code | Kenya Master Health Facility List code |
| name, facility_type, ownership | Hospital, health centre, clinic or retail pharmacy; public, private or faith-based |
| sub_county, county_code, latitude/longitude | Hotspot analysis |
| ppb_licence_number | Pharmacy premises licence |
| active | Whether the facility is operating |

### DrugClass

| Field | Purpose |
|---|---|
| code, name | OPIOID, BENZODIAZEPINE, STIMULANT, ANAESTHETIC, BARBITURATE, GABAPENTINOID. Alert rules work at class level |

### Drug (catalogue)

| Field | Purpose |
|---|---|
| name, generic_name, drug_class | What it is |
| strength_mg, unit, form | Strength per unit (tablet, capsule, mL, ampoule, patch) |
| mme_factor | Morphine-equivalent conversion factor (opioids only); drives the high-dose rule |
| monitored, active | Whether it is on the monitored list, and whether it is in use |

### Practitioner (local copy of the national registers)

| Field | Purpose |
|---|---|
| licence_number, full_name, cadre, regulator (KMPDC, COC, PPB), status | Confirms that a licence on a prescription is real and active |

**To confirm**
- The **official monitored-drug list** and schedules from PPB, including the Narcotic Drugs and Psychotropic Substances schedules.
- The **national product codes** to use (KEML, PPB registration number or GTIN). We need these to link to track-and-trace.
- The **morphine-equivalent factors** to adopt locally, with clinical sign-off, especially for tramadol, codeine and fentanyl patches.
- **Combination products** such as paracetamol/codeine: store the strength of the controlled component only, or both components?
- Do we need **brand names** (several brands per generic)?

---

## 3. Patient

### Patient

| Field | Purpose |
|---|---|
| cr_id | DHA Client Registry ID (empty if not yet verified) |
| first_name, middle_name, last_name, date_of_birth, sex, phone | Demographics needed to confirm identity |
| verified | Matched in the Client Registry, or registered locally |
| registered_by, registered_at_facility | Who registered an unverified patient, and where |

### PatientIdentifier

| Field | Purpose |
|---|---|
| id_type, value | NATIONAL_ID, MAISHA_NAMBA, BIRTH_CERT, PASSPORT, REFUGEE_ID. One patient can have several |

**To confirm**
- The **Client Registry API**: what it returns and what we are allowed to store. Data minimisation applies under the Data Protection Act.
- How to handle **minors**, who may only have a birth certificate or appear under a parent's ID.
- How to handle **foreign nationals and refugees**.
- Whether to keep the phone number at all. It is useful for future SMS notices but is extra personal data.

---

## 4. Prescription

### Prescription (one medicine per prescription in the MVP)

| Field | Purpose |
|---|---|
| code | Short code and QR content given to the patient (e.g. `RX-K7P2M9Q`) |
| patient_id, prescriber_id, prescriber_name, prescriber_licence, facility_id | Who the prescription is for, who wrote it, and where |
| drug_id, dosage_instructions, quantity, days_supply, refills_allowed | What was prescribed |
| quantity_dispensed | Running total; enforces the "no double redemption" rule |
| diagnosis_note, notes | Clinical context |
| status | ACTIVE, COMPLETED, CANCELLED, EXPIRED |
| issued_at, expires_at | Validity window (30 days in the MVP) |
| idempotency_key | Stops a double-submitted form from creating two prescriptions |

**To confirm**
- The **legal validity period** for controlled-drug prescriptions, and whether it differs by schedule.
- **Are refills allowed** for controlled drugs in Kenya, and with what limits?
- Should one prescription hold **several medicines** (a prescription with item lines)?
- Must we store a **diagnosis code** (ICD-10/11)? It helps oversight but is more sensitive data.
- The format of the **national e-prescription standard** (DHA / Kenya ePrescription FHIR Implementation Guide).

---

## 5. Dispensing

### Dispense

| Field | Purpose |
|---|---|
| patient_id, prescription_id (empty for paper) | Links to the patient and, for e-prescriptions, the prescription |
| drug_id, quantity, days_supply, batch_number | What was handed over |
| facility_id, pharmacist_id, pharmacist_name | Where, and by whom |
| prescriber_name, prescriber_licence | Copied from the e-prescription or typed from the paper one |
| is_paper, paper_rx_date, paper_rx_number, paper_prescriber_facility, paper_licence_verified | Paper prescription capture |
| dispensed_at, status, void_reason, voided_by, voided_at | Records are voided, never deleted |
| evaluation_id, idempotency_key | Traceability to the alert check; protection against double-submission |

**To confirm**
- What the **controlled-drugs register** (the paper DDA book) legally requires. The digital record should replace it, or at least match it.
- Whether pharmacies must record **who collected** the medicine (patient or agent, plus the agent's ID).
- Whether **partial dispensing** happens in practice, and how it is recorded today.
- Rules for **in-patient / ward dispensing** in hospitals. That is a different workflow from outpatient dispensing.

---

## 6. Supply (mocked until PPB track-and-trace is available)

### StockReceipt

| Field | Purpose |
|---|---|
| facility_id, drug_id, batch_number, gtin, quantity | Stock received by a facility |
| supplier_name, received_at, source | Where it came from (MANUAL, MOCK_TT or TRACK_AND_TRACE) |

**To confirm**
- What PPB track-and-trace will expose, and whether we can get access.
- Whether we also need **stock-on-hand and stock adjustments** (expiries, breakages, returns) for a fair reconciliation.

---

## 7. Medication History (read model, built from events)

### MedicationEvent

| Field | Purpose |
|---|---|
| kind | PRESCRIBED or DISPENSED |
| source_id, prescription_id, patient_id | Links back to the original record |
| drug_id, drug_name, class_code, quantity, days_supply | Copied in so the timeline loads fast |
| start_date, end_date, daily_mme | Supply period and dose, used by the alert rules |
| prescriber_key, prescriber_name, facility_id, facility_name, sub_county | Who and where |
| is_paper, status, occurred_at | Paper or electronic; ACTIVE, VOIDED or CANCELLED; when |

This is a copy. It can always be rebuilt from the events, so it needs no separate team input beyond the fields above.

---

## 8. Alerts

### RuleConfig

| Field | Purpose |
|---|---|
| code, enabled, params (JSON) | Thresholds per rule that the admin can change |

### Evaluation

| Field | Purpose |
|---|---|
| action, patient_id, actor_id, facility_id, proposed, findings | The result of each `preview` check |

### Alert

| Field | Purpose |
|---|---|
| action, subject_type, subject_id | What triggered it: which prescription or dispense |
| patient_id, facility_id, prescriber_key | Who it concerns |
| rule_code, severity, title, message, details | What fired and why. Explainable: details hold the exact numbers and thresholds |
| acknowledged_by, ack_reason, ack_note | The clinician's decision |
| referral_made, referral_note | Whether the patient was referred for support |

**To confirm**
- **Thresholds**, with clinical sign-off: early refill %, number of prescribers and pharmacies, MME warning and critical levels.
- The **reason codes** clinicians actually need when overriding an alert.
- **Referral destinations**: NACADA, MAT clinics, counselling. A list of these could become its own model.

---

## 9. Audit

### AuditEvent (append-only, hash-chained)

| Field | Purpose |
|---|---|
| seq, occurred_at | Order and time |
| actor_id, actor_name, actor_role, facility_id, ip_address | Who |
| action, resource_type, resource_id, patient_id | What was accessed or changed |
| purpose | Why (DISPENSING, PRESCRIBING, CONSULTATION, OVERSIGHT) |
| details | Extra context |
| prev_hash, hash | Tamper evidence |

**To confirm**
- **Retention period** for audit logs and for clinical records, under the Data Protection Act 2019 and the Digital Health Act 2023.
- Whether patients should be able to see their own access log. This is the deferred patient portal.

---

## 10. Interop (MVP only)

### MockRegistryRecord

| Field | Purpose |
|---|---|
| kind (CLIENT, PRACTITIONER), key, data | Seeded stand-ins for the national registries. Replaced by live API adapters later |

---

## 11. Not stored yet (future models)

| Model | Why we will need it |
|---|---|
| ReferralService | Directory of support services, for referrals made from alerts |
| Investigation / Case | Regulator case management for flagged prescribers, pharmacies and patients |
| PatientDispute | Patient disputes "this wasn't me" (patient portal) |
| Notification | SMS and email notices (OTP, patient dispense notice) |
| FacilityMembership | A user working at several facilities |
| StockAdjustment | Expiries, returns and losses, for accurate supply reconciliation |

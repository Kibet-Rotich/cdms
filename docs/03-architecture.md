# Architecture: Controlled-Drug Monitoring System

**Status:** Draft v1 · **Date:** 6 November 2026 · **Related:** [02-mvp-requirements.md](02-mvp-requirements.md)

---

## 1. Architectural style: modular monolith

The backend is **one deployable application** made of **strongly separated modules**. Each module owns its own data and exposes a small public interface. No module reaches into another module's tables or internal code.

**Why this style now:**

| Concern | How the modular monolith handles it |
|---|---|
| One lead builder, proof-of-concept stage | One codebase, one deployment, one database to run and debug |
| Changes should not ripple across the system | Modules talk only through public interfaces and events, so internal changes stay inside the module |
| Microservices later | Module boundaries are drawn as future service boundaries. Splitting one out means replacing an in-process call with an HTTP call and the in-process event bus with a message broker. Business logic does not change. |

**Rules every module follows:**

1. **Owns its data.** Each module has its own PostgreSQL schema. No foreign keys or joins across schemas; other modules' records are referenced by ID only.
2. **Public interface only.** Other modules call a module through its *facade* (a service interface), never its repositories or internal classes.
3. **Events for side effects.** When something happens ("dispense recorded"), the module publishes a domain event. Interested modules subscribe. The publisher does not know who is listening.
4. **No circular dependencies.** The dependency graph in section 3 must stay acyclic.

---

## 2. System overview

```
                         ┌───────────────────────────────┐
   Browser (web app) ───▶│   Web front end (React SPA)   │
                         └───────────────┬───────────────┘
                                         │  HTTPS / JSON  (REST API v1)
                         ┌───────────────▼───────────────────────────────────────┐
                         │                 API application (modular monolith)     │
                         │  ┌──────────────────────────────────────────────────┐  │
                         │  │ Cross-cutting: auth, RBAC + scope, purpose-of-use,│  │
                         │  │ audit interceptor, validation, errors, idempotency│  │
                         │  └──────────────────────────────────────────────────┘  │
                         │  IAM │ Registry │ Patient │ Prescription │ Dispensing  │
                         │  Supply │ Medication History │ Alerts │ Oversight      │
                         │  Audit │ Interop (adapters + FHIR façade)              │
                         │          ▲ in-process event bus + outbox ▲             │
                         └───────────────┬───────────────────────┬───────────────┘
                                         │                       │
                              ┌──────────▼─────────┐   ┌─────────▼──────────────┐
                              │ PostgreSQL         │   │ External systems        │
                              │ (schema per module)│   │ MVP: mocked adapters    │
                              └────────────────────┘   │ Later: DHA Client       │
                                                       │ Registry, KMPDC/PPB,    │
                                                       │ KMHFR, HIE, PPB T&T, SMS│
                                                       └─────────────────────────┘
```

**Running pieces for the MVP:** 3 containers. These are the web front end, the API application and PostgreSQL.

---

## 3. Modules

### 3.1 Module list

| # | Module | Owns (data) | Responsibility | Requirements |
|---|---|---|---|---|
| 1 | **IAM** (Identity & Access) | users, roles, sessions, MFA secrets | Login, tokens, MFA, account approval and suspension, role and scope checks | FR-A1–A5 |
| 2 | **Registry** | facilities, practitioners (local copy), drug catalogue, drug classes | Master data: facility list, practitioner licence verification, drug catalogue with morphine-equivalent factors | FR-A1, A6, FR-H1, FR-F7 |
| 3 | **Patient** | patients, patient identifiers | Look up and register patients, link to Client Registry ID, detect duplicates | FR-B1–B3 |
| 4 | **Prescription** | prescriptions, prescription items | Electronic prescription lifecycle: create, code/QR, cancel, expire, track remaining quantity and refills | FR-D1–D5, FR-E4 |
| 5 | **Dispensing** | dispenses, paper prescription records, voids | Record dispenses (electronic or paper), partial dispense, voids | FR-E1–E6 |
| 6 | **Supply** | stock receipts | Record stock received per pharmacy (mocked now, PPB track-and-trace later) | FR-G8 |
| 7 | **Medication History** | read model: patient medication timeline | Builds and serves each patient's timeline and summary (active medicines, daily dose, prescriber and pharmacy counts) | FR-C1–C4 |
| 8 | **Alerts** | rule definitions and thresholds, alert records, acknowledgements, referrals | Rules engine: evaluates prescriptions and dispenses, stores alerts and overrides | FR-F1–F10, FR-H2 |
| 9 | **Oversight** | aggregates / materialized views | Regulator dashboard: headline numbers, trends, outliers, hotspots, flagged patients, supply reconciliation | FR-G1–G8 |
| 10 | **Audit** | audit events (append-only) | Records every access to patient data and every change; serves the audit log viewer | FR-B4, FR-H4 |
| 11 | **Interop** | adapter config, mapping tables | Adapters to external registries (mocked in MVP); FHIR façade for future integrations | NFR Interoperability |
| — | **Shared kernel** | none | Common types (IDs, county code, date ranges), event bus, request context (user, role, facility, county, purpose) | — |

The patient portal (FR-I1/I2) is not in the MVP. When it is added, it becomes a new client of the existing Medication History and Audit APIs, plus a patient role in IAM. No new core module is needed.

### 3.2 Dependency graph

Arrows mean "calls the facade of" (synchronous). Dotted lines are event subscriptions (asynchronous).

```
                    ┌─────────┐
                    │   IAM   │◀──────────── (every module reads request context)
                    └─────────┘

  ┌──────────┐     ┌──────────┐
  │ Interop  │◀────│ Registry │◀─────────────────────────────────┐
  │(adapters)│◀────│ Patient  │◀──────────────┐                  │
  └──────────┘     └──────────┘               │                  │
                                              │                  │
          ┌──────────────┐   ┌──────────────┐ │                  │
          │ Prescription │──▶│    Alerts    │─┼──▶ Medication ───┤
          └──────┬───────┘   └──────▲───────┘ │     History      │
                 │                  │         │                  │
          ┌──────▼───────┐          │         │                  │
          │  Dispensing  │──────────┘─────────┘                  │
          └──────────────┘                                       │
                                                                 │
   Events:  Prescription ┄┄▶ Medication History, Oversight, Audit
            Dispensing   ┄┄▶ Medication History, Oversight, Audit, Prescription (decrement remaining qty)
            Alerts       ┄┄▶ Oversight, Audit
            Supply       ┄┄▶ Oversight
```

Key points:

- **Alerts depends on Medication History** (to read a patient's recent supply) and **Registry** (drug classes, morphine-equivalent factors). It does not depend on Prescription or Dispensing. They call *it*.
- **Medication History** never calls Prescription or Dispensing. It builds its timeline from their **events**. This keeps the graph acyclic and makes History easy to extract later.
- **Oversight and Audit** only listen to events and serve read APIs. Nothing depends on them, so they are the easiest modules to split out first.

### 3.3 Internal structure of each module

Every module follows the same layout so the codebase stays predictable:

```
modules/dispensing/
  api/            # HTTP controllers, request/response DTOs        (outer layer)
  application/    # use cases: RecordDispense, VoidDispense         (orchestration)
  domain/         # entities, rules, domain events                  (pure logic, no framework)
  infrastructure/ # repositories, DB schema/migrations, adapters    (outer layer)
  dispensing.facade.ts   # the ONLY thing other modules may import
  dispensing.module.ts   # wiring
```

Changing the database, framework or transport touches only `infrastructure/` or `api/`. Domain logic stays untouched.

---

## 4. Key flows

### 4.1 Dispense with alerts (the core flow)

Dispensing is a **two-step** flow, so the pharmacist always sees alerts before committing and the server never trusts the client to have checked.

```
Pharmacist UI        Dispensing           Alerts            Medication History      Event bus
     │  POST /dispenses/preview │            │                      │                    │
     │─────────────────────────▶│ evaluate() │                      │                    │
     │                          │───────────▶│ getSupplyWindow()    │                    │
     │                          │            │─────────────────────▶│                    │
     │                          │            │◀─────────────────────│                    │
     │                          │◀───────────│ findings + evaluationId                   │
     │◀─────────────────────────│ alerts shown (reasons in plain language)               │
     │                          │            │                      │                    │
     │  POST /dispenses  {evaluationId, acknowledgements[], Idempotency-Key}             │
     │─────────────────────────▶│ re-evaluate│                      │                    │
     │                          │───────────▶│ (must match; every alert acknowledged)    │
     │                          │ save dispense + outbox event (same transaction)        │
     │                          │──────────────────────────────────────────────────────▶│ DispenseRecorded
     │◀─────────────────────────│ 201 Created                                            │
                                                     ┄┄▶ History updates timeline
                                                     ┄┄▶ Prescription decrements remaining
                                                     ┄┄▶ Oversight updates aggregates
                                                     ┄┄▶ Audit records event
```

- **Hard block (FR-E4):** if the prescription is already fully dispensed, the API returns `409 Conflict`. No acknowledgement can override this.
- **Advisory alerts (FR-F1–F7):** the commit is rejected with `422` if any alert from the re-evaluation is not acknowledged with a reason.
- **Idempotency key** on the commit stops a network retry from creating a duplicate dispense (reliability NFR).

Prescribing uses the same preview → commit pattern (`POST /prescriptions/preview` then `POST /prescriptions`).

### 4.2 Patient lookup

1. UI calls `GET /patients/search` with ID type and number, plus the `X-Purpose-Of-Use` header.
2. The Patient module checks its local records, then the Client Registry adapter (mocked).
3. The audit interceptor records who searched, for which patient, and why.
4. UI loads the timeline from Medication History.

---

## 5. Alerts engine design

The rules engine is the core intellectual property, so it has to be easy to extend without touching existing rules.

- Each rule is a **separate class** implementing one interface:
  ```
  interface Rule {
    code: string                 // e.g. "MULTIPLE_PHARMACIES"
    appliesTo: ("PRESCRIBE" | "DISPENSE")[]
    evaluate(ctx: EvaluationContext, cfg: RuleConfig): Finding[]
  }
  ```
- `EvaluationContext` holds the proposed prescription or dispense plus the patient's supply window from Medication History. Rules do no database queries of their own, so they are pure and easy to test.
- `RuleConfig` (thresholds, severities, on/off) is stored in the Alerts schema and edited through the admin API (FR-H2).
- Each `Finding` stores the rule code, severity, a plain-language message, and the **exact inputs and thresholds** used (explainability NFR).
- **Adding a rule** means writing one new class and registering it. Nothing else changes.

MVP rules: `EARLY_REFILL`, `DUPLICATE_THERAPY`, `MULTIPLE_PRESCRIBERS`, `MULTIPLE_PHARMACIES`, `OPIOID_BENZO_OVERLAP`, `HIGH_DAILY_MME`, `UNKNOWN_PRESCRIBER_LICENCE`.

---

## 6. API design

### 6.1 Conventions

| Topic | Convention |
|---|---|
| Style | REST over HTTPS, JSON. Versioned under `/api/v1`. |
| Contract | OpenAPI spec, generated from code and served at `/api/docs`. The front end and future clients work from this contract. |
| Auth | Short-lived JWT access token plus refresh token. MFA step at login (S). |
| Authorization | Role check **and** scope check. A pharmacist acts only for their own facility. A regulator sees only their own county. |
| Purpose of use | `X-Purpose-Of-Use` header required on any endpoint that returns patient data (`DISPENSING`, `PRESCRIBING`, `CONSULTATION`, `OVERSIGHT`). |
| Errors | RFC 7807 problem+json with a stable `code` field. |
| Idempotency | `Idempotency-Key` header required on `POST /dispenses` and `POST /prescriptions`. |
| Pagination | `?page=&pageSize=`, returning `{ items, total }`. |
| Data shape | Field names and code systems follow FHIR R4 concepts, so mapping to FHIR later is mechanical. |

### 6.2 Endpoints by module

**IAM**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| POST | `/auth/login` | Log in with email/licence and password | public |
| POST | `/auth/mfa/verify` | Complete MFA step (S) | public |
| POST | `/auth/refresh` | New access token | authenticated |
| POST | `/auth/logout` | End session | authenticated |
| GET | `/me` | Current user, role, facility, county | authenticated |
| POST | `/users/register` | Self-registration with licence number and facility | public |
| GET | `/users` | List users, filter by status or facility | admin, facility admin |
| POST | `/users/{id}/approve` | Approve account | admin, facility admin |
| POST | `/users/{id}/suspend` | Suspend account | admin, facility admin |

**Registry**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/facilities` | List or search facilities (by sub-county, type) | authenticated |
| GET | `/facilities/{id}` | Facility details | authenticated |
| POST / PATCH | `/facilities`, `/facilities/{id}` | Manage facilities | admin |
| GET | `/practitioners/verify?licence=&cadre=` | Verify a licence number (used at registration and for paper prescriptions) | authenticated |
| GET | `/practitioners/{id}` | Practitioner details | authenticated |
| GET | `/drugs` | Drug catalogue (filter by class, monitored) | authenticated |
| POST / PATCH | `/drugs`, `/drugs/{id}` | Manage catalogue, morphine-equivalent factors | admin |
| GET | `/drug-classes` | Drug classes | authenticated |

**Patient**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/patients/search?idType=&idNumber=` | Find patient (local, then Client Registry) | prescriber, pharmacist |
| POST | `/patients` | Register unverified patient | prescriber, pharmacist |
| GET | `/patients/{id}` | Patient demographics and identifiers | prescriber, pharmacist |
| GET | `/patients/{id}/possible-duplicates` | Duplicate candidates (S) | prescriber, pharmacist, admin |

**Medication History**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/patients/{id}/medication-history?from=&to=&class=` | Timeline of prescriptions and dispenses | prescriber, pharmacist, regulator |
| GET | `/patients/{id}/medication-summary` | Summary panel: active medicines, daily dose, prescriber/pharmacy counts, open alerts | prescriber, pharmacist, regulator |

**Prescription**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| POST | `/prescriptions/preview` | Run alert rules before saving | prescriber |
| POST | `/prescriptions` | Create prescription (with acknowledgements), returns code and QR | prescriber |
| GET | `/prescriptions/{id}` | Prescription details | prescriber, pharmacist |
| GET | `/prescriptions/by-code/{code}` | Look up by code or scanned QR | pharmacist |
| GET | `/patients/{id}/prescriptions?status=` | Patient's open, dispensed or expired prescriptions | prescriber, pharmacist |
| POST | `/prescriptions/{id}/cancel` | Cancel undispensed prescription (S) | prescriber (owner) |

**Dispensing**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| POST | `/dispenses/preview` | Run alert rules and hard checks for a proposed dispense (electronic or paper) | pharmacist |
| POST | `/dispenses` | Commit dispense with `evaluationId` and acknowledgements | pharmacist |
| GET | `/dispenses/{id}` | Dispense details | pharmacist, regulator |
| POST | `/dispenses/{id}/void` | Void with reason (no deletes) | pharmacist (own facility) |
| GET | `/facilities/{id}/dispenses?from=&to=` | Facility dispensing register | pharmacist (own), regulator |

**Supply** (mocked data in MVP)

| Method | Path | Purpose | Roles |
|---|---|---|---|
| POST | `/stock-receipts` | Record stock received (drug, batch, quantity) | pharmacist, admin |
| GET | `/facilities/{id}/stock-receipts` | Stock received by facility | pharmacist (own), regulator |

**Alerts**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/alerts?patientId=&facilityId=&severity=&from=&to=` | Search stored alerts | regulator, admin |
| GET | `/alerts/{id}` | Alert with full explanation and acknowledgement | regulator, pharmacist, prescriber |
| POST | `/alerts/{id}/referral` | Record referral for support (S) | pharmacist, prescriber |
| GET | `/alert-rules` | Rules with current thresholds | admin, regulator |
| PATCH | `/alert-rules/{code}` | Change thresholds, severity, on/off | admin |

(Evaluation itself is not a public endpoint. It is called internally through the Alerts facade by the two `preview` endpoints.)

**Oversight** (regulator dashboard)

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/oversight/summary?from=&to=` | Headline numbers | regulator |
| GET | `/oversight/trends?class=&granularity=` | Dispenses over time by drug class | regulator |
| GET | `/oversight/outliers/prescribers` | Prescribers ranked against peers | regulator |
| GET | `/oversight/outliers/pharmacies` | Pharmacies ranked against peers | regulator |
| GET | `/oversight/hotspots` | Alerts and volume by sub-county (S) | regulator |
| GET | `/oversight/flagged-patients` | Patients with repeated critical alerts, identities hidden (S) | regulator |
| POST | `/oversight/flagged-patients/{ref}/reveal` | Reveal identity with reason (audited) (S) | regulator |
| GET | `/oversight/supply-reconciliation` | Supply vs. dispensed per pharmacy (C) | regulator |
| GET | `/oversight/reports/export?type=&format=` | CSV or PDF export (C) | regulator |

**Audit**

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/audit-events?actorId=&patientId=&action=&from=&to=` | Search audit log | admin, regulator |

(Writing audit events is internal only: via the audit interceptor and event subscriptions. There is no public write endpoint.)

**Interop** (C for MVP, important for the pitch)

| Method | Path | Purpose | Roles |
|---|---|---|---|
| GET | `/fhir/Patient/{id}` | FHIR R4 view of a patient | system client |
| GET | `/fhir/MedicationDispense?patient=` | FHIR R4 dispenses (shows readiness for the national exchange) | system client |
| GET | `/fhir/MedicationRequest?patient=` | FHIR R4 prescriptions | system client |

### 6.3 Internal facades (module-to-module, not HTTP)

| Facade | Method | Used by |
|---|---|---|
| `RegistryFacade` | `getDrug(id)`, `getDrugClass(id)`, `verifyPractitioner(licence)`, `getFacility(id)` | Prescription, Dispensing, Alerts, Oversight |
| `PatientFacade` | `getPatient(id)`, `resolveIdentifier(type, number)` | Prescription, Dispensing |
| `MedicationHistoryFacade` | `getSupplyWindow(patientId, days)` | Alerts |
| `AlertsFacade` | `evaluate(context) → { evaluationId, findings }`, `verifyAcknowledgements(evaluationId, acks)` | Prescription, Dispensing |
| `PrescriptionFacade` | `getDispensableState(prescriptionId)` | Dispensing |

### 6.4 Domain events

| Event | Published by | Consumed by |
|---|---|---|
| `PrescriptionCreated`, `PrescriptionCancelled`, `PrescriptionExpired` | Prescription | Medication History, Oversight, Audit |
| `DispenseRecorded`, `DispenseVoided` | Dispensing | Medication History, Prescription, Oversight, Audit |
| `AlertRaised`, `AlertAcknowledged`, `ReferralRecorded` | Alerts | Oversight, Audit |
| `StockReceived` | Supply | Oversight |
| `PatientRegistered` | Patient | Audit |
| `UserApproved`, `UserSuspended` | IAM | Audit |

Events are written to an **outbox table** in the same transaction as the change, then delivered by the in-process bus. Nothing is lost if the app crashes mid-request, and the outbox is exactly what a message broker reads from later.

---

## 7. Data architecture

- **One PostgreSQL database, one schema per module:** `iam`, `registry`, `patient`, `rx`, `dispensing`, `supply`, `history`, `alerts`, `oversight`, `audit`, `interop`.
- **No cross-schema foreign keys or joins.** References are plain IDs, and integrity is enforced in the application layer.
- **County tagging:** every patient-related and facility-related row carries `county_code` (Nairobi = `047`) for multi-county readiness.
- **Audit schema is append-only.** The application's database role has `INSERT` and `SELECT` only on it. Each row stores a hash of the previous row (hash chain), so tampering is detectable.
- **Medication History** is a read model rebuilt from events. If it is ever wrong, it can be rebuilt from scratch.
- **Oversight** uses materialized views refreshed on events or on a short schedule. Good enough for one county.
- **Synthetic data only.** No real patient data in the MVP or demo.

---

## 8. Cross-cutting concerns

| Concern | Approach |
|---|---|
| Authentication | JWT access token (about 15 minutes) plus rotating refresh token in an httpOnly cookie. Idle timeout (FR-A5). |
| Authorization | Guards check role, then scope (own facility, own county). Applied per endpoint. |
| Purpose of use | Middleware rejects patient-data requests without a valid `X-Purpose-Of-Use`. |
| Audit | Interceptor logs every patient-data read automatically. Writes are audited through events. |
| Validation | Request schemas validated at the `api/` layer. Domain rules enforced in `domain/`. |
| Configuration | Environment variables. External adapters switched by config (`CLIENT_REGISTRY_MODE=mock\|live`). |
| Observability | Structured JSON logs with a request ID. Health endpoint `/health`. |
| Security | HTTPS, password hashing (argon2/bcrypt), rate limiting on auth endpoints, OWASP Top 10 checks, secrets outside the repo. |

---

## 9. External integrations (adapters)

Each external system sits behind an interface in the Interop module, with a **mock implementation for the MVP**. The mocks use realistic request and response shapes so the demo can show the integration story.

| External system | Interface | MVP | Later |
|---|---|---|---|
| DHA Client Registry | `ClientRegistryPort` | Mock with seeded Nairobi patients | Live DHA API |
| KMPDC / PPB practitioner registers | `PractitionerRegistryPort` | Mock with seeded licences | Live registers |
| Kenya Master Health Facility List (KMHFR) | `FacilityRegistryPort` | Mock with seeded Nairobi facilities | Live KMHFR |
| National health data exchange (HIE / SHR) | `HealthExchangePort` | Not used (FHIR façade only) | Publish MedicationDispense to the shared health record |
| PPB track-and-trace | `TrackAndTracePort` | Seeded stock receipts | Live supply data |
| SMS / USSD gateway | `MessagingPort` | Not used | OTP, alerts, USSD lookups |

---

## 10. Front end

- **Single web app** (React single-page application) with role-based navigation:
  - **Prescriber:** patient lookup → history → new prescription (preview → confirm) → code/QR
  - **Pharmacist:** prescription by code/QR or patient lookup → history → dispense (preview → acknowledge → confirm) → paper prescription entry
  - **Regulator:** dashboard, outliers, hotspots, flagged patients, audit log
  - **Admin:** users, facilities, drug catalogue, alert rules
- Uses only the public REST API, the same contract future mobile, USSD and integration clients will use.
- Responsive layout for tablet and phone browsers.

---

## 11. Technology stack (decided)

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Django 5.2 + Django REST Framework** | Each module is a Django app under `backend/modules/`; others may import only its `facade.py` |
| Auth | JWT (`djangorestframework-simplejwt`) | Access token plus rotating refresh token |
| Database | **PostgreSQL** (Docker Compose); SQLite fallback for quick local runs | |
| API contract | OpenAPI via `drf-spectacular` | Swagger UI at `/api/docs/` |
| Front end | **React 18 + Vite**, React Router, Recharts, qrcode.react | Plain CSS with light/dark design tokens; no component library |
| Testing | Django test runner | Unit tests per alert rule, plus an end-to-end API test of the demo flow |
| Packaging | Docker Compose: `web`, `api`, `db` | |

### 11.1 Where the proof of concept differs from this design (on purpose, for speed)

| Design | Proof of concept | Upgrade path |
|---|---|---|
| One PostgreSQL schema per module | One schema; each module's tables are prefixed with its app label (`dispensing_dispense`, `alerts_alert`, ...). There are still no foreign keys between modules. | Move each app's tables to its own schema with a database router |
| Oversight uses materialized views | Oversight queries other modules' facades live (fast enough for one county) | Add materialized views or a reporting store fed by events |
| Refresh token in an httpOnly cookie | Tokens kept in `localStorage` | Move the refresh token to an httpOnly cookie before any real pilot |
| FHIR façade inside Interop | A separate small `fhir` module, so Interop stays free of dependencies on History and Patient | — |
| Alerts writes in the same transaction as Prescription/Dispensing | Same (fine inside a monolith) | When extracting Alerts, use the outbox and a saga |

---|---|---|---|
| Backend | **NestJS (TypeScript)** | Built-in modules, dependency injection, guards, interceptors and event emitter map directly onto this design. One language across front and back end. | Django + Django REST Framework, if the team is stronger in Python |
| ORM / migrations | Prisma or TypeORM (multi-schema) | Typed queries, migrations per module | Django ORM |
| Database | **PostgreSQL** | Schemas, materialized views, row-level security, mature | — |
| Front end | **React + Vite**, with a component library (e.g. MUI or shadcn/ui) and a charting library | Fast to build dashboards and forms | Next.js |
| API contract | OpenAPI (Swagger), generated from code | Front end and future clients share one contract | — |
| Testing | Unit tests per rule in the alerts engine; API tests for the demo flows | Rules are the core logic and must be correct | — |
| Packaging | Docker Compose: `web`, `api`, `db` | One command to run the demo anywhere | — |
| Hosting (demo) | Single small VM or a platform service (Render, Railway, Fly.io) | Cheap, quick | — |

---

## 12. Path to microservices

When load, team size or a buyer's requirements justify it, extract modules in this order:

| Order | Module | Why first |
|---|---|---|
| 1 | **Audit** | Only consumes events. Security teams often want it isolated. |
| 2 | **Oversight** | Read-heavy analytics. Scales differently and may move to a data warehouse. |
| 3 | **Interop** | Becomes the integration gateway to DHA, PPB and SMS. Has its own release cadence. |
| 4 | **Alerts** | Rules engine scales with request volume and could be offered as a service to other systems. |
| 5 | Core (IAM, Registry, Patient, Prescription, Dispensing) | Stays together until there is a real reason to split. |

**Mechanics of extracting a module:**

1. Move the module folder into its own service. It keeps its schema, which can move to its own database.
2. Replace its facade in callers with an HTTP/gRPC client that implements the same interface.
3. Replace the in-process event bus with a broker (RabbitMQ or Kafka) reading from the same outbox tables.
4. Business logic and domain code do not change.

---

## 13. Open technical decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | Backend language and framework | **Decided: Django + DRF** |
| 2 | Hosting for the demo | Single VM or Render/Railway with Docker Compose |
| 3 | QR scanning | Browser camera-based scanning (S); typing the code manually is enough for the demo |

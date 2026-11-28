# CDMS: Controlled-Drug Monitoring System (proof of concept)

A centralized system that lets any licensed prescriber or pharmacist in a county look up a patient's controlled-drug history across every facility, and that flags misuse patterns (doctor shopping, early refills, duplicate prescriptions, dangerous combinations, high opioid doses) at the point of care. Regulators get a county dashboard. The pilot is Nairobi County.

> **All data is synthetic.** Never load real patient data into this proof of concept.

Docs: [research](docs/01-research-and-ideation.md) · [MVP requirements](docs/02-mvp-requirements.md) · [architecture](docs/03-architecture.md) · [data models](docs/04-data-models.md)

---

## Run it

### Option A: Docker (PostgreSQL, closest to production)

```bash
docker compose up --build
```

Open **http://localhost:5173**. The first start migrates the database and seeds the demo data (about 1–2 minutes).

### Option B: Local without Docker (SQLite)

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo          # add --reset to wipe and re-seed
.venv/bin/python manage.py runserver 8000

# Front end (second terminal)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

To use a local PostgreSQL instead of SQLite, set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_HOST` before running `manage.py`.

### Other useful URLs

| URL | What |
|---|---|
| http://localhost:8000/api/docs/ | Swagger UI for the whole API |
| http://localhost:8000/admin/ | Django admin (log in as `admin@demo.ke`) to view and edit raw data |
| http://localhost:8000/fhir/MedicationDispense?patient=&lt;id&gt; | FHIR R4 view (regulator/admin token required) |

---

## Demo accounts

Password for every account: **`Demo@1234`**. The login page has one-click buttons for each.

| Email | Role | Who |
|---|---|---|
| dr.achieng@demo.ke | Prescriber | "Dr A", Westlands General Hospital |
| dr.baraka@demo.ke | Prescriber | "Dr B", Kasarani Community Hospital |
| pharm.wambui@demo.ke | Pharmacist | "Pharmacy X", Uhuru Pharmacy |
| pharm.otieno@demo.ke | Pharmacist | "Pharmacy Y", Jamii Chemist |
| regulator@demo.ke | County regulator | Dashboard, audit log |
| facility.admin@demo.ke | Facility admin | Approves staff at Westlands General |
| admin@demo.ke | System admin | Users, alert rules, drug catalogue |

Demo patients (National ID):

| ID | Patient | Story |
|---|---|---|
| 30000001 | Grace Wanjiku | Exists only in the (mock) Client Registry. Pulled in on first lookup; clean history |
| 23456789 | Peter Kamau | "Doctor shopper": 4 prescribers and 3 pharmacies in the last month; a tramadol e-prescription from Dr B is waiting |
| 34567890 | Mary Njeri | High-dose morphine (60 MME/day) dispensed 5 days ago; a diazepam prescription is waiting |

Self-registration demo: licence **A19999** (prescriber) or **PPB-29999** (pharmacist). **A18888** is suspended in the registry and is rejected.

---

## Hackathon demo script

1. **Dr A** → look up `30000001` (pulled from the Client Registry) → New prescription → Tramadol 50 mg, 30 caps, 10 days → **No alerts** → issue → code and QR shown.
2. **Dr B** → look up `30000001` → prescribe the same → **Duplicate therapy** warning naming Dr A → acknowledge with a reason → issued.
3. **Pharmacy X (Wambui)** → look up `23456789` → Dispense the open prescription → **5 alerts, 2 critical** (multiple prescribers, multiple pharmacies, early refill, duplicate therapy, high dose) → acknowledge, tick "referred for support" → recorded.
4. **Pharmacy Y (Brian)** → Dispense by code → enter the same code → **Cannot dispense**: already fully dispensed (hard block).
5. **Regulator** → dashboard: Dr Kevin Mutua flagged at 6.8× the median for opioid prescribing; hotspots; flagged patients (pseudonymised, "Reveal" requires a reason); **supply gap** at Mtaa Pharmacy (dispensed far more tramadol than it received).
6. **Regulator** → Audit log → **Verify integrity** → every lookup, with its purpose, including the identity reveal.

Optional: as Pharmacy X, open Mary Njeri (`34567890`) and dispense her diazepam → **Opioid + benzodiazepine** critical alert.

Re-run `python manage.py seed_demo --reset` (or `docker compose down -v && docker compose up`) to reset the demo before presenting.

---

## Project layout

```
backend/
  config/                 settings, root URLs
  core/                   shared kernel: event bus + outbox, errors, permissions, seed_demo command
  modules/                one Django app per module; others import ONLY its facade.py
    iam/                  users, roles, login, approval
    registry/             facilities, practitioners, drug catalogue
    interop/              ports to national systems (mock adapters today)
    patients/             lookup (local → Client Registry), registration
    prescriptions/        e-prescriptions, codes/QR, expiry
    dispensing/           e-Rx and paper dispensing, hard blocks, voids
    supply/               stock receipts (mock track-and-trace)
    history/              medication timeline read model (built from events)
    alerts/               rules engine (rules.py), acknowledgements
    oversight/            regulator dashboard (read-only)
    audit/                append-only, hash-chained audit log
    fhir/                 read-only FHIR R4 façade
frontend/src/
  pages/                  Login, Register, PatientLookup, PatientPage, NewPrescription,
                          Dispense, PaperDispense, Dashboard, AuditLog, Admin
  components/             AlertReview (acknowledge alerts), SupplyTimeline
  api.js                  API client (JWT, purpose-of-use header, refresh)
docs/                     research, requirements, architecture, data models
```

## Tests

```bash
cd backend && .venv/bin/python manage.py test
```

These are unit tests for every alert rule, plus an end-to-end API test of the demo flow (prescribe → alert → dispense → block → dashboard → audit).

## Adding an alert rule

1. Add a class to `backend/modules/alerts/rules.py` with `code`, `title`, `applies_to`, `defaults` and `evaluate(ctx, cfg)`.
2. Append it to `RULES`.
3. Add a unit test in `modules/alerts/tests.py`.

Nothing else changes. The admin "Alert rules" page picks it up automatically.

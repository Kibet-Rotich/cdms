"""Seed synthetic Nairobi pilot data for the demo. ALL DATA IS FICTIONAL.

    python manage.py seed_demo            # seed an empty database
    python manage.py seed_demo --reset    # wipe business data and re-seed

History is generated through the real services (prescriptions.create, dispensing.commit), so the alert
engine, events, read models and audit log are exercised exactly as in live use.
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import OutboxEvent
from modules.alerts import facade as alerts
from modules.alerts.models import Alert, Evaluation, RuleConfig
from modules.alerts.rules import RULES
from modules.audit.models import AuditEvent
from modules.dispensing import services as dispensing
from modules.dispensing.models import Dispense
from modules.history import facade as history
from modules.history.models import MedicationEvent
from modules.iam.models import User
from modules.interop.models import MockRegistryRecord
from modules.patients.models import Patient, PatientIdentifier
from modules.prescriptions import services as prescriptions
from modules.prescriptions.models import Prescription
from modules.registry.models import Drug, DrugClass, Facility, Practitioner
from modules.supply.models import StockReceipt

DEMO_PASSWORD = "Demo@1234"
COUNTY = "047"

DRUG_CLASSES = [
    ("OPIOID", "Opioid analgesics"),
    ("BENZODIAZEPINE", "Benzodiazepines"),
    ("STIMULANT", "CNS stimulants"),
    ("ANAESTHETIC", "Dissociative anaesthetics"),
    ("BARBITURATE", "Barbiturates"),
    ("GABAPENTINOID", "Gabapentinoids"),
]

# key, name, generic, class, strength_mg, unit, form, mme_factor, typical (qty, days, instructions)
DRUGS = [
    ("tramadol50", "Tramadol 50 mg capsule", "Tramadol", "OPIOID", 50, "CAPSULE", "Capsule", 0.2, (30, 10, "1 capsule three times daily")),
    ("codeine30", "Codeine phosphate 30 mg tablet", "Codeine", "OPIOID", 30, "TABLET", "Tablet", 0.15, (20, 5, "1 tablet four times daily")),
    ("paracod", "Paracetamol/Codeine 500/8 mg tablet", "Codeine (combination)", "OPIOID", 8, "TABLET", "Tablet", 0.15, (24, 6, "2 tablets four times daily")),
    ("morphine10", "Morphine sulfate 10 mg tablet", "Morphine", "OPIOID", 10, "TABLET", "Tablet", 1.0, (60, 30, "1 tablet twice daily")),
    ("pethidine50", "Pethidine 50 mg/mL injection", "Pethidine", "OPIOID", 50, "AMPOULE", "Injection", 0.1, (4, 2, "50 mg IM every 6 hours as needed")),
    ("oxycodone5", "Oxycodone 5 mg tablet", "Oxycodone", "OPIOID", 5, "TABLET", "Tablet", 1.5, (28, 7, "1 tablet four times daily")),
    ("methadone10", "Methadone 10 mg tablet", "Methadone", "OPIOID", 10, "TABLET", "Tablet", 4.7, (30, 30, "1 tablet daily")),
    # Fentanyl patch: strength is mcg/h; factor set so qty x 25 x f / days gives ~2.4 MME per mcg/h
    ("fentanyl25", "Fentanyl 25 mcg/h transdermal patch", "Fentanyl", "OPIOID", 25, "PATCH", "Patch", 7.2, (10, 30, "Apply 1 patch every 72 hours")),
    ("diazepam5", "Diazepam 5 mg tablet", "Diazepam", "BENZODIAZEPINE", 5, "TABLET", "Tablet", None, (14, 14, "1 tablet at night")),
    ("lorazepam1", "Lorazepam 1 mg tablet", "Lorazepam", "BENZODIAZEPINE", 1, "TABLET", "Tablet", None, (14, 14, "1 tablet at night")),
    ("alprazolam05", "Alprazolam 0.5 mg tablet", "Alprazolam", "BENZODIAZEPINE", 0.5, "TABLET", "Tablet", None, (28, 14, "1 tablet twice daily")),
    ("clonazepam2", "Clonazepam 2 mg tablet", "Clonazepam", "BENZODIAZEPINE", 2, "TABLET", "Tablet", None, (30, 30, "1 tablet daily")),
    ("midazolam5", "Midazolam 5 mg/mL injection", "Midazolam", "BENZODIAZEPINE", 5, "AMPOULE", "Injection", None, (2, 1, "As directed (procedural)")),
    ("ketamine50", "Ketamine 50 mg/mL injection", "Ketamine", "ANAESTHETIC", 50, "AMPOULE", "Injection", None, (2, 1, "As directed (procedural)")),
    ("phenobarb30", "Phenobarbital 30 mg tablet", "Phenobarbital", "BARBITURATE", 30, "TABLET", "Tablet", None, (60, 30, "1 tablet twice daily")),
    ("methylphen10", "Methylphenidate 10 mg tablet", "Methylphenidate", "STIMULANT", 10, "TABLET", "Tablet", None, (60, 30, "1 tablet twice daily")),
    ("pregabalin75", "Pregabalin 75 mg capsule", "Pregabalin", "GABAPENTINOID", 75, "CAPSULE", "Capsule", None, (60, 30, "1 capsule twice daily")),
]
OUTPATIENT_WEIGHTS = {
    "tramadol50": 34, "codeine30": 10, "paracod": 12, "diazepam5": 11, "pregabalin75": 9, "morphine10": 5,
    "alprazolam05": 4, "lorazepam1": 4, "phenobarb30": 4, "methylphen10": 3, "clonazepam2": 2, "oxycodone5": 1,
}

# kmhfl, name, type, sub-county, ownership, lat, lng
FACILITIES = [
    ("10001", "Westlands General Hospital", "HOSPITAL", "Westlands", "PRIVATE", -1.2649, 36.8031),
    ("10002", "Kasarani Community Hospital", "HOSPITAL", "Kasarani", "PUBLIC", -1.2219, 36.8984),
    ("10003", "Embakasi Health Centre", "HEALTH_CENTRE", "Embakasi East", "PUBLIC", -1.3197, 36.9051),
    ("10004", "Starehe Medical Centre", "CLINIC", "Starehe", "PRIVATE", -1.2833, 36.8333),
    ("10005", "Langata Family Clinic", "CLINIC", "Langata", "PRIVATE", -1.3369, 36.7651),
    ("20001", "Uhuru Pharmacy", "RETAIL_PHARMACY", "Westlands", "PRIVATE", -1.2675, 36.8108),
    ("20002", "Jamii Chemist", "RETAIL_PHARMACY", "Kasarani", "PRIVATE", -1.2206, 36.8925),
    ("20003", "Mtaa Pharmacy", "RETAIL_PHARMACY", "Embakasi East", "PRIVATE", -1.3156, 36.8992),
    ("20004", "Dawa Bora Pharmacy", "RETAIL_PHARMACY", "Starehe", "PRIVATE", -1.2841, 36.8262),
    ("20005", "Kibra Care Chemist", "RETAIL_PHARMACY", "Kibra", "PRIVATE", -1.3133, 36.7869),
    ("20006", "Roysambu Wellness Pharmacy", "RETAIL_PHARMACY", "Roysambu", "PRIVATE", -1.2185, 36.8853),
    ("20007", "Makadara Chemists", "RETAIL_PHARMACY", "Makadara", "PRIVATE", -1.2985, 36.8686),
]
PRESCRIBING_FACILITIES = ["10001", "10002", "10003", "10004", "10005"]
DISPENSING_FACILITIES = ["10001", "10002", "20001", "20002", "20003", "20004", "20005", "20006", "20007"]
NEARBY = {  # where patients registered at a prescribing facility usually collect medicines
    "10001": ["10001", "20001", "20005"], "10002": ["10002", "20002", "20006"], "10003": ["20003", "20007"],
    "10004": ["20004", "20007", "20001"], "10005": ["20005", "20004"],
}

FIRST_NAMES_F = ["Achieng", "Wanjiku", "Njeri", "Akinyi", "Wambui", "Chebet", "Mumbua", "Atieno", "Nyambura", "Jepkoech",
                 "Kerubo", "Moraa", "Wairimu", "Nafula", "Zawadi", "Amina", "Faith", "Mercy", "Grace", "Esther"]
FIRST_NAMES_M = ["Otieno", "Kamau", "Mwangi", "Kiprono", "Mutua", "Ochieng", "Kibet", "Omondi", "Njoroge", "Wekesa",
                 "Barasa", "Kiplagat", "Maina", "Odhiambo", "Juma", "Hassan", "Brian", "Kevin", "Dennis", "Peter"]
LAST_NAMES = ["Kariuki", "Odhiambo", "Mwangi", "Wanjala", "Kiptoo", "Mutiso", "Onyango", "Njoroge", "Chepkemoi", "Owino",
              "Kimani", "Nyaga", "Ruto", "Wafula", "Achieng", "Muthoni", "Gitau", "Okoth", "Kilonzo", "Mohamed",
              "Ndegwa", "Kosgei", "Atieno", "Macharia", "Langat", "Omollo", "Wambua", "Kirui", "Nduta", "Ouma"]


class Command(BaseCommand):
    help = "Seed synthetic Nairobi demo data (facilities, users, drugs, patients, 6 months of history)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing business data first")
        parser.add_argument("--patients", type=int, default=200)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts):
        self.rng = random.Random(opts["seed"])
        self.now = timezone.now()
        self.today = timezone.localdate()
        if opts["reset"]:
            self._reset()
        elif Facility.objects.exists():
            self.stdout.write(self.style.WARNING("Data already present. Use --reset to re-seed."))
            return

        self.password_hash = make_password(DEMO_PASSWORD)
        self._catalogue()
        self._facilities()
        self._practitioners_and_users()
        self._rule_configs()
        self._patients(opts["patients"])
        self.stdout.write("Generating 6 months of prescribing and dispensing history (runs the real alert engine)...")
        self._background_history()
        self._planted_stories()
        self._stock_receipts()
        self._summary()

    # ------------------------------------------------------------------ setup
    def _reset(self):
        self.stdout.write("Resetting business data...")
        for model in [Alert, Evaluation, RuleConfig, Dispense, Prescription, MedicationEvent, StockReceipt,
                      PatientIdentifier, Patient, MockRegistryRecord, Practitioner, Drug, DrugClass, OutboxEvent]:
            model.objects.all().delete()
        AuditEvent.objects.all()._raw_delete(AuditEvent.objects.db)
        User.objects.all().delete()
        Facility.objects.all().delete()

    def _catalogue(self):
        for code, name in DRUG_CLASSES:
            DrugClass.objects.create(code=code, name=name)
        self.drugs = {}
        self.typical = {}
        for key, name, generic, cls, strength, unit, form, mme, typical in DRUGS:
            self.drugs[key] = Drug.objects.create(
                name=name, generic_name=generic, drug_class_id=cls, strength_mg=Decimal(str(strength)), unit=unit,
                form=form, mme_factor=Decimal(str(mme)) if mme is not None else None, monitored=True,
            )
            self.typical[key] = typical

    def _facilities(self):
        self.fac = {}
        for code, name, ftype, sub, own, lat, lng in FACILITIES:
            self.fac[code] = Facility.objects.create(
                kmhfl_code=code, name=name, facility_type=ftype, sub_county=sub, ownership=own,
                ppb_licence_number=f"PPB/F/{code}", latitude=lat, longitude=lng, county_code=COUNTY,
            )

    def _user(self, email, name, role, licence="", cadre="", facility=None, **extra):
        if licence:
            regulator = {"MEDICAL_OFFICER": "KMPDC", "CLINICAL_OFFICER": "COC"}.get(cadre, "PPB")
            MockRegistryRecord.objects.update_or_create(kind="PRACTITIONER", key=licence, defaults={"data": {
                "licence_number": licence, "full_name": name, "cadre": cadre, "regulator": regulator, "status": "ACTIVE"}})
            Practitioner.objects.update_or_create(licence_number=licence, defaults={
                "full_name": name, "cadre": cadre, "regulator": regulator, "status": "ACTIVE"})
        u = User(email=email, full_name=name, role=role, licence_number=licence, cadre=cadre,
                 facility_id=facility.id if facility else None, county_code=COUNTY, status=User.Status.ACTIVE,
                 approved_at=self.now, **extra)
        u.password = self.password_hash
        u.save()
        return u

    def _practitioners_and_users(self):
        f = self.fac
        # ---- Named demo accounts ----
        self.dr_a = self._user("dr.achieng@demo.ke", "Dr. Achieng Odhiambo", "PRESCRIBER", "A10001", "MEDICAL_OFFICER", f["10001"])
        self.dr_b = self._user("dr.baraka@demo.ke", "Dr. Baraka Mwangi", "PRESCRIBER", "A10002", "MEDICAL_OFFICER", f["10002"])
        self.dr_kevin = self._user("dr.mutua@demo.ke", "Dr. Kevin Mutua", "PRESCRIBER", "A10003", "MEDICAL_OFFICER", f["10003"])
        self.ph_x = self._user("pharm.wambui@demo.ke", "Wambui Kariuki", "PHARMACIST", "PPB-20001", "PHARMACIST", f["20001"])
        self.ph_y = self._user("pharm.otieno@demo.ke", "Brian Otieno", "PHARMACIST", "PPB-20002", "PHARMACIST", f["20002"])
        self._user("facility.admin@demo.ke", "Lucy Wanjala", "FACILITY_ADMIN", facility=f["10001"])
        self._user("regulator@demo.ke", "Dr. Hassan Omar (County Pharmacist)", "REGULATOR")
        self._user("admin@demo.ke", "System Administrator", "SYSTEM_ADMIN", is_staff=True, is_superuser=True)

        # ---- Generated prescribers: 4 per prescribing facility (incl. the named ones) ----
        self.prescribers_by_fac = {code: [] for code in PRESCRIBING_FACILITIES}
        for u in (self.dr_a, self.dr_b, self.dr_kevin):
            self.prescribers_by_fac[next(c for c, fac in f.items() if fac.id == u.facility_id)].append(u)
        n = 4
        for code in PRESCRIBING_FACILITIES:
            while len(self.prescribers_by_fac[code]) < 4:
                n += 1
                is_doc = self.rng.random() < 0.6
                first = self.rng.choice(FIRST_NAMES_F + FIRST_NAMES_M)
                last = self.rng.choice(LAST_NAMES)
                name = f"Dr. {first} {last}" if is_doc else f"{first} {last} (CO)"
                licence = f"A1{n:04d}" if is_doc else f"CO-3{n:04d}"
                u = self._user(f"prescriber{n}@demo.ke", name, "PRESCRIBER", licence,
                               "MEDICAL_OFFICER" if is_doc else "CLINICAL_OFFICER", f[code])
                self.prescribers_by_fac[code].append(u)

        # ---- Generated pharmacists: at least one per dispensing facility, 15 total ----
        self.pharmacists_by_fac = {code: [] for code in DISPENSING_FACILITIES}
        self.pharmacists_by_fac["20001"].append(self.ph_x)
        self.pharmacists_by_fac["20002"].append(self.ph_y)
        n = 2
        targets = [c for c in DISPENSING_FACILITIES if c not in ("20001", "20002")] + ["10001", "10002", "20003", "20004", "20001", "20002"]
        for code in targets:
            n += 1
            name = f"{self.rng.choice(FIRST_NAMES_F + FIRST_NAMES_M)} {self.rng.choice(LAST_NAMES)}"
            u = self._user(f"pharmacist{n}@demo.ke", name, "PHARMACIST", f"PPB-2{n:04d}", "PHARMACIST", f[code])
            self.pharmacists_by_fac[code].append(u)

        # ---- Registry-only practitioners (for the self-registration demo) ----
        for licence, name, cadre, status in [
            ("A19999", "Dr. Faith Njoki", "MEDICAL_OFFICER", "ACTIVE"),
            ("PPB-29999", "Samuel Kiptoo", "PHARMACIST", "ACTIVE"),
            ("A18888", "Dr. Suspended Example", "MEDICAL_OFFICER", "SUSPENDED"),
        ]:
            MockRegistryRecord.objects.create(kind="PRACTITIONER", key=licence, data={
                "licence_number": licence, "full_name": name, "cadre": cadre,
                "regulator": "PPB" if cadre == "PHARMACIST" else "KMPDC", "status": status})

    def _rule_configs(self):
        for rule in RULES:
            RuleConfig.objects.get_or_create(code=rule.code, defaults={"params": {}})

    # ------------------------------------------------------------------ patients
    def _new_patient(self, first, last, sex, dob, national_id, local=True, middle=""):
        cr_id = f"CR{national_id}{self.rng.randint(10, 99)}"
        data = {"cr_id": cr_id, "first_name": first, "middle_name": middle, "last_name": last,
                "date_of_birth": dob.isoformat(), "sex": sex, "phone": f"07{self.rng.randint(10000000, 99999999)}"}
        MockRegistryRecord.objects.create(kind="CLIENT", key=f"NATIONAL_ID:{national_id}", data=data)
        if not local:
            return None
        p = Patient.objects.create(cr_id=cr_id, first_name=first, middle_name=middle, last_name=last, date_of_birth=dob,
                                   sex=sex, phone=data["phone"], verified=True, county_code=COUNTY)
        PatientIdentifier.objects.create(patient=p, id_type="NATIONAL_ID", value=str(national_id))
        return p

    def _random_person(self):
        sex = self.rng.choice(["F", "M"])
        first = self.rng.choice(FIRST_NAMES_F if sex == "F" else FIRST_NAMES_M)
        dob = self.today - timedelta(days=self.rng.randint(18 * 365, 80 * 365))
        return first, self.rng.choice(LAST_NAMES), sex, dob

    def _patients(self, count):
        reserved = {23456789, 34567890, 30000001}
        used = set(reserved)

        def new_id():
            while True:
                v = self.rng.randint(20000000, 39999999)
                if v not in used:
                    used.add(v)
                    return v

        self.patients = []
        for _ in range(count):
            first, last, sex, dob = self._random_person()
            p = self._new_patient(first, last, sex, dob, new_id())
            p.home = self.rng.choice(PRESCRIBING_FACILITIES)
            self.patients.append(p)
        for _ in range(40):  # people in the Client Registry with no local record yet
            first, last, sex, dob = self._random_person()
            self._new_patient(first, last, sex, dob, new_id(), local=False)

        # Planted patients
        self.peter = self._new_patient("Peter", "Kamau", "M", self.today.replace(year=self.today.year - 34), 23456789, middle="Njuguna")
        self.mary = self._new_patient("Mary", "Njeri", "F", self.today.replace(year=self.today.year - 58), 34567890, middle="Wairimu")
        self._new_patient("Grace", "Wanjiku", "F", self.today.replace(year=self.today.year - 29), 30000001, local=False)

    # ------------------------------------------------------------------ history helpers
    @staticmethod
    def _actor(u, purpose):
        return {"id": str(u.id), "role": u.role, "full_name": u.full_name, "licence_number": u.licence_number,
                "facility_id": str(u.facility_id) if u.facility_id else None, "county_code": u.county_code,
                "ip": "seed", "purpose": purpose}

    def _at(self, day, hour=None):
        hour = hour if hour is not None else self.rng.randint(8, 18)
        return timezone.make_aware(datetime.combine(day, time(hour, self.rng.randint(0, 59))))

    @staticmethod
    def _ack_all(evaluation, note="Seeded history"):
        acks = []
        for f in evaluation["findings"]:
            acks.append({"rule_code": f["rule_code"], "reason": "CLINICALLY_JUSTIFIED", "note": note,
                         "referral": f["severity"] == "CRITICAL" and f["rule_code"] in ("MULTIPLE_PRESCRIBERS", "MULTIPLE_PHARMACIES")})
        return acks

    def _prescribe(self, prescriber, patient, drug_key, day, qty=None, days=None, refills=0):
        tq, td, instr = self.typical[drug_key]
        data = {"patient_id": str(patient.id), "drug_id": str(self.drugs[drug_key].id), "dosage_instructions": instr,
                "quantity": Decimal(str(qty or tq)), "days_supply": days or td, "refills_allowed": refills}
        actor = self._actor(prescriber, "PRESCRIBING")
        when = self._at(day)
        ev = prescriptions.preview(data, actor, as_of=day)
        return prescriptions.create(data, actor, acknowledgements=self._ack_all(ev), issued_at=when)

    def _dispense_rx(self, pharmacist, rx, day, qty=None):
        data = {"prescription_id": str(rx.id), "quantity": Decimal(str(qty or rx.quantity)),
                "batch_number": f"B{self.rng.randint(1000, 9999)}"}
        actor = self._actor(pharmacist, "DISPENSING")
        when = self._at(day)
        _, proposal, _ = dispensing.build_proposal(data, actor, now=when)
        # Evaluate exactly as the preview endpoint would, then acknowledge everything for seeded history.
        ev = alerts.evaluate(action="DISPENSE", patient_id=str(rx.patient_id), proposed=proposal, actor=actor, as_of=day)
        return dispensing.commit(data, actor, acknowledgements=self._ack_all(ev), dispensed_at=when)

    def _dispense_paper(self, pharmacist, patient, drug_key, day, prescriber_name, licence, qty=None, days=None):
        tq, td, _ = self.typical[drug_key]
        data = {"patient_id": str(patient.id), "drug_id": str(self.drugs[drug_key].id), "quantity": Decimal(str(qty or tq)),
                "days_supply": days or td, "paper_prescriber_name": prescriber_name, "paper_prescriber_licence": licence,
                "paper_rx_date": day - timedelta(days=1), "paper_rx_number": f"PR{self.rng.randint(10000, 99999)}"}
        actor = self._actor(pharmacist, "DISPENSING")
        when = self._at(day)
        _, proposal, _ = dispensing.build_proposal(data, actor, now=when)
        ev = alerts.evaluate(action="DISPENSE", patient_id=str(patient.id), proposed=proposal, actor=actor, as_of=day)
        return dispensing.commit(data, actor, acknowledgements=self._ack_all(ev), dispensed_at=when)

    def _pharmacist_at(self, code):
        return self.rng.choice(self.pharmacists_by_fac[code])

    # ------------------------------------------------------------------ background history
    def _background_history(self):
        keys, weights = zip(*OUTPATIENT_WEIGHTS.items())
        start_window = self.today - timedelta(days=178)
        for i, patient in enumerate(self.patients):
            if self.rng.random() < 0.12:
                continue  # some registered patients have no recent monitored-drug history
            day = start_window + timedelta(days=self.rng.randint(0, 60))
            for _ in range(self.rng.randint(1, 4)):
                if day >= self.today - timedelta(days=2):
                    break
                drug_key = self.rng.choices(keys, weights)[0]
                home = patient.home
                prescriber = self.rng.choice(self.prescribers_by_fac[home])
                qty = None
                if drug_key == "tramadol50" and self.rng.random() < 0.45:
                    prescriber, qty = self.dr_kevin, 90  # high-volume tramadol prescriber
                elif self.rng.random() < 0.06:
                    other = self.rng.choice([c for c in PRESCRIBING_FACILITIES if c != home])
                    prescriber = self.rng.choice(self.prescribers_by_fac[other])  # occasional second opinion
                pharmacy = self.rng.choice(NEARBY[home])
                tq, td, _ = self.typical[drug_key]
                qty = qty or tq
                days = td * qty // tq
                if self.rng.random() < 0.15:
                    # Paper prescription dispensed directly (no e-prescription in the system)
                    licence = prescriber.licence_number if self.rng.random() < 0.9 else f"A0{self.rng.randint(1000, 9999)}"
                    self._dispense_paper(self._pharmacist_at(pharmacy), patient, drug_key, day, prescriber.full_name, licence, qty, days)
                    day = day + timedelta(days=days + self.rng.randint(10, 45))
                    continue
                refills = 1 if (days <= 14 and self.rng.random() < 0.3) else 0
                rx = self._prescribe(prescriber, patient, drug_key, day, qty, days, refills)
                disp_day = day + timedelta(days=self.rng.choice([0, 0, 0, 1]))
                if disp_day >= self.today:
                    continue
                self._dispense_rx(self._pharmacist_at(pharmacy), rx, disp_day)
                end = disp_day + timedelta(days=days)
                if refills and end - timedelta(days=1) < self.today:
                    self._dispense_rx(self._pharmacist_at(pharmacy), rx, end - timedelta(days=1))
                    end = end + timedelta(days=days)
                day = end + timedelta(days=self.rng.randint(10, 45))
            if (i + 1) % 50 == 0:
                self.stdout.write(f"  {i + 1} patients done")

    # ------------------------------------------------------------------ planted demo stories
    def _planted_stories(self):
        t = self.today
        # Story 1: Peter Kamau, "doctor shopper": 4 prescribers and 3 pharmacies in the last 4 weeks,
        # plus an undispensed tramadol prescription from Dr. Baraka (Pharmacy X will dispense it live).
        shop = [
            (self.prescribers_by_fac["10004"][0], "20004", 27),
            (self.prescribers_by_fac["10005"][0], "20005", 20),
            (self.dr_kevin, "20003", 13),
            (self.prescribers_by_fac["10001"][1], "20004", 6),
        ]
        for prescriber, pharmacy, ago in shop:
            rx = self._prescribe(prescriber, self.peter, "tramadol50", t - timedelta(days=ago + 1))
            self._dispense_rx(self._pharmacist_at(pharmacy), rx, t - timedelta(days=ago))
        self.peter_rx = self._prescribe(self.dr_b, self.peter, "tramadol50", t - timedelta(days=1))

        # Story 2: Mary Njeri, high-dose morphine (60 MME/day) dispensed 5 days ago; a diazepam
        # prescription from another clinic is waiting -> dispensing it triggers OPIOID_BENZO_OVERLAP.
        rx = self._prescribe(self.dr_a, self.mary, "morphine10", t - timedelta(days=6), qty=180, days=30)
        self._dispense_rx(self._pharmacist_at("10001"), rx, t - timedelta(days=5))
        self.mary_rx = self._prescribe(self.prescribers_by_fac["10004"][1], self.mary, "diazepam5", t - timedelta(days=1))

        # Story 3: a couple of earlier shopping patterns elsewhere so the dashboard has flagged patients.
        for p in self.rng.sample(self.patients, 3):
            base = t - timedelta(days=self.rng.randint(35, 120))
            for j, code in enumerate(self.rng.sample(PRESCRIBING_FACILITIES, 4)):
                day = base + timedelta(days=j * 4)
                rx = self._prescribe(self.rng.choice(self.prescribers_by_fac[code]), p, "tramadol50", day)
                self._dispense_rx(self._pharmacist_at(self.rng.choice(DISPENSING_FACILITIES)), rx, day)

    # ------------------------------------------------------------------ supply (mock track-and-trace)
    def _stock_receipts(self):
        """Receipts roughly cover what was dispensed (+10-30%), except Mtaa Pharmacy's tramadol (planted gap)."""
        start = self.today - timedelta(days=182)
        rows = history.dispensed_quantity_by_facility_drug(COUNTY, start, self.today)
        mtaa = str(self.fac["20003"].id)
        tramadol = str(self.drugs["tramadol50"].id)
        for r in rows:
            factor = 0.4 if (r["facility_id"] == mtaa and r["drug_id"] == tramadol) else self.rng.uniform(1.1, 1.3)
            total = max(10, round(r["quantity"] * factor / 10) * 10)
            parts = self.rng.randint(1, 3)
            for k in range(parts):
                StockReceipt.objects.create(
                    facility_id=r["facility_id"], drug_id=r["drug_id"], quantity=Decimal(total // parts),
                    batch_number=f"LOT{self.rng.randint(10000, 99999)}", gtin=f"0614{self.rng.randint(100000000, 999999999)}",
                    supplier_name=self.rng.choice(["MEDS Kenya", "KEMSA", "Nairobi Pharma Distributors"]),
                    received_at=self._at(start + timedelta(days=5 + k * 55)), source="MOCK_TT", county_code=COUNTY,
                )

    def _summary(self):
        self.stdout.write(self.style.SUCCESS(
            f"\nSeeded: {Facility.objects.count()} facilities, {User.objects.count()} users, {Drug.objects.count()} drugs, "
            f"{Patient.objects.count()} patients, {Prescription.objects.count()} prescriptions, "
            f"{Dispense.objects.count()} dispenses, {Alert.objects.count()} alerts, {AuditEvent.objects.count()} audit events."
        ))
        self.stdout.write(f"\nDemo password for every account: {DEMO_PASSWORD}")
        for email in ["dr.achieng@demo.ke", "dr.baraka@demo.ke", "pharm.wambui@demo.ke", "pharm.otieno@demo.ke",
                      "regulator@demo.ke", "facility.admin@demo.ke", "admin@demo.ke"]:
            u = User.objects.get(email=email)
            self.stdout.write(f"  {email:26} {u.role:15} {u.full_name}")
        self.stdout.write("\nDemo patients (National ID):")
        self.stdout.write("  30000001  Grace Wanjiku  - only in the Client Registry; clean history (demo steps 1-2)")
        self.stdout.write(f"  23456789  Peter Kamau    - doctor shopper; e-prescription {self.peter_rx.code} waiting (steps 3-4)")
        self.stdout.write(f"  34567890  Mary Njeri     - high-dose morphine; diazepam prescription {self.mary_rx.code} waiting")

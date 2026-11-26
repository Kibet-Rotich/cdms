"""End-to-end API test of the hackathon demo flow (prescribe -> alert -> dispense -> block -> oversight)."""
from django.core.management import call_command
from django.test import TransactionTestCase
from rest_framework.test import APIClient


class DemoFlowTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def setUp(self):
        call_command("seed_demo", patients=20, verbosity=0, stdout=open("/dev/null", "w"))

    def client_for(self, email, purpose):
        c = APIClient()
        r = c.post("/api/v1/auth/login", {"email": email, "password": "Demo@1234"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}", HTTP_X_PURPOSE_OF_USE=purpose)
        return c

    def test_demo_flow(self):
        dr_a = self.client_for("dr.achieng@demo.ke", "PRESCRIBING")
        dr_b = self.client_for("dr.baraka@demo.ke", "PRESCRIBING")
        ph_x = self.client_for("pharm.wambui@demo.ke", "DISPENSING")
        ph_y = self.client_for("pharm.otieno@demo.ke", "DISPENSING")
        reg = self.client_for("regulator@demo.ke", "OVERSIGHT")

        # Purpose of use is mandatory for patient data
        no_purpose = APIClient()
        no_purpose.credentials(HTTP_AUTHORIZATION=dr_a._credentials["HTTP_AUTHORIZATION"])
        self.assertEqual(no_purpose.get("/api/v1/patients/search?idType=NATIONAL_ID&idNumber=30000001").status_code, 403)

        # 1. Grace is pulled from the Client Registry; Dr A prescribes tramadol with no alerts
        r = dr_a.get("/api/v1/patients/search?idType=NATIONAL_ID&idNumber=30000001")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["source"], "CLIENT_REGISTRY")
        grace = r.json()["patient"]["id"]
        tramadol = next(d["id"] for d in dr_a.get("/api/v1/drugs").json() if d["generic_name"] == "Tramadol")
        rx = {"patient_id": grace, "drug_id": tramadol, "dosage_instructions": "1 cap TDS", "quantity": 30, "days_supply": 10}
        r = dr_a.post("/api/v1/prescriptions/preview", rx, format="json")
        self.assertEqual(r.json()["findings"], [])
        r = dr_a.post("/api/v1/prescriptions", rx, format="json")
        self.assertEqual(r.status_code, 201, r.content)

        # 2. Dr B prescribes the same class -> DUPLICATE_THERAPY; commit without acknowledgement is rejected
        r = dr_b.post("/api/v1/prescriptions/preview", rx, format="json")
        self.assertIn("DUPLICATE_THERAPY", [f["rule_code"] for f in r.json()["findings"]])
        ev = r.json()["evaluation_id"]
        r = dr_b.post("/api/v1/prescriptions", {**rx, "evaluation_id": ev}, format="json")
        self.assertEqual(r.status_code, 422)
        acks = [{"rule_code": "DUPLICATE_THERAPY", "reason": "VERIFIED_WITH_PRESCRIBER"}]
        r = dr_b.post("/api/v1/prescriptions", {**rx, "evaluation_id": ev, "acknowledgements": acks}, format="json")
        self.assertEqual(r.status_code, 201, r.content)

        # 3. Pharmacy X dispenses Peter's waiting prescription -> critical shopping alerts
        r = ph_x.get("/api/v1/patients/search?idType=NATIONAL_ID&idNumber=23456789")
        peter = r.json()["patient"]["id"]
        code = next(p["code"] for p in ph_x.get(f"/api/v1/patients/{peter}/prescriptions?status=ACTIVE").json())
        r = ph_x.post("/api/v1/dispenses/preview", {"prescription_code": code, "quantity": 30}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        findings = {f["rule_code"]: f["severity"] for f in r.json()["findings"]}
        self.assertEqual(findings.get("MULTIPLE_PHARMACIES"), "CRITICAL")
        self.assertEqual(findings.get("MULTIPLE_PRESCRIBERS"), "CRITICAL")
        acks = [{"rule_code": c, "reason": "CLINICALLY_JUSTIFIED", "referral": True} for c in findings]
        r = ph_x.post("/api/v1/dispenses", {"prescription_code": code, "quantity": 30, "evaluation_id": r.json()["evaluation_id"],
                                            "acknowledgements": acks}, format="json", HTTP_IDEMPOTENCY_KEY="k1")
        self.assertEqual(r.status_code, 201, r.content)

        # 4. Pharmacy Y tries the same prescription -> hard block
        r = ph_y.post("/api/v1/dispenses/preview", {"prescription_code": code, "quantity": 30}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "PRESCRIPTION_ALREADY_DISPENSED")

        # 5. Regulator dashboard and flagged patients
        self.assertEqual(reg.get("/api/v1/oversight/summary").status_code, 200)
        self.assertEqual(reg.get("/api/v1/oversight/outliers/prescribers").status_code, 200)
        flagged = reg.get("/api/v1/oversight/flagged-patients").json()["items"]
        self.assertTrue(flagged)
        r = reg.post(f"/api/v1/oversight/flagged-patients/{flagged[0]['ref']}/reveal", {"reason": "Investigation INV-001"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        recon = reg.get("/api/v1/oversight/supply-reconciliation").json()["items"]
        self.assertTrue(any(i["flag"] for i in recon))

        # 6. Audit log is intact and records the reveal
        self.assertTrue(reg.get("/api/v1/audit-events/verify").json()["intact"])
        self.assertTrue(reg.get("/api/v1/audit-events?action=REVEAL").json()["items"])
        # Clinicians cannot see the dashboard
        self.assertEqual(ph_x.get("/api/v1/oversight/summary").status_code, 403)

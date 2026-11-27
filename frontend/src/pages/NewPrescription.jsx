import { QRCodeSVG } from "qrcode.react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { get, newIdempotencyKey, post } from "../api";
import AlertReview from "../components/AlertReview";

export default function NewPrescription() {
  const { id } = useParams();
  const [patient, setPatient] = useState(null);
  const [drugs, setDrugs] = useState([]);
  const [form, setForm] = useState({ drug_id: "", dosage_instructions: "", quantity: "", days_supply: "", refills_allowed: 0, diagnosis_note: "", notes: "" });
  const [step, setStep] = useState("form"); // form -> review -> done
  const [preview, setPreview] = useState(null);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    get(`/patients/${id}`).then(setPatient).catch((e) => setError(e.message));
    get("/drugs?monitored=true").then(setDrugs);
  }, [id]);

  const body = () => ({ ...form, patient_id: id, quantity: Number(form.quantity), days_supply: Number(form.days_supply), refills_allowed: Number(form.refills_allowed) });

  const runPreview = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(await post("/prescriptions/preview", body()));
      setKey(newIdempotencyKey());
      setStep("review");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const commit = async (acknowledgements) => {
    setBusy(true);
    setError("");
    try {
      const rx = await post("/prescriptions", { ...body(), evaluation_id: preview.evaluation_id, acknowledgements }, { "Idempotency-Key": key });
      setCreated(rx);
      setStep("done");
    } catch (err) {
      if (err.code === "ALERTS_NOT_ACKNOWLEDGED") {
        setPreview({ ...preview, findings: err.body.findings });
        setError("The patient's history changed since the preview. Review the updated alerts.");
      } else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const drug = drugs.find((d) => d.id === form.drug_id);

  return (
    <div className="stack" style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1>New prescription</h1>
          <p>{patient ? <Link to={`/patients/${id}`}>{patient.full_name}</Link> : "…"}</p>
        </div>
      </div>
      {error && <div className="banner error">{error}</div>}

      {step === "form" && (
        <form className="card" onSubmit={runPreview}>
          <div className="form-grid">
            <label className="field" style={{ gridColumn: "1 / -1" }}>
              Monitored medicine
              <select value={form.drug_id} onChange={set("drug_id")} required>
                <option value="">Select…</option>
                {drugs.map((d) => (
                  <option key={d.id} value={d.id}>{d.name} ({d.class_name})</option>
                ))}
              </select>
            </label>
            <label className="field" style={{ gridColumn: "1 / -1" }}>
              Dosage instructions
              <input value={form.dosage_instructions} onChange={set("dosage_instructions")} placeholder="e.g. 1 capsule three times daily" required />
            </label>
            <label className="field">Quantity ({drug ? drug.unit.toLowerCase() + "s" : "units"})<input type="number" min="1" value={form.quantity} onChange={set("quantity")} required /></label>
            <label className="field">Days' supply<input type="number" min="1" max="180" value={form.days_supply} onChange={set("days_supply")} required /></label>
            <label className="field">
              Refills
              <select value={form.refills_allowed} onChange={set("refills_allowed")}>
                {[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label className="field">Diagnosis / indication<input value={form.diagnosis_note} onChange={set("diagnosis_note")} /></label>
          </div>
          <div className="form-actions">
            <button className="primary" disabled={busy}>{busy ? "Checking…" : "Check & continue"}</button>
            <Link className="btn" to={`/patients/${id}`}>Cancel</Link>
          </div>
        </form>
      )}

      {step === "review" && preview && (
        <div className="card">
          <div className="card-head"><h2>Safety check</h2><p>{drug?.name} · {form.quantity} units · {form.days_supply} days</p></div>
          <AlertReview findings={preview.findings} onConfirm={commit} onBack={() => setStep("form")} confirmLabel="Issue prescription" busy={busy} />
        </div>
      )}

      {step === "done" && created && (
        <div className="card">
          <div className="banner ok" style={{ marginBottom: 16 }}>Prescription issued. Give the patient this code or QR.</div>
          <div className="row" style={{ gap: 24, alignItems: "flex-start" }}>
            <div className="qr"><QRCodeSVG value={created.code} size={150} /></div>
            <div>
              <div className="code-big mono">{created.code}</div>
              <p>{created.drug?.name}<br />{created.dosage_instructions}<br />Qty {Number(created.quantity)} · {created.days_supply} days · {created.refills_allowed} refill(s)</p>
              <p className="muted small">Valid until {new Date(created.expires_at).toLocaleDateString("en-KE")}. Can be dispensed at any pharmacy in the county.</p>
              <Link className="btn primary" to={`/patients/${id}`}>Back to patient</Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

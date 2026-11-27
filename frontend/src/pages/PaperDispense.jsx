import { useEffect, useState } from "react";
import { get, newIdempotencyKey, post } from "../api";
import AlertReview from "../components/AlertReview";

/** Record a dispense against a paper prescription (most prescriptions in Kenya are still on paper). */
export default function PaperDispense({ patient, onDone }) {
  const [drugs, setDrugs] = useState([]);
  const [form, setForm] = useState({
    drug_id: "", quantity: "", days_supply: "", paper_prescriber_name: "", paper_prescriber_licence: "",
    paper_prescriber_facility: "", paper_rx_date: new Date().toISOString().slice(0, 10), paper_rx_number: "", batch_number: "",
  });
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    get("/drugs?monitored=true").then(setDrugs);
  }, []);

  const body = () => ({ ...form, patient_id: patient.id, quantity: Number(form.quantity), days_supply: Number(form.days_supply) });

  const runPreview = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(await post("/dispenses/preview", body()));
      setKey(newIdempotencyKey());
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
      await post("/dispenses", { ...body(), evaluation_id: preview.evaluation_id, acknowledgements }, { "Idempotency-Key": key });
      onDone();
    } catch (err) {
      if (err.code === "ALERTS_NOT_ACKNOWLEDGED") setPreview({ ...preview, findings: err.body.findings });
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="card-head">
        <h2>Paper prescription</h2>
        <p>The prescriber's licence is checked against the practitioner registry.</p>
      </div>
      {error && <div className="banner error" style={{ marginBottom: 12 }}>{error}</div>}
      {preview ? (
        <AlertReview findings={preview.findings} onConfirm={commit} onBack={() => setPreview(null)} confirmLabel="Record dispense" busy={busy} />
      ) : (
        <form onSubmit={runPreview}>
          <div className="form-grid">
            <label className="field" style={{ gridColumn: "1 / -1" }}>
              Medicine
              <select value={form.drug_id} onChange={set("drug_id")} required>
                <option value="">Select…</option>
                {drugs.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
            <label className="field">Quantity<input type="number" min="1" value={form.quantity} onChange={set("quantity")} required /></label>
            <label className="field">Days' supply<input type="number" min="1" value={form.days_supply} onChange={set("days_supply")} required /></label>
            <label className="field">Prescriber name<input value={form.paper_prescriber_name} onChange={set("paper_prescriber_name")} required /></label>
            <label className="field">Prescriber licence no.<input value={form.paper_prescriber_licence} onChange={set("paper_prescriber_licence")} placeholder="e.g. A10004" required /></label>
            <label className="field">Prescriber's facility<input value={form.paper_prescriber_facility} onChange={set("paper_prescriber_facility")} /></label>
            <label className="field">Prescription date<input type="date" value={form.paper_rx_date} onChange={set("paper_rx_date")} required /></label>
            <label className="field">Prescription number<input value={form.paper_rx_number} onChange={set("paper_rx_number")} /></label>
            <label className="field">Batch number<input value={form.batch_number} onChange={set("batch_number")} /></label>
          </div>
          <div className="form-actions">
            <button className="primary" disabled={busy}>{busy ? "Checking…" : "Check & continue"}</button>
          </div>
        </form>
      )}
    </div>
  );
}

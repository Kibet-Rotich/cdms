import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { get, newIdempotencyKey, post } from "../api";
import AlertReview from "../components/AlertReview";
import { fmtDate, fmtNum } from "../format";

/** Dispense against an e-prescription code (typed or scanned from the QR). */
export default function Dispense() {
  const [params] = useSearchParams();
  const [code, setCode] = useState(params.get("code") || "");
  const [rx, setRx] = useState(null);
  const [quantity, setQuantity] = useState("");
  const [batch, setBatch] = useState("");
  const [step, setStep] = useState("find"); // find -> details -> review -> done | blocked
  const [preview, setPreview] = useState(null);
  const [blocked, setBlocked] = useState(null);
  const [done, setDone] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(null);

  const find = async (e, c = code) => {
    e?.preventDefault();
    setError("");
    setBlocked(null);
    setBusy(true);
    try {
      const p = await get(`/prescriptions/by-code/${encodeURIComponent(c.trim().toUpperCase())}`);
      setRx(p);
      // If nothing remains, keep the full fill quantity so the server check runs and explains the block.
      const remaining = Number(p.remaining_quantity);
      setQuantity(String(remaining > 0 ? Math.min(Number(p.quantity), remaining) : Number(p.quantity)));
      setStep("details");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (params.get("code")) find(null, params.get("code"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const body = () => ({ prescription_code: rx.code, quantity: Number(quantity), batch_number: batch });

  const runPreview = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setPreview(await post("/dispenses/preview", body()));
      setKey(newIdempotencyKey());
      setStep("review");
    } catch (err) {
      if (err.status === 409) {
        setBlocked(err.body);
        setStep("blocked");
      } else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const commit = async (acknowledgements) => {
    setBusy(true);
    setError("");
    try {
      setDone(await post("/dispenses", { ...body(), evaluation_id: preview.evaluation_id, acknowledgements }, { "Idempotency-Key": key }));
      setStep("done");
    } catch (err) {
      if (err.status === 409) {
        setBlocked(err.body);
        setStep("blocked");
      } else if (err.code === "ALERTS_NOT_ACKNOWLEDGED") {
        setPreview({ ...preview, findings: err.body.findings });
        setError("The patient's history changed since the check. Review the updated alerts.");
      } else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setStep("find");
    setRx(null);
    setCode("");
    setPreview(null);
    setBlocked(null);
    setDone(null);
  };

  return (
    <div className="stack" style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1>Dispense</h1>
          <p>Enter the prescription code from the patient's slip or QR.</p>
        </div>
      </div>
      {error && <div className="banner error">{error}</div>}

      {step === "find" && (
        <form className="card row" onSubmit={find}>
          <label className="field" style={{ flex: 1 }}>
            Prescription code
            <input className="mono" value={code} onChange={(e) => setCode(e.target.value)} placeholder="RX-XXXXXXX" required autoFocus />
          </label>
          <button className="primary" style={{ alignSelf: "flex-end" }} disabled={busy}>Find</button>
        </form>
      )}

      {rx && step !== "find" && step !== "blocked" && (
        <div className="card">
          <div className="card-head">
            <h2 className="mono">{rx.code}</h2>
            <Link to={`/patients/${rx.patient_id}`}>Open patient history →</Link>
          </div>
          <table>
            <tbody>
              <tr><th>Medicine</th><td>{rx.drug?.name}<div className="muted small">{rx.dosage_instructions}</div></td></tr>
              <tr><th>Prescriber</th><td>{rx.prescriber_name} <span className="muted mono small">{rx.prescriber_licence}</span><div className="muted small">{rx.facility?.name}</div></td></tr>
              <tr><th>Issued</th><td>{fmtDate(rx.issued_at)} (valid until {fmtDate(rx.expires_at)})</td></tr>
              <tr><th>Status</th><td>{rx.status} · {fmtNum(rx.quantity_dispensed)} of {fmtNum(Number(rx.quantity) * (rx.refills_allowed + 1))} dispensed</td></tr>
            </tbody>
          </table>
        </div>
      )}

      {step === "details" && rx && (
        <form className="card" onSubmit={runPreview}>
          <div className="form-grid">
            <label className="field">Quantity to dispense<input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /></label>
            <label className="field">Batch number (optional)<input value={batch} onChange={(e) => setBatch(e.target.value)} /></label>
          </div>
          <div className="form-actions">
            <button className="primary" disabled={busy}>{busy ? "Checking…" : "Check & continue"}</button>
            <button type="button" onClick={reset}>Cancel</button>
          </div>
        </form>
      )}

      {step === "review" && preview && (
        <div className="card">
          <div className="card-head"><h2>Safety check</h2><p>Checked against the patient's history at every facility in the county</p></div>
          <AlertReview findings={preview.findings} onConfirm={commit} onBack={() => setStep("details")} confirmLabel="Record dispense" busy={busy} />
        </div>
      )}

      {step === "blocked" && blocked && (
        <div className="banner block">
          <h2>Cannot dispense</h2>
          <p>{blocked.detail}</p>
          {blocked.prescription && (
            <p className="small">
              {blocked.prescription.code}: {fmtNum(blocked.prescription.quantity_dispensed)} units already dispensed against this prescription.
              Possible duplicate redemption (photocopied or reused slip).
            </p>
          )}
          <button onClick={reset}>Start again</button>
        </div>
      )}

      {step === "done" && done && (
        <div className="banner ok">
          <strong>Dispense recorded.</strong> {fmtNum(done.quantity)} × {done.drug?.name} at {done.facility?.name}. The patient's history is
          updated for every pharmacy and prescriber in the county.
          <div className="form-actions">
            <button onClick={reset}>Dispense another</button>
            <Link className="btn" to={`/patients/${done.patient_id}`}>View patient</Link>
          </div>
        </div>
      )}
    </div>
  );
}

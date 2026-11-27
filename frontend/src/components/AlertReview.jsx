import { useState } from "react";
import { ACK_REASONS } from "../format";

/**
 * Shows the alert findings from a `preview` call. Every finding must be acknowledged with a reason
 * (and a note for OTHER) before the user can continue. Alerts are advisory: the user decides.
 */
export default function AlertReview({ findings, onConfirm, onBack, confirmLabel, busy }) {
  const [acks, setAcks] = useState(() =>
    Object.fromEntries(findings.map((f) => [f.rule_code, { reason: "", note: "", referral: false }]))
  );
  const set = (code, patch) => setAcks((a) => ({ ...a, [code]: { ...a[code], ...patch } }));
  const complete = findings.every((f) => acks[f.rule_code].reason && (acks[f.rule_code].reason !== "OTHER" || acks[f.rule_code].note.trim()));

  if (findings.length === 0) {
    return (
      <div className="stack">
        <div className="banner ok">
          <strong>No alerts.</strong> Nothing in this patient's monitored-medicine history needs attention.
        </div>
        <div className="form-actions">
          <button className="primary" onClick={() => onConfirm([])} disabled={busy}>{confirmLabel}</button>
          <button onClick={onBack} disabled={busy}>Back</button>
        </div>
      </div>
    );
  }

  const critical = findings.filter((f) => f.severity === "CRITICAL").length;
  return (
    <div className="stack">
      <div className={`banner ${critical ? "error" : ""}`}>
        <strong>{findings.length} alert{findings.length > 1 ? "s" : ""}</strong>
        {critical ? `, ${critical} critical` : ""}. Review each one and record why you are proceeding. These alerts are
        advisory: the decision is yours, and it will be logged.
      </div>
      {findings.map((f) => (
        <div key={f.rule_code} className={`finding ${f.severity}`}>
          <div className="row">
            <span className={`sev ${f.severity}`}>{f.severity}</span>
            <strong>{f.title}</strong>
            <span className="muted small mono">{f.rule_code}</span>
          </div>
          <p>{f.message}</p>
          <div className="form-grid">
            <label className="field">
              Reason for proceeding
              <select value={acks[f.rule_code].reason} onChange={(e) => set(f.rule_code, { reason: e.target.value })}>
                <option value="">Select a reason…</option>
                {ACK_REASONS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Note {acks[f.rule_code].reason === "OTHER" ? "(required)" : "(optional)"}
              <input value={acks[f.rule_code].note} onChange={(e) => set(f.rule_code, { note: e.target.value })} />
            </label>
          </div>
          <label className="row small" style={{ marginTop: 8 }}>
            <input type="checkbox" checked={acks[f.rule_code].referral} onChange={(e) => set(f.rule_code, { referral: e.target.checked })} />
            Patient referred for support (counselling / addiction services)
          </label>
        </div>
      ))}
      <div className="form-actions">
        <button
          className="primary"
          disabled={!complete || busy}
          onClick={() => onConfirm(findings.map((f) => ({ rule_code: f.rule_code, ...acks[f.rule_code] })))}
        >
          Acknowledge & {confirmLabel.toLowerCase()}
        </button>
        <button onClick={onBack} disabled={busy}>Back</button>
      </div>
    </div>
  );
}

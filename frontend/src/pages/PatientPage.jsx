import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { get } from "../api";
import { useAuth } from "../auth";
import SupplyTimeline from "../components/SupplyTimeline";
import PaperDispense from "./PaperDispense";
import { fmtDate, fmtDateTime, fmtNum, titleCase } from "../format";

export default function PatientPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const location = useLocation();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [showPaper, setShowPaper] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      get(`/patients/${id}`),
      get(`/patients/${id}/medication-summary`),
      get(`/patients/${id}/medication-history`),
      get(`/patients/${id}/prescriptions?status=ACTIVE`),
      get(`/alerts?patientId=${id}&pageSize=10`),
    ])
      .then(([patient, summary, historyRes, openRx, alerts]) => {
        if (!cancelled) setData({ patient, summary, history: historyRes.items, openRx, alerts: alerts.items });
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [id, tick]);

  if (error) return <div className="banner error">{error}</div>;
  if (!data) return <p className="muted">Loading patient…</p>;
  const { patient, summary, history, openRx, alerts } = data;
  const mme = summary.total_daily_mme;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>{patient.full_name}</h1>
          <p className="row">
            <span>{patient.sex === "F" ? "Female" : patient.sex === "M" ? "Male" : "Other"} · born {fmtDate(patient.date_of_birth)}</span>
            {patient.identifiers.map((i) => (
              <span key={i.id_type} className="badge">{titleCase(i.id_type)} {i.value}</span>
            ))}
            {patient.verified ? (
              <span className="badge good">Client Registry {patient.cr_id}</span>
            ) : (
              <span className="badge">Unverified</span>
            )}
          </p>
          {location.state?.source === "CLIENT_REGISTRY" && (
            <p className="small muted">First seen in this system today: record pulled from the national Client Registry.</p>
          )}
        </div>
        <div className="row">
          {user.role === "PRESCRIBER" && <Link className="btn primary" to={`/patients/${id}/prescribe`}>New prescription</Link>}
          {user.role === "PHARMACIST" && <button onClick={() => setShowPaper((s) => !s)}>Dispense paper prescription</button>}
        </div>
      </div>

      {showPaper && <PaperDispense patient={patient} onDone={() => { setShowPaper(false); setTick((t) => t + 1); }} />}

      <div className="grid grid-4">
        <Stat label="Active monitored medicines" value={summary.active_medicines.length} sub="supply not yet run out" />
        <Stat label="Opioid dose now" value={`${fmtNum(mme, 1)}`} sub="MME per day (warning ≥ 50)" alert={mme >= 50} />
        <Stat label="Prescribers, last 90 days" value={summary.prescribers_90d} sub="distinct licences" alert={summary.prescribers_90d >= 3} />
        <Stat label="Pharmacies, last 90 days" value={summary.pharmacies_90d} sub={`${summary.dispenses_90d} dispenses`} alert={summary.pharmacies_90d >= 3} />
      </div>

      {openRx.length > 0 && (
        <div className="card">
          <div className="card-head"><h2>Open prescriptions</h2></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Medicine</th><th>Prescriber</th><th>Issued</th><th className="num">Remaining</th><th /></tr></thead>
              <tbody>
                {openRx.map((rx) => (
                  <tr key={rx.id}>
                    <td className="mono">{rx.code}</td>
                    <td>{rx.drug?.name}<div className="muted small">{rx.dosage_instructions}</div></td>
                    <td>{rx.prescriber_name}<div className="muted small">{rx.facility?.name}</div></td>
                    <td>{fmtDate(rx.issued_at)}</td>
                    <td className="num">{fmtNum(rx.remaining_quantity)}</td>
                    <td>{user.role === "PHARMACIST" && <Link className="btn primary" to={`/dispense?code=${rx.code}`}>Dispense</Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-head">
          <h2>Supply timeline</h2>
          <p>Each bar is one dispensed supply; overlapping bars mean overlapping supply.</p>
        </div>
        <SupplyTimeline events={history} />
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-head"><h2>Recent alerts</h2><p>Across all facilities</p></div>
          {alerts.length === 0 ? (
            <p className="muted">No alerts recorded for this patient.</p>
          ) : (
            alerts.map((a) => (
              <div key={a.id} className={`finding ${a.severity}`}>
                <div className="row">
                  <span className={`sev ${a.severity}`}>{a.severity}</span>
                  <strong>{a.title}</strong>
                  <span className="muted small">{fmtDateTime(a.occurred_at)}</span>
                </div>
                <p className="small">{a.message}</p>
                <div className="small muted">
                  {titleCase(a.action)} · acknowledged by {a.acknowledged_by_name}: {titleCase(a.ack_reason)}
                  {a.referral_made && " · referred for support"}
                </div>
              </div>
            ))
          )}
        </div>
        <div className="card">
          <div className="card-head"><h2>Active supply</h2></div>
          {summary.active_medicines.length === 0 ? (
            <p className="muted">No active supply.</p>
          ) : (
            <table>
              <thead><tr><th>Medicine</th><th>Until</th><th className="num">Days left</th><th className="num">MME/day</th></tr></thead>
              <tbody>
                {summary.active_medicines.map((m, i) => (
                  <tr key={i}>
                    <td>{m.drug_name}<div className="muted small">{m.facility_name}</div></td>
                    <td>{fmtDate(m.end_date)}</td>
                    <td className="num">{m.days_left}</td>
                    <td className="num">{m.daily_mme ? fmtNum(m.daily_mme, 1) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h2>Full history</h2><p>{history.length} records across the county</p></div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Event</th><th>Medicine</th><th className="num">Qty</th><th className="num">Days</th><th>Prescriber</th><th>Facility</th></tr>
            </thead>
            <tbody>
              {history.map((e) => (
                <tr key={e.id} style={e.status !== "ACTIVE" ? { opacity: 0.5 } : undefined}>
                  <td>{fmtDate(e.occurred_at)}</td>
                  <td>
                    <span className="badge">{titleCase(e.kind)}</span>
                    {e.is_paper && <span className="badge">Paper</span>}
                    {e.status !== "ACTIVE" && <span className="badge">{titleCase(e.status)}</span>}
                  </td>
                  <td>{e.drug_name}</td>
                  <td className="num">{fmtNum(e.quantity)}</td>
                  <td className="num">{e.days_supply}</td>
                  <td>{e.prescriber_name}<div className="muted small mono">{e.prescriber_key}</div></td>
                  <td>{e.facility_name}<div className="muted small">{e.sub_county}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, alert }) {
  return (
    <div className="stat" style={alert ? { borderColor: "var(--critical)", background: "var(--critical-soft)" } : undefined}>
      <div className="label">{alert && "⚠️ "}{label}</div>
      <div className="value">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

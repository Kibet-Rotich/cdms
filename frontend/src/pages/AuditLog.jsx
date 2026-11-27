import { useEffect, useState } from "react";
import { get } from "../api";
import { fmtDateTime, titleCase } from "../format";

export default function AuditLog() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [accessOnly, setAccessOnly] = useState(true);
  const [patientId, setPatientId] = useState("");
  const [chain, setChain] = useState(null);

  useEffect(() => {
    const q = new URLSearchParams({ page, pageSize: 50 });
    if (accessOnly) q.set("accessOnly", "true");
    if (patientId.trim()) q.set("patientId", patientId.trim());
    get(`/audit-events?${q}`).then((r) => {
      setItems(r.items);
      setTotal(r.total);
    });
  }, [page, accessOnly, patientId]);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Audit log</h1>
          <p>Append-only. Every row carries the hash of the previous row, so any edit or deletion breaks the chain.</p>
        </div>
        <div className="row">
          <button onClick={() => get("/audit-events/verify").then(setChain)}>Verify integrity</button>
          {chain && (
            <span className={`badge ${chain.intact ? "good" : ""}`}>
              {chain.intact ? `Chain intact (${chain.events} events)` : `Broken at #${chain.firstBrokenSeq}`}
            </span>
          )}
        </div>
      </div>
      <div className="card">
        <div className="row" style={{ marginBottom: 12 }}>
          <label className="row small"><input type="checkbox" checked={accessOnly} onChange={(e) => { setPage(1); setAccessOnly(e.target.checked); }} /> Only data access (hide system events)</label>
          <input placeholder="Filter by patient ID" value={patientId} onChange={(e) => { setPage(1); setPatientId(e.target.value); }} style={{ minWidth: 280 }} />
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>When</th><th>Who</th><th>Action</th><th>Resource</th><th>Purpose</th><th>Details</th></tr></thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.seq}>
                  <td className="mono small">{e.seq}</td>
                  <td className="small">{fmtDateTime(e.occurred_at)}</td>
                  <td>{e.actor_name || <span className="muted">system</span>}<div className="muted small">{titleCase(e.actor_role)}</div></td>
                  <td><span className="badge">{e.action.replace("EVENT:", "")}</span></td>
                  <td className="small">{e.resource_type}<div className="muted mono">{e.patient_id ? `patient ${e.patient_id.slice(0, 8)}…` : ""}</div></td>
                  <td className="small">{titleCase(e.purpose)}</td>
                  <td className="small muted mono" style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {Object.keys(e.details || {}).length ? JSON.stringify(e.details) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="small muted">Page {page} of {Math.max(1, Math.ceil(total / 50))} · {total} events</span>
          <button disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>
    </div>
  );
}

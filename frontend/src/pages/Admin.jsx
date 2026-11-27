import { useEffect, useState } from "react";
import { get, patch, post } from "../api";
import { useAuth } from "../auth";
import { fmtDate, fmtNum, ROLE_LABEL, titleCase } from "../format";

export function Users() {
  const [status, setStatus] = useState("PENDING");
  const [users, setUsers] = useState([]);
  const [facilities, setFacilities] = useState({});
  const [error, setError] = useState("");

  const load = () => get(`/users?status=${status}&pageSize=200`).then((r) => setUsers(r.items)).catch((e) => setError(e.message));
  useEffect(() => {
    get("/facilities").then((fs) => setFacilities(Object.fromEntries(fs.map((f) => [f.id, f.name]))));
  }, []);
  useEffect(() => {
    load();
  }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id, action) => {
    setError("");
    try {
      await post(`/users/${id}/${action}`, {});
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Users</h1><p>Approve practitioners after their licence is verified; suspend accounts when needed.</p></div>
        <div className="row">
          {["PENDING", "ACTIVE", "SUSPENDED"].map((s) => (
            <button key={s} className={s === status ? "primary" : ""} onClick={() => setStatus(s)}>{titleCase(s)}</button>
          ))}
        </div>
      </div>
      {error && <div className="banner error">{error}</div>}
      <div className="card table-wrap">
        {users.length === 0 ? <p className="muted">No {status.toLowerCase()} users.</p> : (
          <table>
            <thead><tr><th>Name</th><th>Role</th><th>Licence</th><th>Facility</th><th>Registered</th><th /></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}<div className="muted small">{u.email}</div></td>
                  <td>{ROLE_LABEL[u.role]}<div className="muted small">{titleCase(u.cadre)}</div></td>
                  <td className="mono">{u.licence_number || "—"}</td>
                  <td>{facilities[u.facility_id] || "—"}</td>
                  <td>{fmtDate(u.created_at)}</td>
                  <td className="row">
                    {u.status !== "ACTIVE" && <button className="primary" onClick={() => act(u.id, "approve")}>Approve</button>}
                    {u.status === "ACTIVE" && <button onClick={() => act(u.id, "suspend")}>Suspend</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function Rules() {
  const { user } = useAuth();
  const [rules, setRules] = useState([]);
  const [edits, setEdits] = useState({});
  const [msg, setMsg] = useState("");
  const editable = user.role === "SYSTEM_ADMIN";

  useEffect(() => {
    get("/alert-rules").then(setRules);
  }, []);

  const save = async (rule) => {
    const params = Object.fromEntries(
      Object.entries(edits[rule.code] || {}).filter(([k]) => k !== "enabled").map(([k, v]) => [k, k === "severity" ? v : Number(v)])
    );
    const body = { params };
    if (edits[rule.code]?.enabled !== undefined) body.enabled = edits[rule.code].enabled;
    try {
      const updated = await patch(`/alert-rules/${rule.code}`, body);
      setRules((rs) => rs.map((r) => (r.code === rule.code ? updated : r)));
      setEdits((e) => ({ ...e, [rule.code]: undefined }));
      setMsg(`Saved ${rule.title}.`);
    } catch (e) {
      setMsg(e.message);
    }
  };

  const val = (rule, k) => edits[rule.code]?.[k] ?? rule.params[k];
  const setVal = (rule, k, v) => setEdits((e) => ({ ...e, [rule.code]: { ...(e[rule.code] || {}), [k]: v } }));

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Alert rules</h1>
          <p>Every alert is explainable: these are the exact rules and thresholds. {editable ? "Changes apply immediately and are audited." : "Only the system admin can change them."}</p>
        </div>
      </div>
      {msg && <div className="banner">{msg}</div>}
      {rules.map((r) => (
        <div className="card" key={r.code}>
          <div className="card-head">
            <div>
              <h2>{r.title} <span className="muted small mono">{r.code}</span></h2>
              <p>{r.description} Runs on: {r.applies_to.map(titleCase).join(", ")}.</p>
            </div>
            <label className="row small">
              <input type="checkbox" disabled={!editable} checked={val(r, "enabled") ?? r.enabled}
                onChange={(e) => setVal(r, "enabled", e.target.checked)} />
              Enabled
            </label>
          </div>
          <div className="form-grid">
            {Object.keys(r.params).map((k) => (
              <label className="field" key={k}>
                {titleCase(k)}
                {k === "severity" ? (
                  <select disabled={!editable} value={val(r, k)} onChange={(e) => setVal(r, k, e.target.value)}>
                    {["CRITICAL", "WARNING", "INFO"].map((s) => <option key={s}>{s}</option>)}
                  </select>
                ) : (
                  <input type="number" step="any" disabled={!editable} value={val(r, k)} onChange={(e) => setVal(r, k, e.target.value)} />
                )}
              </label>
            ))}
          </div>
          {editable && edits[r.code] && (
            <div className="form-actions"><button className="primary" onClick={() => save(r)}>Save</button></div>
          )}
        </div>
      ))}
    </div>
  );
}

export function Drugs() {
  const [drugs, setDrugs] = useState([]);
  useEffect(() => {
    get("/drugs?active=all").then(setDrugs);
  }, []);
  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Drug catalogue</h1><p>General starter list of monitored medicines. Morphine-equivalent factors drive the dose rule. Edit details in Django admin (/admin) for now.</p></div>
      </div>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Medicine</th><th>Class</th><th className="num">Strength</th><th>Unit</th><th className="num">MME factor</th><th>Monitored</th></tr></thead>
          <tbody>
            {drugs.map((d) => (
              <tr key={d.id}>
                <td>{d.name}<div className="muted small">{d.generic_name}</div></td>
                <td>{d.class_name}</td>
                <td className="num">{fmtNum(d.strength_mg, 3)}</td>
                <td>{titleCase(d.unit)}</td>
                <td className="num">{d.mme_factor ?? "—"}</td>
                <td>{d.monitored ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

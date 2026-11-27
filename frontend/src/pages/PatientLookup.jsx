import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { get, post, purpose } from "../api";
import { ID_TYPES } from "../format";

const PURPOSES = [
  ["DISPENSING", "Dispensing"],
  ["PRESCRIBING", "Prescribing"],
  ["CONSULTATION", "Consultation"],
];

export default function PatientLookup() {
  const navigate = useNavigate();
  const [idType, setIdType] = useState("NATIONAL_ID");
  const [idNumber, setIdNumber] = useState("");
  const [why, setWhy] = useState(purpose.get() || "DISPENSING");
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);

  const search = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotFound(false);
    purpose.set(why);
    try {
      const res = await get(`/patients/search?idType=${idType}&idNumber=${encodeURIComponent(idNumber)}`);
      navigate(`/patients/${res.patient.id}`, { state: { source: res.source } });
    } catch (err) {
      if (err.code === "PATIENT_NOT_FOUND") setNotFound(true);
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack" style={{ maxWidth: 760 }}>
      <div className="page-head">
        <div>
          <h1>Find a patient</h1>
          <p>Searches local records first, then the national Client Registry. Every lookup is logged with its purpose.</p>
        </div>
      </div>
      <form className="card" onSubmit={search}>
        <div className="form-grid">
          <label className="field">
            ID type
            <select value={idType} onChange={(e) => setIdType(e.target.value)}>
              {ID_TYPES.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
          <label className="field">
            ID number
            <input value={idNumber} onChange={(e) => setIdNumber(e.target.value)} placeholder="e.g. 23456789" required autoFocus />
          </label>
          <label className="field">
            Purpose of access
            <select value={why} onChange={(e) => setWhy(e.target.value)}>
              {PURPOSES.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
        </div>
        {error && <div className="banner error" style={{ marginTop: 12 }}>{error}</div>}
        <div className="form-actions">
          <button className="primary" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>
          Demo IDs: 30000001 (Grace Wanjiku, Client Registry only) · 23456789 (Peter Kamau) · 34567890 (Mary Njeri)
        </p>
      </form>
      {notFound && <RegisterPatient idType={idType} idNumber={idNumber} onCreated={(p) => navigate(`/patients/${p.id}`)} />}
    </div>
  );
}

function RegisterPatient({ idType, idNumber, onCreated }) {
  const [form, setForm] = useState({ first_name: "", middle_name: "", last_name: "", date_of_birth: "", sex: "F", phone: "" });
  const [error, setError] = useState("");
  const [candidates, setCandidates] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e, confirm = false) => {
    e?.preventDefault();
    setError("");
    try {
      const p = await post(`/patients${confirm ? "?confirm=true" : ""}`, { ...form, id_type: idType, id_number: idNumber });
      onCreated(p);
    } catch (err) {
      if (err.code === "POSSIBLE_DUPLICATE") setCandidates(err.body.candidates);
      else setError(err.message);
    }
  };

  return (
    <form className="card" onSubmit={submit}>
      <div className="card-head">
        <h2>Not found. Register an unverified patient</h2>
        <p>The record is marked unverified until matched in the Client Registry.</p>
      </div>
      <div className="form-grid">
        <label className="field">First name<input value={form.first_name} onChange={set("first_name")} required /></label>
        <label className="field">Middle name<input value={form.middle_name} onChange={set("middle_name")} /></label>
        <label className="field">Last name<input value={form.last_name} onChange={set("last_name")} required /></label>
        <label className="field">Date of birth<input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} required /></label>
        <label className="field">
          Sex
          <select value={form.sex} onChange={set("sex")}>
            <option value="F">Female</option>
            <option value="M">Male</option>
            <option value="O">Other / unknown</option>
          </select>
        </label>
        <label className="field">Phone<input value={form.phone} onChange={set("phone")} /></label>
      </div>
      {candidates && (
        <div className="banner error" style={{ marginTop: 12 }}>
          <strong>Possible duplicate.</strong> These patients have matching details:
          <ul>
            {candidates.map((c) => (
              <li key={c.id}>
                <a href={`/patients/${c.id}`}>{c.full_name}</a> · born {c.date_of_birth} ·{" "}
                {c.identifiers.map((i) => `${i.id_type} ${i.value}`).join(", ")}
              </li>
            ))}
          </ul>
          <button type="button" onClick={() => submit(null, true)}>Not the same person, register anyway</button>
        </div>
      )}
      {error && <div className="banner error" style={{ marginTop: 12 }}>{error}</div>}
      <div className="form-actions">
        <button className="primary">Register patient</button>
      </div>
    </form>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post } from "../api";

export default function Register() {
  const [facilities, setFacilities] = useState([]);
  const [form, setForm] = useState({ email: "", password: "", full_name: "", phone: "", role: "PRESCRIBER", licence_number: "", facility_id: "" });
  const [verified, setVerified] = useState(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    get("/facilities").then(setFacilities).catch(() => {});
  }, []);

  const verify = async () => {
    setVerified(null);
    setError("");
    try {
      const p = await get(`/practitioners/verify?licence=${encodeURIComponent(form.licence_number)}`);
      setVerified(p);
      if (!form.full_name) setForm((f) => ({ ...f, full_name: p.full_name }));
    } catch (err) {
      setError(err.message);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await post("/users/register", form);
      setDone(true);
    } catch (err) {
      const fieldErrors = err.body?.errors ? Object.values(err.body.errors).flat().join(" ") : "";
      setError(`${err.message} ${fieldErrors}`);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card login-card" style={{ width: "min(560px, 100%)" }}>
        <h1>Practitioner registration</h1>
        {done ? (
          <div className="banner ok">
            Registration received. Your facility admin or the system admin must approve your account before you can sign in.
            <div style={{ marginTop: 8 }}><Link to="/login">Back to sign in</Link></div>
          </div>
        ) : (
          <form onSubmit={submit} className="stack" style={{ gap: 12 }}>
            <p className="small muted">
              Your licence is checked against the practitioner registry (KMPDC / PPB, mocked in this demo). Try A19999 or PPB-29999.
            </p>
            <div className="form-grid">
              <label className="field">
                I am a
                <select value={form.role} onChange={set("role")}>
                  <option value="PRESCRIBER">Prescriber (doctor / clinical officer)</option>
                  <option value="PHARMACIST">Pharmacist</option>
                </select>
              </label>
              <label className="field">
                Licence number
                <div className="row" style={{ flexWrap: "nowrap" }}>
                  <input value={form.licence_number} onChange={set("licence_number")} required style={{ flex: 1 }} />
                  <button type="button" onClick={verify}>Verify</button>
                </div>
              </label>
            </div>
            {verified && (
              <div className={`banner ${verified.status === "ACTIVE" ? "ok" : "error"}`}>
                {verified.full_name} · {verified.cadre.replace("_", " ").toLowerCase()} · {verified.regulator} · status {verified.status}
              </div>
            )}
            <div className="form-grid">
              <label className="field">Full name<input value={form.full_name} onChange={set("full_name")} required /></label>
              <label className="field">Phone<input value={form.phone} onChange={set("phone")} /></label>
              <label className="field">Email<input type="email" value={form.email} onChange={set("email")} required /></label>
              <label className="field">Password<input type="password" value={form.password} onChange={set("password")} minLength={8} required /></label>
            </div>
            <label className="field">
              Facility
              <select value={form.facility_id} onChange={set("facility_id")} required>
                <option value="">Select your facility…</option>
                {facilities.map((f) => (
                  <option key={f.id} value={f.id}>{f.name} ({f.sub_county})</option>
                ))}
              </select>
            </label>
            {error && <div className="banner error">{error}</div>}
            <div className="form-actions">
              <button className="primary">Submit for approval</button>
              <Link className="btn" to="/login">Cancel</Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { HOME_BY_ROLE, useAuth } from "../auth";

const DEMO = [
  ["dr.achieng@demo.ke", "Dr. Achieng (Prescriber, \"Dr A\")"],
  ["dr.baraka@demo.ke", "Dr. Baraka (Prescriber, \"Dr B\")"],
  ["pharm.wambui@demo.ke", "Wambui (Pharmacist, Uhuru Pharmacy)"],
  ["pharm.otieno@demo.ke", "Brian (Pharmacist, Jamii Chemist)"],
  ["regulator@demo.ke", "County regulator"],
  ["admin@demo.ke", "System admin"],
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e, creds) => {
    e?.preventDefault();
    setBusy(true);
    setError("");
    try {
      const me = await login(creds?.email || email, creds?.password || password);
      navigate(HOME_BY_ROLE[me.role]);
    } catch (err) {
      setError(err.status === 401 ? "Wrong email or password, or the account is not approved yet." : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="brand" style={{ padding: "0 0 12px" }}>
          <div className="brand-mark">Rx</div>
          <div>
            <strong>Controlled-Drug Monitoring System</strong>
            <small>Nairobi County pilot · synthetic demo data</small>
          </div>
        </div>
        <form onSubmit={submit} className="stack" style={{ gap: 12 }}>
          <label className="field">
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </label>
          <label className="field">
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {error && <div className="banner error">{error}</div>}
          <button className="primary" disabled={busy}>Sign in</button>
        </form>
        <p className="small muted">
          New practitioner? <Link to="/register">Register with your licence number</Link>
        </p>
        <hr style={{ border: 0, borderTop: "1px solid var(--border)", margin: "14px 0" }} />
        <div className="demo-list">
          <div className="small muted">Demo accounts (password Demo@1234)</div>
          {DEMO.map(([em, label]) => (
            <button key={em} disabled={busy} onClick={(e) => submit(e, { email: em, password: "Demo@1234" })}>
              <span>{label}</span>
              <span className="muted small">{em}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

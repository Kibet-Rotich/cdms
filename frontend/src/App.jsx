import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { HOME_BY_ROLE, useAuth } from "./auth";
import { ROLE_LABEL } from "./format";
import Login from "./pages/Login";
import Register from "./pages/Register";
import PatientLookup from "./pages/PatientLookup";
import PatientPage from "./pages/PatientPage";
import NewPrescription from "./pages/NewPrescription";
import Dispense from "./pages/Dispense";
import Dashboard from "./pages/Dashboard";
import AuditLog from "./pages/AuditLog";
import { Drugs, Rules, Users } from "./pages/Admin";

const NAV = {
  PRESCRIBER: [["/patients", "Patient lookup"], ["/rules", "Alert rules"]],
  PHARMACIST: [["/patients", "Patient lookup"], ["/dispense", "Dispense by code"], ["/rules", "Alert rules"]],
  REGULATOR: [["/dashboard", "County dashboard"], ["/audit", "Audit log"], ["/rules", "Alert rules"]],
  SYSTEM_ADMIN: [["/admin/users", "Users"], ["/rules", "Alert rules"], ["/admin/drugs", "Drug catalogue"], ["/dashboard", "County dashboard"], ["/audit", "Audit log"]],
  FACILITY_ADMIN: [["/admin/users", "Facility users"]],
};

function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Rx</div>
          <div>
            <strong>CDMS</strong>
            <small>Nairobi pilot</small>
          </div>
        </div>
        <nav className="nav">
          {(NAV[user.role] || []).map(([to, label]) => (
            <NavLink key={to} to={to}>{label}</NavLink>
          ))}
        </nav>
        <div className="who">
          <div><strong>{user.full_name}</strong></div>
          <div>{ROLE_LABEL[user.role]}</div>
          {user.facility && <div className="muted">{user.facility.name}</div>}
          <button className="link" style={{ marginTop: 6 }} onClick={() => { logout(); navigate("/login"); }}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

function RequireAuth({ roles }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="main muted">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
  return <Outlet />;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user ? HOME_BY_ROLE[user.role] : "/login"} replace />;
}

const CLINICAL = ["PRESCRIBER", "PHARMACIST"];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route element={<RequireAuth roles={CLINICAL} />}>
            <Route path="/patients" element={<PatientLookup />} />
            <Route path="/patients/:id" element={<PatientPage />} />
          </Route>
          <Route element={<RequireAuth roles={["PRESCRIBER"]} />}>
            <Route path="/patients/:id/prescribe" element={<NewPrescription />} />
          </Route>
          <Route element={<RequireAuth roles={["PHARMACIST"]} />}>
            <Route path="/dispense" element={<Dispense />} />
          </Route>
          <Route element={<RequireAuth roles={["REGULATOR", "SYSTEM_ADMIN"]} />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/audit" element={<AuditLog />} />
          </Route>
          <Route element={<RequireAuth roles={["SYSTEM_ADMIN", "FACILITY_ADMIN"]} />}>
            <Route path="/admin/users" element={<Users />} />
          </Route>
          <Route element={<RequireAuth roles={["SYSTEM_ADMIN"]} />}>
            <Route path="/admin/drugs" element={<Drugs />} />
          </Route>
          <Route path="/rules" element={<Rules />} />
        </Route>
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  );
}

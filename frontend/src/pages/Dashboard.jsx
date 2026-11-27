import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, get, post } from "../api";
import { fmtDate, fmtDateTime, fmtNum, titleCase } from "../format";

const RANGES = [
  [30, "Last 30 days"],
  [90, "Last 90 days"],
  [182, "Last 6 months"],
];
// Drug classes folded to three series so categorical colours stay distinguishable (fixed order).
const SERIES = [
  { key: "Opioid", color: "var(--series-1)" },
  { key: "Benzodiazepine", color: "var(--series-2)" },
  { key: "Other monitored", color: "var(--series-3)" },
];

const iso = (d) => d.toISOString().slice(0, 10);

export default function Dashboard() {
  const [days, setDays] = useState(90);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [revealed, setRevealed] = useState({});

  useEffect(() => {
    const to = new Date();
    const from = new Date(Date.now() - days * 86400000);
    const q = `?from=${iso(from)}&to=${iso(to)}`;
    setData(null);
    Promise.all([
      get(`/oversight/summary${q}`),
      get(`/oversight/trends?from=${iso(new Date(Date.now() - 182 * 86400000))}&to=${iso(to)}`),
      get(`/oversight/outliers/prescribers${q}`),
      get(`/oversight/outliers/pharmacies${q}`),
      get(`/oversight/hotspots${q}`),
      get(`/oversight/flagged-patients${q}`),
      get(`/oversight/supply-reconciliation`),
    ])
      .then(([summary, trends, prescribers, pharmacies, hotspots, flagged, supply]) =>
        setData({ summary, trends, prescribers, pharmacies, hotspots, flagged, supply })
      )
      .catch((e) => setError(e.message));
  }, [days]);

  const trend = useMemo(
    () =>
      (data?.trends.weeks || []).map((w) => {
        const other = Object.entries(w).filter(([k]) => !["week", "OPIOID", "BENZODIAZEPINE"].includes(k)).reduce((s, [, v]) => s + v, 0);
        return { week: fmtDate(w.week).replace(/ \d{4}$/, ""), Opioid: w.OPIOID || 0, Benzodiazepine: w.BENZODIAZEPINE || 0, "Other monitored": other };
      }),
    [data]
  );

  const reveal = async (ref) => {
    const reason = window.prompt("Reason for revealing this patient's identity (investigation reference). This is logged.");
    if (!reason) return;
    try {
      const res = await post(`/oversight/flagged-patients/${ref}/reveal`, { reason });
      setRevealed((r) => ({ ...r, [ref]: res.patient }));
    } catch (e) {
      window.alert(e.message);
    }
  };

  const exportCsv = async (type) => {
    const res = await api(`/oversight/reports/export?type=${type}`, { raw: true });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${type}.csv`;
    a.click();
  };

  if (error) return <div className="banner error">{error}</div>;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Nairobi County: controlled-drug oversight</h1>
          <p>Monitored medicines dispensed across all participating facilities.</p>
        </div>
        <div className="row">
          {RANGES.map(([d, label]) => (
            <button key={d} className={d === days ? "primary" : ""} onClick={() => setDays(d)}>{label}</button>
          ))}
        </div>
      </div>

      {!data ? (
        <p className="muted">Loading dashboard…</p>
      ) : (
        <>
          <div className="grid grid-4">
            <Stat label="Dispenses" value={fmtNum(data.summary.dispenses)} sub={`${fmtNum(data.summary.paper_dispenses)} on paper prescriptions`} />
            <Stat label="Patients" value={fmtNum(data.summary.patients)} sub={`${fmtNum(data.summary.prescriptions)} e-prescriptions issued`} />
            <Stat label="Alerts acknowledged" value={fmtNum(data.summary.alerts.alerts)} sub={`${fmtNum(data.summary.alerts.critical)} critical · ${fmtNum(data.summary.alerts.referrals)} referrals`} />
            <Stat label="Flagged patients" value={fmtNum(data.flagged.items.length)} sub="2+ critical alerts in period" />
          </div>

          <div className="card">
            <div className="card-head">
              <h2>Weekly dispenses by drug class</h2>
              <p>Last 6 months</p>
            </div>
            <div style={{ width: "100%", height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={trend} margin={{ top: 8, right: 8, left: -12, bottom: 0 }} barCategoryGap="18%">
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: "var(--text-3)" }} tickLine={false} axisLine={{ stroke: "var(--grid)" }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-3)" }} tickLine={false} axisLine={false} />
                  <Tooltip
                    cursor={{ fill: "var(--surface-2)" }}
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} iconType="square" formatter={(v) => <span style={{ color: "var(--text-2)" }}>{v}</span>} />
                  {SERIES.map((s, i) => (
                    <Bar key={s.key} dataKey={s.key} stackId="a" fill={s.color} isAnimationActive={false} stroke="var(--surface)" strokeWidth={1}
                      radius={i === SERIES.length - 1 ? [4, 4, 0, 0] : 0} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="card-head"><h2>Alerts by rule</h2><p>Acknowledged and overridden by clinicians</p></div>
              <table>
                <thead><tr><th>Rule</th><th className="num">Alerts</th><th className="num">Critical</th></tr></thead>
                <tbody>
                  {data.summary.alerts.by_rule.map((r) => (
                    <tr key={r.rule_code}><td>{r.title}</td><td className="num">{r.n}</td><td className="num">{r.critical}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card">
              <div className="card-head"><h2>Hotspots by sub-county</h2><p>Sorted by critical alerts</p></div>
              <table>
                <thead><tr><th>Sub-county</th><th className="num">Dispenses</th><th className="num">Alerts</th><th className="num">Critical</th><th className="num">per 100</th></tr></thead>
                <tbody>
                  {data.hotspots.items.map((h) => (
                    <tr key={h.sub_county}>
                      <td>{h.sub_county}</td><td className="num">{h.dispenses}</td><td className="num">{h.alerts}</td>
                      <td className="num">{h.critical_alerts}</td><td className="num">{h.alerts_per_100_dispenses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>Prescriber outliers</h2>
              <p>Opioid prescriptions compared with the county median ({fmtNum(data.prescribers.median_opioid_prescriptions, 1)}); flagged at {data.prescribers.outlier_ratio}× or more</p>
              <button onClick={() => exportCsv("prescribers")}>Export CSV</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Prescriber</th><th>Facility</th><th className="num">Prescriptions</th><th className="num">Opioid Rx</th><th className="num">× median</th><th className="num">Patients</th><th className="num">Alerts</th></tr></thead>
                <tbody>
                  {data.prescribers.items.slice(0, 10).map((p) => (
                    <tr key={p.prescriber_key} className={p.outlier ? "flagged" : ""}>
                      <td>{p.outlier && <span className="sev CRITICAL">Outlier</span>} {p.prescriber_name}<div className="muted small mono">{p.prescriber_key}</div></td>
                      <td>{p.facilities.join(", ")}</td>
                      <td className="num">{p.prescriptions}</td><td className="num">{p.opioid_prescriptions}</td>
                      <td className="num"><strong>{p.ratio_to_median}×</strong></td><td className="num">{p.patients}</td><td className="num">{p.alerts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="card">
              <div className="card-head">
                <h2>Pharmacies</h2>
                <p>Sorted by critical alerts</p>
                <button onClick={() => exportCsv("pharmacies")}>Export CSV</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Pharmacy</th><th className="num">Dispenses</th><th className="num">Paper</th><th className="num">Alerts</th><th className="num">Critical</th></tr></thead>
                  <tbody>
                    {data.pharmacies.items.map((p) => (
                      <tr key={p.facility_id}>
                        <td>{p.facility_name}<div className="muted small">{p.sub_county}</div></td>
                        <td className="num">{p.dispenses}</td><td className="num">{p.paper_dispenses}</td>
                        <td className="num">{p.alerts}</td><td className="num">{p.critical_alerts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card">
              <div className="card-head"><h2>Flagged patients</h2><p>Pseudonymised. Revealing an identity requires a reason and is audited.</p></div>
              {data.flagged.items.length === 0 ? (
                <p className="muted">No patients with repeated critical alerts.</p>
              ) : (
                <table>
                  <thead><tr><th>Patient</th><th>Rules triggered</th><th className="num">Critical</th><th>Last alert</th></tr></thead>
                  <tbody>
                    {data.flagged.items.map((f) => (
                      <tr key={f.ref}>
                        <td>
                          {revealed[f.ref] ? (
                            <div>
                              <strong>{revealed[f.ref].full_name}</strong>
                              <div className="small muted">{revealed[f.ref].identifiers.map((i) => `${titleCase(i.id_type)} ${i.value}`).join(", ")}</div>
                            </div>
                          ) : (
                            <>
                              <span className="mono">{f.ref}</span>{" "}
                              <button className="link small" onClick={() => reveal(f.ref)}>Reveal</button>
                            </>
                          )}
                        </td>
                        <td className="small">{f.rules.map(titleCase).join(", ")}</td>
                        <td className="num">{f.critical}</td>
                        <td className="small">{fmtDateTime(f.last_alert_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>Supply vs dispensed (preview)</h2>
              <p>Stock received (mocked PPB track-and-trace feed) compared with stock dispensed, last 6 months. Dispensing more than was received points to stock from an unrecorded source.</p>
              <button onClick={() => exportCsv("supply")}>Export CSV</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Pharmacy</th><th>Medicine</th><th className="num">Received</th><th className="num">Dispensed</th><th className="num">Gap</th></tr></thead>
                <tbody>
                  {data.supply.items.slice(0, 8).map((r, i) => (
                    <tr key={i} className={r.flag ? "flagged" : ""}>
                      <td>{r.flag && <span className="sev CRITICAL">Gap</span>} {r.facility_name}</td>
                      <td>{r.drug_name}</td>
                      <td className="num">{fmtNum(r.received)}</td><td className="num">{fmtNum(r.dispensed)}</td>
                      <td className="num"><strong>{r.gap > 0 ? `+${fmtNum(r.gap)}` : fmtNum(r.gap)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}

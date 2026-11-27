import { useMemo, useState } from "react";
import { fmtDate } from "../format";

// Gantt-style view of dispensed supply over the last N days: overlapping bars = overlapping supply.
// Classes are folded to three series (opioid, benzodiazepine, other) so colours stay distinguishable.
const SERIES = [
  { key: "OPIOID", label: "Opioid", color: "var(--series-1)" },
  { key: "BENZODIAZEPINE", label: "Benzodiazepine", color: "var(--series-2)" },
  { key: "OTHER", label: "Other monitored", color: "var(--series-3)" },
];
const seriesOf = (cls) => SERIES.find((s) => s.key === cls) || SERIES[2];
const DAY = 86400000;

export default function SupplyTimeline({ events, days = 120 }) {
  const [tip, setTip] = useState(null);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today.getTime() - days * DAY);
  const end = new Date(today.getTime() + 30 * DAY);
  const span = end - start;

  const rows = useMemo(
    () =>
      events
        .filter((e) => e.kind === "DISPENSED" && e.status === "ACTIVE" && new Date(e.end_date) >= start)
        .sort((a, b) => new Date(a.start_date) - new Date(b.start_date)),
    [events] // eslint-disable-line react-hooks/exhaustive-deps
  );

  if (!rows.length) return <p className="muted">No dispensed supply in the last {days} days.</p>;

  const W = 1000;
  const rowH = 22;
  const top = 22;
  const H = top + rows.length * rowH + 8;
  const x = (d) => Math.max(0, Math.min(W, ((new Date(d) - start) / span) * W));
  const ticks = [];
  for (let t = new Date(start.getFullYear(), start.getMonth() + 1, 1); t < end; t = new Date(t.getFullYear(), t.getMonth() + 1, 1)) ticks.push(t);

  return (
    <div>
      <div className="legend" style={{ marginBottom: 6 }}>
        {SERIES.map((s) => (
          <span key={s.key}><i style={{ background: s.color }} />{s.label}</span>
        ))}
        <span><i style={{ background: "var(--critical)", width: 2 }} />Today</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Dispensed supply timeline" style={{ display: "block" }}>
        {ticks.map((t) => (
          <g key={t.toISOString()}>
            <line x1={x(t)} x2={x(t)} y1={top - 6} y2={H} stroke="var(--grid)" />
            <text x={x(t) + 4} y={12} fontSize="11" fill="var(--text-3)">
              {t.toLocaleDateString("en-KE", { month: "short" })}
            </text>
          </g>
        ))}
        {rows.map((e, i) => {
          const s = seriesOf(e.class_code);
          const x1 = x(e.start_date);
          const w = Math.max(4, x(e.end_date) - x1);
          return (
            <rect
              key={e.id}
              x={x1}
              y={top + i * rowH + 3}
              width={w}
              height={rowH - 8}
              rx="4"
              fill={s.color}
              stroke="var(--surface)"
              strokeWidth="2"
              onMouseMove={(ev) => setTip({ e, x: ev.clientX, y: ev.clientY })}
              onMouseLeave={() => setTip(null)}
            />
          );
        })}
        <line x1={x(today)} x2={x(today)} y1={top - 6} y2={H} stroke="var(--critical)" strokeWidth="2" />
      </svg>
      {tip && (
        <div className="tooltip" style={{ left: tip.x + 12, top: tip.y + 12 }}>
          <strong>{tip.e.drug_name}</strong>
          <div>{fmtDate(tip.e.start_date)} → {fmtDate(tip.e.end_date)} ({tip.e.days_supply} days)</div>
          <div>{tip.e.facility_name}</div>
          <div className="muted">Prescriber: {tip.e.prescriber_name || "—"}</div>
          {tip.e.daily_mme > 0 && <div>{tip.e.daily_mme} MME/day</div>}
        </div>
      )}
    </div>
  );
}

"use client";
import { useState } from "react";

export function Heatmap({ data }: { data: { date: string; submissions: number; accepted: number }[] }) {
  const map = new Map(data.map((d) => [d.date, d])); const end = new Date(); end.setHours(0, 0, 0, 0); const start = new Date(end); start.setDate(end.getDate() - 363 - ((end.getDay() + 6) % 7));
  const weeks: { date: string; n: number; ac: number }[][] = []; const d = new Date(start);
  while (d <= end) { const w: { date: string; n: number; ac: number }[] = []; for (let i = 0; i < 7 && d <= end; i++) { const k = d.toISOString().slice(0, 10); const v = map.get(k); w.push({ date: k, n: v?.submissions ?? 0, ac: v?.accepted ?? 0 }); d.setDate(d.getDate() + 1); } weeks.push(w); }
  const max = Math.max(1, ...data.map((x) => x.submissions)); const [tip, setTip] = useState("");
  const col = (n: number) => n === 0 ? "rgba(255,255,255,.05)" : `rgba(${n / max > 0.66 ? "163,230,53" : n / max > 0.33 ? "34,211,238" : "139,92,246"},${0.35 + 0.65 * Math.min(1, n / max)})`;
  return <div><div style={{ overflowX: "auto" }}><svg width={weeks.length * 14} height={7 * 14 + 4} role="img" aria-label="Submission activity over the last year">
    {weeks.map((w, i) => w.map((c, j) => <rect key={c.date} x={i * 14} y={j * 14} width={11} height={11} rx={3} fill={col(c.n)} onMouseEnter={() => setTip(`${c.date}: ${c.n} submissions, ${c.ac} accepted`)} onMouseLeave={() => setTip("")}><title>{`${c.date}: ${c.n} submissions, ${c.ac} accepted`}</title></rect>))}</svg></div>
    <p className="mono muted" style={{ fontSize: 11, minHeight: 16, marginTop: 6 }}>{tip || "Hover a day"}</p></div>;
}

export function LineChart({ series, height = 190, color = "#22d3ee", fmt = (v: number) => String(v) }: { series: { x: string; y: number | null; label?: string }[]; height?: number; color?: string; fmt?: (v: number) => string }) {
  const pts = series.filter((p) => p.y != null) as { x: string; y: number; label?: string }[]; const [hover, setHover] = useState<number | null>(null);
  if (pts.length < 2) return <p className="muted" style={{ padding: 20 }}>Not enough data points yet.</p>;
  const W = 640, H = height, pad = 30; const ys = pts.map((p) => p.y); const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const X = (i: number) => pad + (i / (pts.length - 1)) * (W - pad * 2), Y = (v: number) => H - pad - ((v - lo) / span) * (H - pad * 2);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.y).toFixed(1)}`).join(" "); const area = `${path} L${X(pts.length - 1)},${H - pad} L${X(0)},${H - pad} Z`; const id = `g${color.slice(1)}`;
  return <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" onMouseLeave={() => setHover(null)}>
    <defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".35" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
    {[0, 0.5, 1].map((t) => <g key={t}><line x1={pad} x2={W - pad} y1={H - pad - t * (H - pad * 2)} y2={H - pad - t * (H - pad * 2)} stroke="rgba(255,255,255,.07)" /><text x={4} y={H - pad - t * (H - pad * 2) + 4} fontSize="10" fill="#9a95b5">{fmt(Math.round(lo + t * span))}</text></g>)}
    <path d={area} fill={`url(#${id})`} /><path d={path} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" />
    {pts.map((p, i) => <rect key={i} x={X(i) - 6} y={0} width={12} height={H} fill="transparent" onMouseEnter={() => setHover(i)} />)}
    {hover != null && <g><circle cx={X(hover)} cy={Y(pts[hover].y)} r={5} fill={color} /><text x={Math.min(X(hover), W - 150)} y={Math.max(Y(pts[hover].y) - 12, 14)} fontSize="11" fill="#ece9f8">{fmt(pts[hover].y)} · {pts[hover].label ?? pts[hover].x}</text></g>}
  </svg>;
}

export function Bars({ data, color = "var(--violet)", fmt = (v: number) => v.toLocaleString() }: { data: [string, number][]; color?: string; fmt?: (v: number) => string }) {
  const max = Math.max(1e-9, ...data.map((d) => d[1]));
  return <div className="grid" style={{ gap: 6 }}>{data.map(([k, v]) => <div key={k} className="row" style={{ gap: 8, flexWrap: "nowrap" }}><span className="mono muted" style={{ width: 96, fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={k}>{k}</span>
    <div className="bar" style={{ flex: 1, height: 10 }}><i style={{ width: `${(v / max) * 100}%`, background: color }} /></div><span className="mono" style={{ width: 52, textAlign: "right", fontSize: 11 }}>{fmt(v)}</span></div>)}</div>;
}

const VCOL: Record<string, string> = { AC: "#a3e635", WA: "#fb7185", TLE: "#fbbf24", MLE: "#f59e0b", RE: "#c084fc", CE: "#94a3b8", OTHER: "#64748b" };
export function Donut({ data }: { data: Record<string, number> }) {
  const tot = Object.values(data).reduce((a, b) => a + b, 0) || 1; let acc = 0; const R = 54, C = 2 * Math.PI * R;
  return <div className="row" style={{ gap: 18 }}><svg width={140} height={140} viewBox="0 0 140 140" role="img" aria-label="Verdict distribution"><g transform="rotate(-90 70 70)">{Object.entries(data).map(([k, v]) => { const len = (v / tot) * C; const el = <circle key={k} cx={70} cy={70} r={R} fill="none" stroke={VCOL[k] ?? "#64748b"} strokeWidth={18} strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc}><title>{`${k}: ${v}`}</title></circle>; acc += len; return el; })}</g>
    <text x={70} y={74} textAnchor="middle" fill="#ece9f8" fontSize="20" fontWeight="700">{tot.toLocaleString()}</text></svg>
    <div className="grid" style={{ gap: 4 }}>{Object.entries(data).map(([k, v]) => <span key={k} className="mono" style={{ fontSize: 12 }}><i style={{ display: "inline-block", width: 9, height: 9, borderRadius: 3, background: VCOL[k] ?? "#64748b", marginRight: 6 }} />{k} {Math.round((v / tot) * 100)}%</span>)}</div></div>;
}

export function Ring({ value, max, label, color = "#22d3ee", size = 92 }: { value: number; max: number; label: string; color?: string; size?: number }) {
  const R = size / 2 - 8, C = 2 * Math.PI * R, p = Math.min(1, max ? value / max : 0);
  return <div style={{ textAlign: "center" }}><svg width={size} height={size} role="img" aria-label={`${label}: ${value} of ${max}`}><circle cx={size / 2} cy={size / 2} r={R} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth={8} />
    <circle cx={size / 2} cy={size / 2} r={R} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round" strokeDasharray={`${p * C} ${C}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dasharray .8s", filter: p >= 1 ? `drop-shadow(0 0 6px ${color})` : "none" }} />
    <text x={size / 2} y={size / 2 + 5} textAnchor="middle" fill="#ece9f8" fontSize="16" fontWeight="700">{value}/{max}</text></svg><p className="muted" style={{ fontSize: 12 }}>{label}</p></div>;
}

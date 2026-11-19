// Topic-mastery radar (SVG, no chart dependency). Values are 0..1.
export default function Radar({ data, size = 320 }: { data: { label: string; value: number }[]; size?: number }) {
  const n = data.length, c = size / 2, R = size / 2 - 52;
  if (n < 3) return <p className="muted" style={{ padding: 24 }}>Solve problems across at least 3 topics to unlock your radar.</p>;
  const pt = (i: number, v: number) => { const a = (Math.PI * 2 * i) / n - Math.PI / 2; return [c + Math.cos(a) * R * v, c + Math.sin(a) * R * v] as const; };
  const poly = data.map((d, i) => pt(i, Math.max(d.value, 0.04)).join(",")).join(" ");
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxWidth: size }} role="img" aria-label="Topic mastery radar">
      <defs><linearGradient id="rg" x1="0" x2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs>
      {[0.25, 0.5, 0.75, 1].map((r) => <polygon key={r} points={data.map((_, i) => pt(i, r).join(",")).join(" ")} fill="none" stroke="rgba(255,255,255,.09)" />)}
      {data.map((_, i) => <line key={i} x1={c} y1={c} x2={pt(i, 1)[0]} y2={pt(i, 1)[1]} stroke="rgba(255,255,255,.07)" />)}
      <polygon points={poly} fill="url(#rg)" fillOpacity=".3" stroke="url(#rg)" strokeWidth="2" />
      {data.map((d, i) => { const [x, y] = pt(i, 1.2); return <text key={d.label} x={x} y={y} fontSize="10" fill="#9a95b5" textAnchor="middle" dominantBaseline="middle">{d.label.length > 14 ? d.label.slice(0, 13) + "…" : d.label}</text>; })}
      {data.map((d, i) => { const [x, y] = pt(i, Math.max(d.value, 0.04)); return <circle key={i} cx={x} cy={y} r="3.5" fill="#a3e635" />; })}
    </svg>
  );
}

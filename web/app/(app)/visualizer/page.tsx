"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { ALGOS, Cell, Frame } from "@/lib/viz";
import { streamChat } from "@/lib/stream";

const TONE: Record<string, string> = { idle: "rgba(255,255,255,.07)", active: "rgba(139,92,246,.55)", compare: "rgba(251,191,36,.6)", done: "rgba(255,255,255,.03)", found: "rgba(163,230,53,.65)", wall: "#1b1830", path: "rgba(34,211,238,.7)" };
const cell = (c: Cell, extra: React.CSSProperties = {}): React.CSSProperties => ({ background: TONE[c.tone ?? "idle"], border: "1px solid rgba(255,255,255,.1)", borderRadius: 8, display: "grid", placeItems: "center", fontFamily: "var(--font-mono)", transition: "all .35s", ...extra });

function Stage({ f }: { f: Frame }) {
  if (f.kind === "graph") {
    const pos = Object.fromEntries(f.nodes.map((n) => [n.id, n]));
    return <svg viewBox="0 0 490 300" width="100%" role="img" aria-label="Graph or tree state" style={{ maxHeight: 320 }}>
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#22d3ee" /></marker><marker id="arrg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="rgba(255,255,255,.5)" /></marker></defs>
      {f.edges.map((e, i) => { const a = pos[e.a], b = pos[e.b]; if (!a || !b) return null; const on = e.tone === "path"; const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1, r = f.directed ? 24 : 0;
        return <g key={i}><line x1={a.x} y1={a.y} x2={b.x - (dx / L) * r} y2={b.y - (dy / L) * r} stroke={on ? "#22d3ee" : "rgba(255,255,255,.22)"} strokeWidth={on ? 3.5 : 1.6} markerEnd={f.directed ? `url(#${on ? "arr" : "arrg"})` : undefined} style={{ transition: "all .35s" }} />
        {!f.hideW && <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 6} fill="#9a95b5" fontSize="12" textAnchor="middle" className="mono">{e.w}</text>}</g>; })}
      {f.nodes.map((n) => <g key={n.id}><circle cx={n.x} cy={n.y} r={f.nodes.length > 12 ? 17 : 22} fill={TONE[n.tone]} stroke="rgba(255,255,255,.25)" style={{ transition: "all .35s" }} />
        <text x={n.x} y={n.y - 2} textAnchor="middle" fill="#ece9f8" fontSize="13" fontWeight="700">{n.id}</text><text x={n.x} y={n.y + 13} textAnchor="middle" fill="#ece9f8" fontSize="11" className="mono">{n.label}</text></g>)}
    </svg>;
  }
  if (f.kind === "array") {
    const max = Math.max(...f.cells.map((c) => Number(c.v)));
    const at = (i: number) => Object.entries(f.pointers).filter(([, v]) => v === i).map(([k]) => k).join("/");
    return <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 240, padding: "20px 0 34px" }}>
      {f.cells.map((c, i) => <div key={i} style={{ flex: 1, position: "relative", height: `${20 + (Number(c.v) / max) * 80}%`, ...cell(c, { alignItems: "start", paddingTop: 6, fontSize: 12 }) }}>{c.v}
        <span style={{ position: "absolute", bottom: -28, fontSize: 11, color: "var(--cyan)" }}>{at(i)}</span></div>)}
    </div>;
  }
  const grid = f.kind === "grid" ? f.cells : f.cells;
  const cols = grid[0].length + (f.kind === "table" ? 1 : 0);
  return <div style={{ overflowX: "auto" }}><div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, minmax(34px,52px))`, gap: 5, padding: "10px 0" }}>
    {f.kind === "table" && <><div />{f.cols.map((c, j) => <div key={j} className="mono muted" style={{ textAlign: "center", fontSize: 12 }}>{c}</div>)}</>}
    {grid.map((row, i) => [f.kind === "table" ? <div key={`h${i}`} className="mono muted" style={{ display: "grid", placeItems: "center", fontSize: 12 }}>{f.rows[i]}</div> : null,
      ...row.map((c, j) => <div key={`${i}-${j}`} style={cell(c, { aspectRatio: "1", fontSize: 13 })}>{c.v}</div>)])}
  </div></div>;
}

export default function Visualizer() {
  const [ai, setAi] = useState(0), [step, setStep] = useState(0), [play, setPlay] = useState(false), [speed, setSpeed] = useState(700);
  const algo = ALGOS[ai];
  const [text, setText] = useState(""), [inErr, setInErr] = useState(""), [custom, setCustom] = useState<Frame[] | null>(null);
  const frames = useMemo(() => custom ?? algo.run(), [algo, custom]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => { setStep(0); setPlay(false); setCustom(null); setInErr(""); setText(ALGOS[ai].input?.default ?? ""); }, [ai]);
  function runCustom() { if (!algo.input) return; try { const fr = algo.input.run(text); setCustom(fr); setStep(0); setPlay(false); setInErr(""); } catch (e) { setInErr((e as Error).message); } }
  useEffect(() => {
    if (!play) return;
    timer.current = setInterval(() => setStep((s) => { if (s >= frames.length - 1) { setPlay(false); return s; } return s + 1; }), speed);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [play, speed, frames.length]);
  const f = frames[Math.min(step, frames.length - 1)];
  const [q, setQ] = useState(""), [ans, setAns] = useState(""), [busy, setBusy] = useState(false);
  async function ask() {
    if (!q.trim() || busy) return; setBusy(true); setAns("");
    const upto = frames.slice(0, Math.min(step, frames.length - 1) + 1).map((fr, i) => ({ n: i + 1, note: fr.note })).slice(-40);
    try { const fin = await streamChat({ message: q, mode: "viz", trace: { algorithm: algo.title, frames: upto } }, (d) => setAns((a) => a + d)); setAns(fin.answer); } catch (e) { setAns(`⚠ ${(e as Error).message}`); } finally { setBusy(false); }
  }
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Algorithm <span className="grad-text">visualiser</span></h1><p className="muted">Each frame is a real state of the algorithm. Step through it and watch the highlighted line.</p></div>
      <div className="row" role="tablist">{ALGOS.map((a, i) => <button key={a.id} role="tab" aria-selected={ai === i} className={`btn ${ai === i ? "primary" : ""}`} onClick={() => setAi(i)}>{a.title}</button>)}</div>
      <div className="grid g2" style={{ alignItems: "start" }}>
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}><h2>{algo.title}</h2><span className="chip mono">{algo.complexity}</span></div>
          <p className="muted" style={{ fontSize: 13 }}>{algo.blurb}</p>
          {algo.input && <div className="row" style={{ margin: "10px 0 0", alignItems: "flex-start" }}><div style={{ flex: "1 1 240px" }}><label htmlFor="ci">Your input — {algo.input.hint}</label><input id="ci" className="mono" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && runCustom()} aria-invalid={!!inErr} aria-describedby="cie" /></div>
            <button className="btn primary" style={{ marginTop: 22 }} onClick={runCustom}>Run</button>{custom && <button className="btn" style={{ marginTop: 22 }} onClick={() => { setCustom(null); setText(algo.input!.default); setInErr(""); setStep(0); }}>Reset</button>}</div>}
          {inErr && <p id="cie" className="err" role="alert">{inErr}</p>}
          <Stage f={f} />
          {(f.kind === "graph" || (f.kind === "array" && f.aux)) && <div className="grid" style={{ gap: 6, marginTop: 6 }}>{(f.kind === "graph" ? f.aux : f.kind === "array" ? f.aux ?? [] : []).map((a) => <p key={a.name} className="mono" style={{ fontSize: 12 }}><span className="muted">{a.name}: </span>{a.value}</p>)}</div>}
          {f.kind === "grid" && f.queue !== undefined && <p className="mono muted" style={{ fontSize: 12 }}>queue: {f.queue || "∅"}</p>}
          <div className="card" style={{ background: "rgba(139,92,246,.1)", marginTop: 8 }} aria-live="polite"><p>{f.note}</p></div>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => setStep(0)} aria-label="Restart">⟲</button>
            <button className="btn" disabled={step === 0} onClick={() => { setPlay(false); setStep((s) => s - 1); }}>◀ Prev</button>
            <button className="btn primary" onClick={() => { if (step >= frames.length - 1) setStep(0); setPlay(!play); }}>{play ? "❚❚ Pause" : "▶ Play"}</button>
            <button className="btn" disabled={step >= frames.length - 1} onClick={() => { setPlay(false); setStep((s) => s + 1); }}>Next ▶</button>
            <label style={{ margin: 0, marginLeft: "auto" }}>Speed <input type="range" min={150} max={1500} step={50} value={1650 - speed} onChange={(e) => setSpeed(1650 - Number(e.target.value))} style={{ width: 110, padding: 0 }} /></label>
          </div>
          <div className="bar" style={{ marginTop: 12 }}><i style={{ width: `${(step / (frames.length - 1)) * 100}%` }} /></div>
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--card-b)" }}><label htmlFor="askviz">Ask the mentor about this step (it only sees frames 1–{Math.min(step, frames.length - 1) + 1})</label>
            <div className="row"><input id="askviz" style={{ flex: 1 }} value={q} maxLength={300} placeholder="Why did this pointer move? What if I remove this condition?" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} /><button className="btn primary" disabled={busy || !q.trim()} onClick={ask}>{busy ? "…" : "Ask"}</button></div>
            {ans && <div className="bubble ai" style={{ marginTop: 10 }}>{ans}</div>}</div>
          <p className="mono muted" style={{ fontSize: 11, marginTop: 6 }}>step {step + 1} / {frames.length}</p>
        </div>
        <div className="grid"><div className="card" style={{ background: "rgba(163,230,53,.06)" }}><p className="muted" style={{ fontSize: 12 }}>INVARIANT</p><p style={{ marginTop: 4 }}>{algo.invariant}</p></div><div className="card"><h2 style={{ marginBottom: 12 }}>Pseudocode</h2>
          <pre className="mono" style={{ fontSize: 13, lineHeight: 1.9, overflowX: "auto" }}>{algo.code.map((l, i) => <div key={i} style={{ padding: "0 10px", borderRadius: 6, background: i === f.line ? "rgba(34,211,238,.18)" : "transparent", boxShadow: i === f.line ? "inset 3px 0 var(--cyan)" : "none", transition: "all .25s" }}>{l}</div>)}</pre></div></div>
      </div>
    </div>
  );
}

"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import CrashCourse from "@/components/CrashCourse";

type P = { goal: { platform: string; target: number; deadline: string; weeks_left: number } | null; message?: string; current?: { rating: number; source: string }; gain_needed?: number;
  feasibility?: { verdict: string; explanation: string; pace_per_week: number | null; solve_velocity_per_week: number }; assumptions?: string[];
  weeks?: { week: number; starts: string; focus_patterns: { id: string; name: string; status: string }[]; problem_quota: number; rating_band: number[]; milestone_rating: number; also: string }[] };
const VC: Record<string, string> = { on_track: "mastered", behind: "weak", insufficient_data: "learning", already_met: "mastered" };

export default function Planner() {
  const [mode, setMode] = useState<"crash" | "rating">("crash");
  const [p, setP] = useState<P | null>(null), [err, setErr] = useState(""), [target, setTarget] = useState(1600), [date, setDate] = useState(() => new Date(Date.now() + 84 * 864e5).toISOString().slice(0, 10)), [busy, setBusy] = useState(false);
  const load = useCallback(() => api<P>("/planner").then(setP).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  async function save(e: React.FormEvent) { e.preventDefault(); setBusy(true); setErr(""); try { setP(await api<P>("/planner/goal", { method: "PUT", body: JSON.stringify({ target, deadline: new Date(date + "T12:00:00Z").toISOString(), platform: "codeforces" }) })); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } }
  const tabs = <div className="seg" role="tablist"><button role="tab" aria-selected={mode === "crash"} className={`btn ${mode === "crash" ? "primary" : ""}`} onClick={() => setMode("crash")}>🚀 Interview crash course (30/60 days)</button><button role="tab" aria-selected={mode === "rating"} className={`btn ${mode === "rating" ? "primary" : ""}`} onClick={() => setMode("rating")}>📈 Rating goal (Codeforces)</button></div>;
  if (mode === "crash") return <div className="grid" style={{ gap: 18 }}><div><h1>Learning <span className="grad-text">planner</span></h1><p className="muted">A fast, focused interview sprint for DSA and system design. It spends your time on what target companies reportedly ask.</p></div>{tabs}<CrashCourse /></div>;
  if (!p) return err ? <p className="err" role="alert">{err}</p> : <div className="skeleton" style={{ height: 200 }} />;
  return (
    <div className="grid" style={{ gap: 18 }}>
      <div><h1>Learning <span className="grad-text">planner</span></h1><p className="muted">Pick a Codeforces rating and a date. The plan is rebuilt from your latest data every time you open it, and it never promises an outcome.</p></div>{tabs}
      {err && <p className="err" role="alert">{err}</p>}
      <form onSubmit={save} className="card row" style={{ alignItems: "flex-end" }}><div><label htmlFor="tg">Target rating</label><input id="tg" type="number" min={800} max={4000} step={100} value={target} onChange={(e) => setTarget(+e.target.value)} /></div>
        <div><label htmlFor="dl">Deadline</label><input id="dl" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div><button className="btn primary" disabled={busy}>{p.goal ? "Update goal" : "Create plan"}</button>
        {p.goal && <button type="button" className="btn" onClick={async () => { await api("/planner/goal", { method: "DELETE" }); load(); }}>Remove</button>}</form>
      {!p.goal ? <div className="card"><p className="muted">{p.message}</p></div> : <>
        <div className="grid g3"><div className="card"><p className="muted">Now</p><h1 className="mono">{p.current?.rating}</h1><p className="muted" style={{ fontSize: 12 }}>{p.current?.source}</p></div><div className="card"><p className="muted">Target in {p.goal.weeks_left} weeks</p><h1 className="mono grad-text">{p.goal.target}</h1><p className="muted" style={{ fontSize: 12 }}>gain needed: {p.gain_needed}</p></div>
          <div className="card"><p className="muted">Feasibility</p><p style={{ margin: "8px 0" }}><span className={`st ${VC[p.feasibility!.verdict]}`}>{p.feasibility!.verdict.replace("_", " ")}</span></p><p className="muted" style={{ fontSize: 12 }}>{p.feasibility!.explanation}</p></div></div>
        <div className="card"><h2>Weekly plan</h2><div style={{ overflowX: "auto" }}><table className="t"><thead><tr><th>Week</th><th>Focus patterns</th><th>Problems</th><th>Rating band</th><th>Milestone</th><th>Also</th></tr></thead><tbody>
          {p.weeks!.map((w) => <tr key={w.week}><td className="mono">{w.week}<br /><span className="muted" style={{ fontSize: 11 }}>{w.starts}</span></td><td>{w.focus_patterns.map((f) => <span key={f.id} className="chip" style={{ marginRight: 4 }}>{f.name}</span>)}</td><td className="mono">{w.problem_quota}</td><td className="mono">{w.rating_band[0]}–{w.rating_band[1]}</td><td className="mono">{w.milestone_rating}</td><td className="muted" style={{ fontSize: 12 }}>{w.also}</td></tr>)}</tbody></table></div></div>
        <details className="card"><summary><h2 style={{ display: "inline" }}>Assumptions ▸</h2></summary>{p.assumptions!.map((a) => <p key={a} className="muted" style={{ fontSize: 13, marginTop: 8 }}>• {a}</p>)}<p className="muted" style={{ fontSize: 13, marginTop: 8 }}>• Pace {p.feasibility!.pace_per_week ?? "unknown"} rating/week; verified solve rate {p.feasibility!.solve_velocity_per_week}/week.</p></details></>}
    </div>
  );
}

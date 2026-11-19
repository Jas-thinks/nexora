"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type S = { id: number; status: string; minutes: number; seconds_left: number; overtime: boolean; problem: { id: number; name: string; platform: string; rating: number | null; url: string; note: string }; transcript: { role: string; content: string }[];
  rubric: { measured: { time_used_seconds: number; candidate_turns: number; code_runs: number; note: string }; scored: { scores: Record<string, number>; summary: string; improvements: string[]; source: string } | null; message: string | null } | null; self_eval: Record<string, number> | null };
const DIMS = ["approach", "communication", "complexity", "edge_cases"];
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function Interview() {
  const [s, setS] = useState<S | null>(null), [past, setPast] = useState<{ id: number; status: string; started_at: string; scores: Record<string, number> | null }[]>([]), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(""), [mins, setMins] = useState(45), [left, setLeft] = useState(0), [se, setSe] = useState<Record<string, number>>({});
  const end = useRef<HTMLDivElement>(null);
  const loadPast = useCallback(() => api<typeof past>("/interview").then(setPast).catch(() => {}), []);
  useEffect(() => { loadPast(); }, [loadPast]);
  useEffect(() => { if (s) setLeft(s.seconds_left); }, [s]);
  useEffect(() => { if (!s || s.status !== "running") return; const t = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000); return () => clearInterval(t); }, [s]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [s?.transcript.length]);
  async function start() { setErr(""); setBusy(true); try { setS(await api<S>("/interview", { method: "POST", body: JSON.stringify({ minutes: mins }) })); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  async function open(id: number) { setS(await api<S>(`/interview/${id}`)); }
  async function say() { if (!s || !msg.trim()) return; const text = msg; setMsg(""); setBusy(true); setS({ ...s, transcript: [...s.transcript, { role: "user", content: text }] });
    try { await api(`/interview/${s.id}/say`, { method: "POST", body: JSON.stringify({ message: text }) }); await open(s.id); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  async function finish() { if (!s) return; setBusy(true); try { setS(await api<S>(`/interview/${s.id}/finish`, { method: "POST", body: JSON.stringify({ self_eval: se }) })); loadPast(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div><h1>Mock <span className="grad-text">interview</span></h1><p className="muted">A timed coding interview. Open the problem on its platform, explain your approach to the interviewer, and defend it. Scoring is an estimate of your reasoning, never a verified solve.</p></div>
      {err && <p className="err" role="alert">{err}</p>}
      {!s ? <div className="grid g2"><div className="card"><h2>Start an interview</h2><p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>The problem is picked from your interview-prep sheets, near your level.</p><div className="row"><select aria-label="Duration" value={mins} onChange={(e) => setMins(+e.target.value)} style={{ width: 140 }}>{[20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} minutes</option>)}</select><button className="btn primary" disabled={busy} onClick={start}>{busy ? "Picking…" : "Begin"}</button></div></div>
        <div className="card"><h2>Past interviews</h2>{past.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>None yet.</p> : past.map((p) => <p key={p.id} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 8 }}><button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={() => open(p.id)}>{new Date(p.started_at).toLocaleString()}</button><span>{p.scores ? Object.values(p.scores).join("·") : p.status}</span></p>)}</div></div> : <>
        <div className="card row" style={{ justifyContent: "space-between" }}><div><span className="chip">{s.problem.platform}</span> <a href={s.problem.url} target="_blank" rel="noreferrer noopener"><b style={{ fontSize: 20 }}>{s.problem.name} ↗</b></a><p className="muted" style={{ fontSize: 12, marginTop: 4 }}>{s.problem.note}</p></div>
          <div style={{ textAlign: "center" }}><h1 className="mono" style={{ color: left < 120 && s.status === "running" ? "var(--rose)" : undefined }}>{s.status === "running" ? mmss(left) : "done"}</h1>{s.overtime && <span className="st weak">overtime</span>}</div></div>
        <div className="card" style={{ minHeight: 280, maxHeight: "46vh", overflowY: "auto", display: "grid", gap: 10, alignContent: "start" }} aria-live="polite">{s.transcript.length === 0 && <p className="muted">Start by describing the problem in your own words and your first idea.</p>}
          {s.transcript.map((m, i) => <div key={i} className={`bubble ${m.role === "user" ? "me" : "ai"}`}><span className="muted" style={{ fontSize: 11 }}>{m.role === "user" ? "You" : "Interviewer"}</span><br />{m.content}</div>)}<div ref={end} /></div>
        {s.status === "running" ? <><div className="row" style={{ alignItems: "flex-end" }}><div style={{ flex: 1 }}><label htmlFor="m">Your answer</label><textarea id="m" rows={3} maxLength={4000} value={msg} onChange={(e) => setMsg(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) say(); }} /></div><button className="btn primary" disabled={busy || !msg.trim()} onClick={say}>{busy ? "…" : "Send"}</button></div>
          <details className="card"><summary><h2 style={{ display: "inline" }}>Finish & score ▸</h2></summary><p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>Optional self-assessment (1–5):</p><div className="row">{DIMS.map((d) => <div key={d}><label htmlFor={`se-${d}`}>{d.replace("_", " ")}</label><input id={`se-${d}`} type="number" min={1} max={5} style={{ width: 80 }} value={se[d] ?? ""} onChange={(e) => setSe({ ...se, [d]: +e.target.value })} /></div>)}</div><button className="btn primary" style={{ marginTop: 10 }} disabled={busy} onClick={finish}>End interview</button></details></> :
          <div className="card"><h2>Result</h2>{s.rubric?.scored ? <><div className="row" style={{ gap: 18, margin: "10px 0" }}>{DIMS.map((d) => <div key={d} style={{ textAlign: "center" }}><h1 className="mono">{s.rubric!.scored!.scores[d]}<span className="muted" style={{ fontSize: 14 }}>/5</span></h1><span className="muted" style={{ fontSize: 12 }}>{d.replace("_", " ")}</span></div>)}</div><p>{s.rubric.scored.summary}</p>{s.rubric.scored.improvements.map((i) => <p key={i} className="muted" style={{ fontSize: 13 }}>→ {i}</p>)}<p className="muted" style={{ fontSize: 11, marginTop: 8 }}>{s.rubric.scored.source}</p></> : <p className="muted" style={{ margin: "8px 0" }}>{s.rubric?.message}</p>}
            {s.self_eval && <p style={{ fontSize: 13, marginTop: 8 }}>Your self-assessment: {Object.entries(s.self_eval).map(([k, v]) => `${k.replace("_", " ")} ${v}/5`).join(" · ")}</p>}<p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Measured: {s.rubric?.measured.candidate_turns} answers, {s.rubric?.measured.code_runs} code runs, {mmss(s.rubric?.measured.time_used_seconds ?? 0)} used. {s.rubric?.measured.note}</p><button className="btn" style={{ marginTop: 10 }} onClick={() => { setS(null); loadPast(); }}>New interview</button></div>}</>}
    </div>
  );
}

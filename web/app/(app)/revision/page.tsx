"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bars } from "@/components/charts";

type Item = { problem: { id: number; name: string; url: string; platform: string; rating: number | null }; due_at: string; box: number; last_result: string };
type O = { due: Item[]; upcoming_7d: Item[]; total_scheduled: number; boxes: Record<string, number>; schedule_days: number[]; consistency: { reviews_90d: number; good_rate: number | null; on_time_rate: number | null; avg_days_overdue_now: number; note: string } };
const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);

export default function Revision() {
  const [o, setO] = useState<O | null>(null), [err, setErr] = useState(""), [busy, setBusy] = useState<number | null>(null);
  const load = useCallback(() => api<O>("/revision/overview").then(setO).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  async function rate(id: number, result: "good" | "again") { setBusy(id); try { await api(`/revision/${id}/review`, { method: "POST", body: JSON.stringify({ result }) }); await load(); window.dispatchEvent(new Event("nexora:refresh")); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); } }
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!o) return <div className="skeleton" style={{ height: 200 }} />;
  const c = o.consistency;
  return (
    <div className="grid" style={{ gap: 18 }}>
      <div><h1>Revision <span className="grad-text">centre</span></h1><p className="muted">Spaced repetition ({o.schedule_days.join(" → ")} days). Problems you solved only after struggling are scheduled automatically.</p></div>
      <div className="grid g3"><div className="card"><p className="muted">Due now</p><h1 className="mono grad-text">{o.due.length}</h1></div><div className="card"><p className="muted">Next 7 days</p><h1 className="mono">{o.upcoming_7d.length}</h1></div><div className="card"><p className="muted">Scheduled in total</p><h1 className="mono">{o.total_scheduled}</h1></div></div>
      <div className="card"><h2>Due for review</h2>{o.due.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>Nothing due. Complete the Daily Challenge or solve problems after failing them and they will appear here.</p> :
        o.due.map((i) => <div key={i.problem.id} className="row" style={{ justifyContent: "space-between", padding: "12px 0", borderTop: "1px solid var(--card-b)" }}>
          <div><a href={i.problem.url} target="_blank" rel="noreferrer noopener"><b>{i.problem.name}</b> ↗</a> <span className="chip">{i.problem.platform}</span> <span className="chip">box {i.box}</span><p className="muted" style={{ fontSize: 12 }}>last: {i.last_result || "—"} · due {new Date(i.due_at).toLocaleDateString()}</p></div>
          <div className="row"><button className="btn" disabled={busy === i.problem.id} onClick={() => rate(i.problem.id, "again")}>Forgot it</button><button className="btn primary" disabled={busy === i.problem.id} onClick={() => rate(i.problem.id, "good")}>Solved again ✓</button></div></div>)}
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Re-solve it on the platform, then report honestly. “Forgot it” resets the interval to 1 day.</p></div>
      <div className="grid g2">
        <div className="card"><h2>How consistent is your revision?</h2><div className="row" style={{ gap: 6, margin: "10px 0" }}><span className="chip">{c.reviews_90d} reviews / 90 d</span><span className="chip">success {pct(c.good_rate)}</span><span className="chip">on time {pct(c.on_time_rate)}</span><span className="chip">avg {c.avg_days_overdue_now} d overdue now</span></div><p className="muted" style={{ fontSize: 12 }}>{c.note}</p></div>
        <div className="card"><h2>Leitner boxes</h2><div style={{ marginTop: 10 }}><Bars data={Object.entries(o.boxes).map(([k, v]) => [`box ${k} (${o.schedule_days[+k]} d)`, v] as [string, number])} color="var(--cyan)" /></div></div></div>
      {o.upcoming_7d.length > 0 && <div className="card"><h2>Coming up</h2>{o.upcoming_7d.map((i) => <p key={i.problem.id} style={{ fontSize: 13, marginTop: 6 }}>{new Date(i.due_at).toLocaleDateString()} · {i.problem.name}</p>)}</div>}
    </div>
  );
}

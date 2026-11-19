"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import Radar from "@/components/Radar";
import ProblemRow, { P } from "@/components/ProblemRow";

type Mastery = { solved: number; estimated_rating: number; confidence: string; topics: { topic: string; mastery: number; attempts: number }[] };
type Rec = { estimated_rating: number; window: number[]; note: string; items: (P & { problem_id: number })[] };

export default function Dashboard() {
  const [m, setM] = useState<Mastery | null>(null), [r, setR] = useState<Rec | null>(null), [err, setErr] = useState("");
  const load = () => Promise.all([api<Mastery>("/mastery"), api<Rec>("/recommendations?count=3")]).then(([a, b]) => { setM(a); setR(b); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!m || !r) return <div className="grid g2"><div className="skeleton" style={{ height: 220 }} /><div className="skeleton" style={{ height: 220 }} /></div>;
  const radar = [...m.topics].sort((a, b) => b.attempts - a.attempts).slice(0, 8).map((t) => ({ label: t.topic, value: t.mastery }));
  const weak = m.topics.slice(0, 3);
  return (
    <div className="grid" style={{ gap: 24 }}>
      <div><h1>Your <span className="grad-text">climb</span></h1><p className="muted">Everything here is computed from problems you report. Ratings are estimates, not official.</p></div>
      <div className="grid g3">
        <div className="card"><p className="muted">Estimated rating</p><h1 className="mono grad-text" style={{ fontSize: 48 }}>{m.estimated_rating}</h1><span className="chip">confidence: {m.confidence}</span></div>
        <div className="card"><p className="muted">Problems solved</p><h1 className="mono" style={{ fontSize: 48 }}>{m.solved}</h1></div>
        <div className="card"><p className="muted">Next target window</p><h1 className="mono" style={{ fontSize: 36 }}>{r.window[0]}–{r.window[1]}</h1></div>
      </div>
      <div className="grid g2">
        <div className="card"><h2>Topic mastery</h2><div style={{ display: "grid", placeItems: "center" }}><Radar data={radar} /></div></div>
        <div className="card"><h2>Focus areas</h2>
          {weak.length === 0 ? <p className="muted" style={{ marginTop: 12 }}>No data yet. Solve or attempt a few problems and your weakest topics appear here.</p> :
            weak.map((t) => <div key={t.topic} style={{ marginTop: 14 }}><div className="row" style={{ justifyContent: "space-between" }}><span>{t.topic}</span><span className="mono muted">{Math.round(t.mastery * 100)}%</span></div><div className="bar"><i style={{ width: `${t.mastery * 100}%` }} /></div></div>)}
        </div>
      </div>
      <div><div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}><h2>Do this next</h2><Link href="/practice" className="btn">More →</Link></div>
        {r.items.length === 0 ? <div className="card"><p className="muted">No catalog loaded yet. An admin needs to sync the Codeforces catalog (POST /catalog/sync/codeforces).</p></div> :
          <div className="grid">{r.items.map((p) => <ProblemRow key={p.problem_id} p={{ ...p, id: p.problem_id }} onDone={load} />)}</div>}
      </div>
    </div>
  );
}

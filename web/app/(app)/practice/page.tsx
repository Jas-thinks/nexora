"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import ProblemRow, { P } from "@/components/ProblemRow";
import { BANDS } from "@/lib/rating";

type Rec = { estimated_rating: number; confidence: string; window: number[]; note: string; items: (P & { problem_id: number })[] };

export default function Practice() {
  const [target, setTarget] = useState<number | "">(""), [topic, setTopic] = useState("");
  const [rec, setRec] = useState<Rec | null>(null), [err, setErr] = useState(""), [loading, setLoading] = useState(true);
  const [band, setBand] = useState(0), [browse, setBrowse] = useState<P[] | null>(null);
  const load = () => { setLoading(true); setErr("");
    const qs = new URLSearchParams({ count: "8" }); if (target) qs.set("target_rating", String(target)); if (topic.trim()) qs.set("topic", topic.trim().toLowerCase());
    api<Rec>(`/recommendations?${qs}`).then(setRec).catch((e) => setErr(e.message)).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, [target]); // eslint-disable-line
  useEffect(() => { setBrowse(null); const [lo, hi] = BANDS[band]; api<{ items: P[] }>(`/problems?min_rating=${lo}&max_rating=${hi - 1}&limit=30`).then((r) => setBrowse(r.items)).catch(() => setBrowse([])); }, [band]);
  return (
    <div className="grid" style={{ gap: 24 }}>
      <div><h1>Practice <span className="grad-text">ladder</span></h1><p className="muted">Suggestions target your weakest topics at a difficulty just above your estimated level.</p></div>
      <div className="card row">
        <div style={{ flex: "1 1 180px" }}><label htmlFor="t">Target difficulty</label>
          <select id="t" value={target} onChange={(e) => setTarget(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Auto (your level{rec ? `: ${rec.estimated_rating}` : ""})</option>{[800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2200].map((r) => <option key={r} value={r}>{r}</option>)}
          </select></div>
        <div style={{ flex: "1 1 180px" }}><label htmlFor="tp">Topic (optional)</label><input id="tp" placeholder="e.g. dp, graphs, greedy" value={topic} onChange={(e) => setTopic(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} /></div>
        <button className="btn primary" style={{ alignSelf: "flex-end" }} onClick={load}>Suggest</button>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
      {loading ? <div className="grid">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 84 }} />)}</div> :
        rec && (<div className="grid">
          <p className="muted" style={{ fontSize: 13 }}>{rec.note} Window: {rec.window[0]}–{rec.window[1]}.</p>
          {rec.items.length === 0 ? <div className="card"><p>No matching unsolved problems. Try another topic or difficulty, or ask an admin to sync the catalog.</p></div> :
            rec.items.map((p) => <ProblemRow key={p.problem_id} p={{ ...p, id: p.problem_id }} onDone={load} />)}</div>)}
      <div><h2 style={{ marginBottom: 12 }}>Browse by difficulty</h2>
        <div className="row" role="tablist" style={{ marginBottom: 14 }}>{BANDS.map(([, , l], i) => <button key={l} role="tab" aria-selected={band === i} className={`btn ${band === i ? "primary" : ""}`} onClick={() => setBand(i)}>{l}</button>)}</div>
        {!browse ? <div className="skeleton" style={{ height: 80 }} /> : browse.length === 0 ? <p className="muted">Nothing in this band yet.</p> : <div className="grid">{browse.map((p) => <ProblemRow key={p.id} p={p} />)}</div>}
      </div>
    </div>
  );
}

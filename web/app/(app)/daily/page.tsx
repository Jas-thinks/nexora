"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ratingColor } from "@/lib/rating";
import { celebrate } from "@/components/Confetti";

type Hint = { level: number; text: string | null; unavailable?: string };
type Ch = { id: number; day: string; mode: string; status: string; swaps: number; pattern: string; hints: Hint[];
  problem: { id: number; name: string; url: string; rating: number | null; platform: string; source_difficulty: string | null; tags: string[]; provenance: string };
  explanation: { why: string[]; pattern: { name: string; status: string; score: number }; difficulty: string; prerequisites: { name: string; status: string }[];
    prerequisite_gaps: string[]; connection_note: string; after_this: string[]; top_objectives: { objective: string; contribution: number }[]; evidence: string[]; data_confidence: string } };
type Pat = { id: string; name: string; kind: string };
const MODES: [string, string][] = [["personalized", "For me"], ["cp", "Competitive"], ["interview", "Interview"], ["revision", "Revision"], ["topic", "Topic"]];

export default function Daily() {
  const [mode, setMode] = useState("personalized"), [path, setPath] = useState(""), [topic, setTopic] = useState("binary-search");
  const [pats, setPats] = useState<Pat[]>([]), [ch, setCh] = useState<Ch | null>(null), [err, setErr] = useState(""), [loading, setLoading] = useState(true);
  const [shown, setShown] = useState(0), [form, setForm] = useState({ solved: true, self_difficulty: 3, understanding: 3, editorial_viewed: false }), [busy, setBusy] = useState(false);
  const [hist, setHist] = useState<{ items: Ch[]; completed: number; total: number } | null>(null), [due, setDue] = useState<{ due: unknown[]; upcoming: number } | null>(null);
  const load = useCallback(() => {
    setLoading(true); setErr(""); setShown(0);
    const qs = new URLSearchParams({ mode }); if (path) qs.set("path", path); if (mode === "topic") qs.set("topic", topic);
    api<Ch>(`/daily?${qs}`).then(setCh).catch((e) => { setCh(null); setErr(e.message); }).finally(() => setLoading(false));
    api<typeof hist>("/daily/history?limit=10").then(setHist).catch(() => {}); api<typeof due>("/revision/due").then(setDue).catch(() => {});
  }, [mode, path, topic]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api<{ patterns: Pat[] }>("/patterns").then((r) => setPats(r.patterns.filter((p) => p.kind !== "category"))).catch(() => {}); }, []);
  async function finish() { if (!ch) return; setBusy(true);
    try { setCh(await api<Ch>(`/daily/${ch.id}/complete`, { method: "POST", body: JSON.stringify({ ...form, hints_used: shown }) })); load2(); window.dispatchEvent(new Event("nexora:refresh")); if (form.solved) celebrate(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  const load2 = () => { api<typeof hist>("/daily/history?limit=10").then(setHist).catch(() => {}); api<typeof due>("/revision/due").then(setDue).catch(() => {}); };
  async function swap() { if (!ch) return; setBusy(true); try { setCh(await api<Ch>(`/daily/${ch.id}/swap`, { method: "POST", body: JSON.stringify({ reason: "student requested" }) })); setShown(0); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  const e = ch?.explanation;
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Daily <span className="grad-text">Challenge</span></h1><p className="muted">One problem, chosen from your own history: weaknesses, revision, difficulty and variety — with the reasons shown.</p></div>
      <div className="card row" style={{ justifyContent: "space-between" }}>
        <div className="seg" role="tablist" aria-label="Mode">{MODES.map(([k, l]) => <button key={k} role="tab" aria-selected={mode === k} className={`btn ${mode === k ? "primary" : ""}`} onClick={() => setMode(k)}>{l}</button>)}</div>
        <div className="row">
          {mode === "topic" && <select aria-label="Pattern" value={topic} onChange={(x) => setTopic(x.target.value)} style={{ width: 220 }}>{pats.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>}
          <select aria-label="Difficulty path" value={path} onChange={(x) => setPath(x.target.value)} style={{ width: 160 }}><option value="">Auto difficulty</option><option value="beginner">Beginner path</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select>
        </div>
      </div>
      {err && <div className="card"><p className="err" role="alert">{err}</p></div>}
      {loading ? <div className="skeleton" style={{ height: 260 }} /> : ch && e && (<>
        <div className="card hover">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div><span className="chip">{ch.day} · {ch.mode} · {ch.status}</span>
              <h2 style={{ fontSize: 28, margin: "10px 0" }}><a href={ch.problem.url} target="_blank" rel="noreferrer noopener">{ch.problem.name} ↗</a></h2>
              <div className="row" style={{ gap: 6 }}><span className="pill mono" style={{ color: ratingColor(ch.problem.rating), background: "rgba(255,255,255,.06)" }}>{ch.problem.rating ?? ch.problem.source_difficulty ?? "unrated"}</span>
                <span className="chip">{ch.problem.platform}</span>{ch.problem.tags.slice(0, 4).map((t) => <span key={t} className="chip">{t}</span>)}</div></div>
            <div className="row"><Link className="btn" href={`/studio?problem=${ch.problem.id}`}>Open in Studio</Link><a className="btn primary" href={ch.problem.url} target="_blank" rel="noreferrer noopener">Solve on {ch.problem.platform} →</a></div>
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>{ch.problem.provenance}</p>
        </div>
        <div className="grid g2">
          <div className="card"><h2>Why this problem</h2>
            {e.why.map((w, i) => <p key={i} style={{ marginTop: 10 }}>{w}</p>)}
            <p className="muted" style={{ marginTop: 10 }}>{e.difficulty}</p>
            <p className="muted" style={{ marginTop: 6 }}>{e.connection_note}</p>
            <div className="row" style={{ marginTop: 12, gap: 6 }}>{e.top_objectives.map((o) => <span key={o.objective} className="chip">{o.objective} +{o.contribution}</span>)}</div>
            <details style={{ marginTop: 12 }}><summary className="muted">▸ Evidence behind this decision</summary>{e.evidence.map((x, i) => <p key={i} className="muted" style={{ fontSize: 13, marginTop: 6 }}>• {x}</p>)}<p className="muted" style={{ fontSize: 12, marginTop: 6 }}>{e.data_confidence}</p></details>
          </div>
          <div className="card"><h2>Pattern: {e.pattern.name} <span className={`st ${e.pattern.status}`}>{e.pattern.status}</span></h2>
            <p className="muted" style={{ marginTop: 10 }}>Prerequisites</p>
            <div className="row" style={{ gap: 6, marginTop: 6 }}>{e.prerequisites.length ? e.prerequisites.map((p) => <span key={p.name} className={`st ${p.status}`}>{p.name}</span>) : <span className="muted">None</span>}</div>
            {e.prerequisite_gaps.length > 0 && <p className="err" style={{ marginTop: 8 }}>Shaky prerequisites: {e.prerequisite_gaps.join(", ")}</p>}
            <p className="muted" style={{ marginTop: 14 }}>After this, practise</p><p>{e.after_this.join(" · ")}</p>
          </div>
        </div>
        <div className="grid g2">
          <div className="card"><h2>Hints</h2><p className="muted" style={{ fontSize: 13 }}>Reveal one at a time. Using hints is recorded as a learning signal, not a penalty.</p>
            {ch.hints.slice(0, shown).map((h) => <p key={h.level} style={{ marginTop: 10 }}><b>Hint {h.level}.</b> {h.text ?? <span className="muted">{h.unavailable}</span>}</p>)}
            {shown < ch.hints.length && <button className="btn" style={{ marginTop: 12 }} onClick={() => setShown(shown + 1)}>Reveal hint {shown + 1}</button>}
          </div>
          <div className="card"><h2>Finish</h2>
            {ch.status === "completed" ? <p style={{ marginTop: 10 }}><span className="st mastered">Recorded</span> Your feedback now shapes tomorrow&apos;s pick and schedules a review.</p> : <div className="grid" style={{ gap: 10, marginTop: 10 }}>
              <div className="seg"><button className={`btn ${form.solved ? "primary" : ""}`} onClick={() => setForm({ ...form, solved: true })}>I solved it</button><button className={`btn ${!form.solved ? "primary" : ""}`} onClick={() => setForm({ ...form, solved: false })}>I got stuck</button></div>
              <div><label htmlFor="sd">How hard did it feel? ({form.self_difficulty}/5)</label><input id="sd" type="range" min={1} max={5} value={form.self_difficulty} onChange={(x) => setForm({ ...form, self_difficulty: +x.target.value })} /></div>
              <div><label htmlFor="un">How well do you understand the solution? ({form.understanding}/5)</label><input id="un" type="range" min={1} max={5} value={form.understanding} onChange={(x) => setForm({ ...form, understanding: +x.target.value })} /></div>
              <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" style={{ width: "auto" }} checked={form.editorial_viewed} onChange={(x) => setForm({ ...form, editorial_viewed: x.target.checked })} /> I read the editorial</label>
              <div className="row"><button className="btn primary" disabled={busy} onClick={finish}>Save</button>{ch.swaps === 0 && <button className="btn" disabled={busy} onClick={swap}>Swap problem (once)</button>}</div>
              <p className="muted" style={{ fontSize: 12 }}>Self-reported. Syncing a platform later lets Nexora verify solves automatically.</p></div>}
          </div></div>
      </>)}
      <div className="grid g2">
        <div className="card"><h2>Revision queue</h2><p className="muted" style={{ marginTop: 8 }}>{due ? `${due.due.length} due now · ${due.upcoming} scheduled` : "…"}. Reviews are scheduled after each challenge (1 → 3 → 7 → 21 → 60 days).</p></div>
        <div className="card"><h2>History</h2>{!hist ? <div className="skeleton" /> : hist.items.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>Nothing yet.</p> :
          <><p className="muted" style={{ marginTop: 8 }}>{hist.completed} completed of {hist.total} shown</p>{hist.items.map((h) => <p key={h.id} style={{ fontSize: 13, marginTop: 6 }}><span className="mono muted">{h.day}</span> {h.problem.name} <span className={`st ${h.status === "completed" ? "mastered" : "unexplored"}`}>{h.status}</span></p>)}</>}</div>
      </div>
    </div>
  );
}

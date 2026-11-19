"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Bars, Donut, Heatmap, LineChart } from "@/components/charts";
import Tilt from "@/components/Tilt";

type Topic = { topic: string; attempted: number; solved: number; acceptance: number; trend: number | null };
type A = { range: string; from: string | null; to: string; empty?: boolean; message?: string; definitions: Record<string, { definition: string; source: string }>;
  freshness: { profiles: { platform: string; handle: string; data_level: string; last_synced_at: string | null }[]; note: string };
  summary: Record<string, number | null>; heatmap: { date: string; submissions: number; accepted: number }[];
  weekly: { week: string; submissions: number; accepted: number; acceptance: number | null; solved: number; mean_solved_rating: number | null }[];
  verdicts: Record<string, number>; languages: Record<string, number>; language_unknown: number; platforms: Record<string, number>; solved_by_tier: Record<string, number>; solved_by_rating_band: Record<string, number>; difficulty_note: string;
  ratings: Record<string, { contests: number; current: number | null; peak: number | null; volatility: number | null; last5_change: number | null; median_rank: number | null; median_performance: number | null; history: { at: string; rating: number | null; contest: string; rank: number | null }[] }>;
  contest_accuracy: { in_contest: { n: number; acceptance: number | null }; practice: { n: number; acceptance: number | null }; unknown_excluded: number } | null;
  improvement: { first_half: { n: number; acceptance: number | null }; second_half: { n: number; acceptance: number | null }; acceptance_delta: number | null; verdict: string | null; note: string } | null;
  abandoned: { count: number; examples: { problem_id: number; name: string | null; attempts: number }[] }; repeated_failures: { count: number; examples: { problem_id: number; name: string | null; attempts: number }[] };
  inactivity_gaps: { days: number; after: string }[];
  topics: { strongest: Topic[]; weakest: Topic[]; improving: Topic[]; stagnating: Topic[]; note: string };
  patterns: { coverage: { total_patterns: number; by_status: Record<string, number>; due_for_revision: number }; weakest: { id: string; name: string; status: string; score: number }[] };
  next_best_action: { action: string; why: string; href: string }[] };
const pct = (v: number | null | undefined) => v == null ? "—" : `${Math.round(v * 100)}%`;

export default function Analytics() {
  const [rng, setRng] = useState("90d"), [a, setA] = useState<A | null>(null), [err, setErr] = useState(""), [loading, setLoading] = useState(true);
  useEffect(() => { setLoading(true); setErr(""); api<A>(`/analytics/me?range=${rng}`).then(setA).catch((e) => setErr(e.message)).finally(() => setLoading(false)); }, [rng]);
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!a) return <div className="grid g2"><div className="skeleton" style={{ height: 200 }} /><div className="skeleton" style={{ height: 200 }} /></div>;
  const s = a.summary; const def = (k: string) => a.definitions[k] ? `${a.definitions[k].definition} (source: ${a.definitions[k].source})` : "";
  const tiles: [string, string, string, string][] = [["Solved", String(s.solved ?? "—"), "solved", "in range"], ["Acceptance", pct(s.acceptance_rate), "acceptance_rate", `${s.accepted ?? 0}/${s.submissions ?? 0} submissions`], ["Consistency", pct(s.consistency), "consistency", `${s.active_days ?? 0} active days`],
    ["Streak", `${s.streak ?? 0}🔥`, "streak", `best ${s.longest_streak ?? 0}`], ["First-try rate", pct(s.first_try_rate), "first_try_rate", "unfamiliar problems"]];
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><h1>My <span className="grad-text">analytics</span></h1><p className="muted">Computed from your own submissions. Hover a metric for its definition and source. Unknown data is shown as “—”, never zero.</p></div>
        <div className="seg" role="tablist">{["30d", "90d", "180d", "365d", "all"].map((r) => <button key={r} role="tab" aria-selected={rng === r} className={`btn ${rng === r ? "primary" : ""}`} onClick={() => setRng(r)}>{r}</button>)}</div></div>
      {a.empty ? <div className="card"><h2>No data yet</h2><p className="muted" style={{ margin: "8px 0 14px" }}>{a.message}</p><Link className="btn primary" href="/connections">Connect a platform →</Link></div> : (<>
        <div className="grid g3" style={{ opacity: loading ? 0.6 : 1 }}>{tiles.map(([k, v, d, sub]) => <Tilt key={k} className="card" ><p className="muted" title={def(d)} style={{ cursor: "help" }}>{k} ⓘ</p><h1 className="mono grad-text" style={{ fontSize: 34 }}>{v}</h1><span className="chip">{sub}</span></Tilt>)}</div>
        <div className="card" style={{ borderColor: "rgba(139,92,246,.5)" }}><h2>Your next best action</h2><div className="grid" style={{ gap: 8, marginTop: 10 }}>{a.next_best_action.map((n) => <Link key={n.action} href={n.href} className="row" style={{ justifyContent: "space-between", padding: "10px 12px", borderRadius: 12, background: "rgba(255,255,255,.04)" }}><span><b>{n.action}</b> <span className="muted" style={{ fontSize: 13 }}>— {n.why}</span></span><span>→</span></Link>)}</div></div>
        <div className="card"><h2 style={{ marginBottom: 10 }}>Activity, last 365 days</h2><Heatmap data={a.heatmap} /></div>
        <div className="grid g2">
          <div className="card"><h2>Acceptance rate by week</h2><LineChart series={a.weekly.map((w) => ({ x: w.week, y: w.acceptance == null ? null : Math.round(w.acceptance * 100), label: `${w.accepted}/${w.submissions} accepted` }))} fmt={(v) => `${v}%`} color="#a3e635" /></div>
          <div className="card"><h2>Is difficulty increasing?</h2><p className="muted" style={{ fontSize: 12 }} title={def("difficulty_trend")}>Mean rating of newly solved rated problems ⓘ</p><LineChart series={a.weekly.map((w) => ({ x: w.week, y: w.mean_solved_rating, label: `${w.solved} solved` }))} color="#8b5cf6" /></div></div>
        {Object.entries(a.ratings).map(([pl, r]) => <div key={pl} className="card"><div className="row" style={{ justifyContent: "space-between" }}><h2>{pl} rating</h2><div className="row" style={{ gap: 6 }}><span className="chip">current {r.current ?? "—"}</span><span className="chip">peak {r.peak ?? "—"}</span><span className="chip">{r.contests} contests</span>
          {r.volatility != null && <span className="chip">volatility ±{r.volatility}</span>}{r.last5_change != null && <span className="chip" style={{ color: r.last5_change >= 0 ? "var(--lime)" : "var(--rose)" }}>last 5: {r.last5_change >= 0 ? "+" : ""}{r.last5_change}</span>}{r.median_performance != null && <span className="chip">median perf {r.median_performance}</span>}</div></div>
          <LineChart series={r.history.map((h) => ({ x: h.at.slice(0, 10), y: h.rating, label: `${h.contest}${h.rank ? ` · rank ${h.rank}` : ""}` }))} /></div>)}
        <div className="grid g3">
          <div className="card"><h2 style={{ marginBottom: 10 }}>Verdicts</h2><Donut data={a.verdicts} /></div>
          <div className="card"><h2 style={{ marginBottom: 10 }}>Languages</h2>{Object.keys(a.languages).length ? <Bars data={Object.entries(a.languages)} color="var(--cyan)" /> : <p className="muted">No language data.</p>}{a.language_unknown > 0 && <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>{a.language_unknown} submissions have no language recorded.</p>}</div>
          <div className="card"><h2 style={{ marginBottom: 10 }}>Solved by difficulty</h2><Bars data={Object.entries(a.solved_by_tier)} color="var(--lime)" /><p className="muted" style={{ fontSize: 11, marginTop: 8 }}>{a.difficulty_note}</p></div></div>
        <div className="grid g2">
          <div className="card"><h2>Are you improving?</h2>{a.improvement ? <><p style={{ margin: "8px 0" }}><span className={`st ${a.improvement.verdict === "improving" ? "mastered" : a.improvement.verdict === "declining" ? "weak" : "learning"}`}>{a.improvement.verdict ?? "not enough data"}</span></p>
            <p className="muted">Acceptance {pct(a.improvement.first_half.acceptance)} → {pct(a.improvement.second_half.acceptance)} (first vs second half of the range).</p><p className="muted" style={{ fontSize: 12, marginTop: 6 }}>{a.improvement.note}</p></> : <p className="muted" style={{ marginTop: 8 }}>Needs at least 20 submissions in range.</p>}
            {a.contest_accuracy && <p className="muted" style={{ marginTop: 10 }}>In contest {pct(a.contest_accuracy.in_contest.acceptance)} (n={a.contest_accuracy.in_contest.n}) vs practice {pct(a.contest_accuracy.practice.acceptance)} (n={a.contest_accuracy.practice.n}); {a.contest_accuracy.unknown_excluded} unknown excluded.</p>}</div>
          <div className="card"><h2>Pattern coverage</h2><div className="row" style={{ gap: 6, margin: "10px 0" }}>{Object.entries(a.patterns.coverage.by_status).map(([k, v]) => <span key={k} className={`st ${k}`}>{k} {v}</span>)}</div>
            {a.patterns.weakest.map((w) => <p key={w.id} style={{ fontSize: 13, marginTop: 6 }}><Link href={`/patterns/${w.id}`}><b>{w.name}</b></Link> <span className={`st ${w.status}`}>{w.status}</span> <span className="mono muted">{Math.round(w.score * 100)}%</span></p>)}<Link href="/patterns" className="btn" style={{ marginTop: 10 }}>Open 3D pattern map →</Link></div></div>
        <div className="grid g2">{([["Strongest topics", a.topics.strongest, "var(--lime)"], ["Weakest topics", a.topics.weakest, "var(--rose)"], ["Improving (last 30d vs before)", a.topics.improving, "var(--cyan)"], ["Stagnating", a.topics.stagnating, "var(--amber)"]] as [string, Topic[], string][]).map(([t, xs, c]) =>
          <div key={t} className="card"><h2 style={{ marginBottom: 10 }}>{t}</h2>{xs.length ? <Bars data={xs.map((x) => [x.topic, Math.round(x.acceptance * 100)] as [string, number])} color={c} fmt={(v) => `${v}%`} /> : <p className="muted">None detected.</p>}</div>)}</div>
        <p className="muted" style={{ fontSize: 12 }}>{a.topics.note}</p>
        <div className="grid g3">
          <div className="card"><h2>Abandoned problems</h2><h1 className="mono">{a.abandoned.count}</h1><p className="muted" style={{ fontSize: 12 }} title={def("abandoned")}>3+ attempts, never solved, idle 14+ days ⓘ</p>{a.abandoned.examples.map((e) => <p key={e.problem_id} style={{ fontSize: 13 }}><Link href={`/problems/${e.problem_id}`}>{e.name}</Link> ×{e.attempts}</p>)}</div>
          <div className="card"><h2>Repeated recent failures</h2><h1 className="mono">{a.repeated_failures.count}</h1>{a.repeated_failures.examples.map((e) => <p key={e.problem_id} style={{ fontSize: 13 }}><Link href={`/problems/${e.problem_id}`}>{e.name}</Link> ×{e.attempts}</p>)}</div>
          <div className="card"><h2>Inactivity gaps</h2>{a.inactivity_gaps.length ? a.inactivity_gaps.map((g) => <p key={g.after} className="mono" style={{ fontSize: 13, marginTop: 6 }}>{g.days} days after {g.after}</p>) : <p className="muted" style={{ marginTop: 8 }}>No gaps over a week.</p>}</div></div>
        <details className="card"><summary><h2 style={{ display: "inline" }}>How each metric is defined ▸</h2></summary>{Object.entries(a.definitions).map(([k, d]) => <p key={k} style={{ fontSize: 13, marginTop: 8 }}><b className="mono">{k}</b> — {d.definition} <span className="muted">(source: {d.source})</span></p>)}</details>
        <div className="card"><h2>Data freshness</h2>{a.freshness.profiles.map((p) => <p key={p.platform + p.handle} style={{ fontSize: 13, marginTop: 6 }}>{p.platform}:{p.handle} · {p.data_level} · {p.last_synced_at ? `synced ${new Date(p.last_synced_at).toLocaleString()}` : "never synced"}</p>)}<p className="muted" style={{ fontSize: 12, marginTop: 6 }}>{a.freshness.note}</p></div></>)}
    </div>
  );
}

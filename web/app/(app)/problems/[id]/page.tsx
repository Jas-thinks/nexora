"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { ratingColor } from "@/lib/rating";

type D = { id: number; platform: string; external_id: string; name: string; url: string; status: string; difficulty: { rating: number | null; source_label: string | null; note: string };
  tags: string[]; patterns: string[]; contest: { id: string; name: string; start_time: string; url: string } | null; contest_ref: string | null; problem_index: string | null; limits: { time_ms: number | null; memory_kb: number | null };
  published_at: string | null; statistics: { solved_count: number | null; submission_count: number | null; history: { observed_at: string; solved_count: number | null; submission_count: number | null; source: string }[] };
  provenance: { source: string | null; observed_at: string | null; raw_record_preserved: boolean; statement_access: string; note: string }; sheets: { title: string; section: string }[]; yours: { solved: boolean; attempts: number; provenance: string } | null };

export default function ProblemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params); const [d, setD] = useState<D | null>(null), [err, setErr] = useState("");
  useEffect(() => { api<D>(`/problems/${id}`).then(setD).catch((e) => setErr(e.status === 404 ? "Problem not found." : e.message)); }, [id]);
  if (err) return <div><p className="err" role="alert">{err}</p><Link className="btn" href="/explorer">← Explorer</Link></div>;
  if (!d) return <div className="skeleton" style={{ height: 200 }} />;
  const Row = ({ k, v }: { k: string; v: React.ReactNode }) => <tr><td className="muted" style={{ width: 170 }}>{k}</td><td>{v ?? <span className="muted">unavailable</span>}</td></tr>;
  return (
    <div className="grid" style={{ gap: 18 }}>
      <Link href="/explorer" className="muted">← Problem Explorer</Link>
      <div className="card"><div className="row" style={{ justifyContent: "space-between" }}><div>
        <div className="row" style={{ gap: 6 }}><span className="chip">{d.platform}</span><span className="chip mono">{d.external_id}</span>{d.status !== "active" && <span className="st weak">{d.status.replace("_", " ")}</span>}{d.yours?.solved && <span className="st mastered">solved ({d.yours.provenance})</span>}</div>
        <h1 style={{ margin: "10px 0" }}>{d.name}</h1>
        <div className="row" style={{ gap: 6 }}>{d.difficulty.rating != null && <span className="pill mono" style={{ color: ratingColor(d.difficulty.rating), background: "rgba(255,255,255,.06)" }}>{d.difficulty.rating}</span>}{d.difficulty.source_label && <span className="chip">{d.difficulty.source_label}</span>}{d.tags.map((t) => <span key={t} className="chip">{t}</span>)}</div></div>
        <a className="btn primary" href={d.url} target="_blank" rel="noreferrer noopener">Open on {d.platform} →</a></div>
        {d.status === "missing_upstream" && <p className="err" style={{ marginTop: 10 }}>This problem was not listed by the source in the latest full enumeration; the link may be invalid.</p>}</div>
      <div className="grid g2">
        <div className="card"><h2>Metadata</h2><table className="t"><tbody>
          <Row k="Contest" v={d.contest ? <a href={d.contest.url} target="_blank" rel="noreferrer noopener">{d.contest.name} ↗</a> : d.contest_ref} /><Row k="Index" v={d.problem_index} />
          <Row k="Time limit" v={d.limits.time_ms != null ? `${d.limits.time_ms} ms` : null} /><Row k="Memory limit" v={d.limits.memory_kb != null ? `${Math.round(d.limits.memory_kb / 1024)} MB` : null} />
          <Row k="Published" v={d.published_at ? new Date(d.published_at).toLocaleDateString() : null} /><Row k="Patterns" v={d.patterns.length ? d.patterns.map((p) => <Link key={p} href={`/patterns/${p}`} className="chip" style={{ marginRight: 4 }}>{p}</Link>) : null} />
          <Row k="On sheets" v={d.sheets.length ? d.sheets.map((s) => `${s.title}${s.section ? ` › ${s.section}` : ""}`).join(" · ") : null} /></tbody></table>
          <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>{d.difficulty.note}</p></div>
        <div className="card"><h2>Statistics (as observed)</h2><table className="t"><tbody><Row k="Solved by" v={d.statistics.solved_count?.toLocaleString()} /><Row k="Submissions" v={d.statistics.submission_count?.toLocaleString()} /></tbody></table>
          {d.statistics.history.length > 0 && <><p className="muted" style={{ fontSize: 12, marginTop: 10 }}>Snapshot history</p>{d.statistics.history.slice(0, 5).map((h, i) => <p key={i} className="mono" style={{ fontSize: 12 }}>{new Date(h.observed_at).toLocaleDateString()} · solved {h.solved_count?.toLocaleString() ?? "–"} · {h.source}</p>)}</>}</div></div>
      <div className="card"><h2>Provenance</h2><p style={{ fontSize: 13, marginTop: 8 }}>Source: <span className="mono">{d.provenance.source ?? "—"}</span> · observed {d.provenance.observed_at ? new Date(d.provenance.observed_at).toLocaleString() : "—"} · raw source record preserved: {d.provenance.raw_record_preserved ? "yes" : "no"} · statement access: {d.provenance.statement_access}</p>
        <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>{d.provenance.note}</p></div>
    </div>
  );
}

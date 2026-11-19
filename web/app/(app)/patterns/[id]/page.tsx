"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import ProblemRow, { P } from "@/components/ProblemRow";

type D = { id: string; name: string; kind: string; parent: string; aliases: string[]; prerequisites: string[]; related: string[]; contrasts_with: string[]; extends: string[]; leads_to: string[];
  complexity: string; clues: string[]; problem_count: number; learning_page: { status: string; note: string };
  mastery: { status: string; score: number; solved: number; attempted: number; reasons: string[]; missing_prereqs: string[]; due_for_revision: boolean } | null;
  problems: Record<string, P[]> };
const L = ({ ids, label }: { ids: string[]; label: string }) => ids.length ? <div style={{ marginTop: 12 }}><p className="muted" style={{ fontSize: 12 }}>{label}</p><div className="row" style={{ gap: 6, marginTop: 4 }}>{ids.map((i) => <Link key={i} href={`/patterns/${i}`} className="chip">{i}</Link>)}</div></div> : null;

export default function PatternPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params); const [d, setD] = useState<D | null>(null), [err, setErr] = useState("");
  useEffect(() => { api<D>(`/patterns/${id}`).then(setD).catch((e) => setErr(e.status === 404 ? "Unknown pattern." : e.message)); }, [id]);
  if (err) return <div><p className="err" role="alert">{err}</p><Link className="btn" href="/patterns">← Patterns</Link></div>;
  if (!d) return <div className="skeleton" style={{ height: 160 }} />;
  const m = d.mastery;
  return (
    <div className="grid" style={{ gap: 20 }}>
      <Link href="/patterns" className="muted">← Pattern Universe</Link>
      <div><span className="chip">{d.kind.replace("_", " ")}</span><h1 style={{ marginTop: 8 }}>{d.name}</h1>{d.complexity && <p className="mono muted">{d.complexity}</p>}{d.aliases.length > 0 && <p className="muted">Also known as: {d.aliases.join(", ")}</p>}</div>
      <div className="grid g2">
        <div className="card"><h2>Your mastery {m && <span className={`st ${m.status}`}>{m.status}</span>}</h2>
          {m ? <><div className="bar" style={{ margin: "12px 0" }}><i style={{ width: `${m.score * 100}%` }} /></div>{m.reasons.map((r, i) => <p key={i} className="muted" style={{ fontSize: 13, marginTop: 6 }}>• {r}</p>)}
            {m.missing_prereqs.length > 0 && <p className="err" style={{ marginTop: 8 }}>Prerequisites to firm up: {m.missing_prereqs.join(", ")}</p>}</> : <p className="muted">Category node.</p>}</div>
        <div className="card"><h2>How to recognise it</h2>{d.clues.length ? d.clues.map((c) => <p key={c} style={{ marginTop: 8 }}>• {c}</p>) : <p className="muted" style={{ marginTop: 8 }}>No recognition clues written yet for this pattern.</p>}
          <L ids={d.prerequisites} label="Prerequisites" /><L ids={d.leads_to} label="Unlocks" /><L ids={d.related} label="Related" /><L ids={d.contrasts_with} label="Looks similar but is different from" /><L ids={d.extends} label="Extends" /></div>
      </div>
      <div className="card"><p className="muted" style={{ fontSize: 13 }}>Learning page: <b>{d.learning_page.status}</b>. {d.learning_page.note}</p></div>
      {Object.entries(d.problems).map(([lvl, ps]) => <div key={lvl}><h2 style={{ textTransform: "capitalize", margin: "8px 0 10px" }}>{lvl} problems <span className="muted" style={{ fontSize: 13 }}>({d.problem_count} mapped in catalog)</span></h2>
        {ps.length === 0 ? <p className="muted">No catalog problems at this level yet.</p> : <div className="grid">{ps.map((p) => <ProblemRow key={p.id} p={p} />)}</div>}</div>)}
    </div>
  );
}

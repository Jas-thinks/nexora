"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import ProblemRow, { P } from "@/components/ProblemRow";

type D = { title: string; source: string; items: P[] };

export default function SheetDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [d, setD] = useState<D | null>(null), [err, setErr] = useState("");
  const load = () => api<D>(`/sheets/${id}`).then(setD).catch((e) => setErr(e.status === 404 ? "Sheet not found." : e.message));
  useEffect(() => { load(); }, [id]); // eslint-disable-line
  if (err) return <div><p className="err" role="alert">{err}</p><Link href="/sheets" className="btn">← Back</Link></div>;
  if (!d) return <div className="skeleton" style={{ height: 120 }} />;
  const done = d.items.filter((i) => i.solved).length;
  const sections = [...new Set(d.items.map((i) => i.section || "Problems"))];
  return (
    <div className="grid" style={{ gap: 20 }}>
      <Link href="/sheets" className="muted">← Sheets</Link>
      <div><h1>{d.title}</h1><p className="muted">{d.source}</p>
        <div className="bar" style={{ marginTop: 14 }}><i style={{ width: `${d.items.length ? (done / d.items.length) * 100 : 0}%` }} /></div>
        <p className="mono muted" style={{ fontSize: 12, marginTop: 6 }}>{done} / {d.items.length}</p></div>
      {sections.map((s) => <div key={s}><h2 style={{ margin: "8px 0 12px" }}>{s}</h2><div className="grid">{d.items.filter((i) => (i.section || "Problems") === s).map((p) => <ProblemRow key={p.id} p={p} onDone={load} />)}</div></div>)}
    </div>
  );
}

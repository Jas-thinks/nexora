"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type S = { id: number; title: string; source: string; description: string; total: number; solved: number; mine: boolean };

export default function Sheets() {
  const [s, setS] = useState<S[] | null>(null), [err, setErr] = useState("");
  const [open, setOpen] = useState(false), [f, setF] = useState({ slug: "", title: "", source: "", text: "" }), [msg, setMsg] = useState(""), [busy, setBusy] = useState(false);
  const load = () => api<S[]>("/sheets").then(setS).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  async function imp(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setMsg("");
    const items = f.text.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean).map((p) => { const [problem, section = ""] = p.split("|").map((x) => x.trim()); return { problem, section }; });
    try { const r = await api<{ imported: number; missing: string[] }>("/sheets/import", { method: "POST", body: JSON.stringify({ slug: f.slug, title: f.title, source: f.source, items }) });
      setMsg(`Imported ${r.imported} problems.${r.missing.length ? ` Not found in catalog: ${r.missing.join(", ")}` : ""}`); load(); }
    catch (x) { setMsg((x as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="grid" style={{ gap: 24 }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><h1>Problem <span className="grad-text">sheets</span></h1><p className="muted">Curated ladders with progress that feeds your mastery model.</p></div>
        <button className="btn primary" onClick={() => setOpen(!open)}>{open ? "Close" : "+ Import sheet"}</button></div>
      {open && <form onSubmit={imp} className="card grid" style={{ gap: 12 }}>
        <p className="muted" style={{ fontSize: 13 }}>Paste Codeforces problem IDs or URLs, one per line (e.g. <span className="mono">1352C</span> or <span className="mono">1352C | Math</span> to set a section). Use this to bring in your CP-31, Striver or any other ladder. Entries not found in the synced catalog are reported, never invented.</p>
        <div className="grid g2"><div><label htmlFor="sl">Slug (a-z, 0-9, -)</label><input id="sl" required pattern="[a-z0-9\-]{3,80}" value={f.slug} onChange={(e) => setF({ ...f, slug: e.target.value })} /></div>
          <div><label htmlFor="ti">Title</label><input id="ti" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div></div>
        <div><label htmlFor="so">Source / credit</label><input id="so" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></div>
        <div><label htmlFor="tx">Problems</label><textarea id="tx" required rows={6} className="mono" style={{ width: "100%", background: "rgba(255,255,255,.05)", color: "inherit", border: "1px solid var(--card-b)", borderRadius: 12, padding: 12 }} value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} /></div>
        <div className="row"><button className="btn primary" disabled={busy}>{busy ? "Importing…" : "Import"}</button>{msg && <span role="status" className="muted">{msg}</span>}</div>
      </form>}
      {err && <p className="err" role="alert">{err}</p>}
      {!s ? <div className="skeleton" style={{ height: 100 }} /> : s.length === 0 ? <div className="card"><p>No sheets yet. Import one above, or ask an admin to seed the starter ladder.</p></div> :
        <div className="grid g2">{s.map((x) => <Link key={x.id} href={`/sheets/${x.id}`} className="card hover">
          <div className="row" style={{ justifyContent: "space-between" }}><h2>{x.title}</h2>{x.mine && <span className="chip">yours</span>}</div>
          <p className="muted" style={{ fontSize: 13, margin: "6px 0 14px" }}>{x.source || x.description}</p>
          <div className="bar"><i style={{ width: `${x.total ? (x.solved / x.total) * 100 : 0}%` }} /></div>
          <p className="mono muted" style={{ fontSize: 12, marginTop: 8 }}>{x.solved} / {x.total} solved</p></Link>)}</div>}
    </div>
  );
}

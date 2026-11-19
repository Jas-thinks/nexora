"use client";
import { useCallback, useEffect, useState } from "react";
import { api, upload } from "@/lib/api";

type Plat = { slug: string; name: string; url: string; tier: number; status: string; capabilities: string[]; api_docs: string | null; auth: string; rate_limit: string; limitations: string; evidence: string | null; verified_on: string | null; has_adapter: boolean };
type Prof = { id: number; platform: string; name: string; handle: string; data_level: string; status: string; last_synced_at: string | null; last_error: string | null; capabilities: string[]; integration_status: string; history_limitations: string };
type Job = { id: number; platform: string; kind: string; status: string; attempts: number; error: string | null; stats: Record<string, unknown> };
const LEVEL: Record<string, string> = { public_api: "VERIFIED", user_imported: "USER-IMPORTED", link_only: "LINK ONLY" };
const STATUS_CLASS: Record<string, string> = { integrated: "mastered", contests_only: "practised", manual_import: "learning", link_only: "unexplored" };

export default function Connections() {
  const [plats, setPlats] = useState<Plat[]>([]), [profs, setProfs] = useState<Prof[]>([]), [jobs, setJobs] = useState<Job[]>([]), [err, setErr] = useState(""), [msg, setMsg] = useState("");
  const [sel, setSel] = useState("codeforces"), [handle, setHandle] = useState(""), [busy, setBusy] = useState(false), [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => Promise.all([api<{ platforms: Plat[] }>("/platforms"), api<Prof[]>("/profiles"), api<Job[]>("/sync-jobs")])
    .then(([a, b, c]) => { setPlats(a.platforms); setProfs(b); setJobs(c); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!jobs.some((j) => j.status === "queued" || j.status === "running")) return; const t = setTimeout(load, 3000); return () => clearTimeout(t); }, [jobs, load]);
  async function link(e: React.FormEvent) { e.preventDefault(); setBusy(true); setErr(""); setMsg("");
    try { await api("/profiles", { method: "POST", body: JSON.stringify({ platform: sel, handle: handle.trim() }) }); setHandle(""); setMsg("Linked."); load(); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } }
  async function sync(p: Prof) { setErr(""); try { await api(`/profiles/${p.id}/sync`, { method: "POST" }); setMsg(`Sync queued for ${p.name}.`); load(); } catch (x) { setErr((x as Error).message); } }
  async function unlink(p: Prof) { if (!confirm(`Unlink ${p.name}:${p.handle}? Imported submissions stay; no more syncing.`)) return; await api(`/profiles/${p.id}`, { method: "DELETE" }); load(); }
  async function imp(p: Prof, file: File | undefined) { if (!file) return; const fd = new FormData(); fd.append("file", file); setErr("");
    try { const r = await upload<{ added: number; duplicates: number; rejected_count: number; label: string }>(`/profiles/${p.id}/import`, fd); setMsg(`Imported ${r.added} new, ${r.duplicates} duplicates, ${r.rejected_count} rejected. Labelled ${r.label}.`); load(); } catch (x) { setErr((x as Error).message); } }
  const linkable = plats.filter((p) => p.status !== "unavailable");
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Platform <span className="grad-text">connections</span></h1><p className="muted">Nexora only claims what a platform genuinely exposes. Every connection is labelled VERIFIED, USER-IMPORTED or LINK ONLY, and unavailable data is shown as unavailable, never as zero.</p></div>
      {err && <p className="err" role="alert">{err}</p>}{msg && <p role="status" style={{ color: "var(--lime)" }}>{msg}</p>}
      <form onSubmit={link} className="card row" style={{ alignItems: "flex-end" }}>
        <div style={{ flex: "1 1 200px" }}><label htmlFor="p">Platform</label><select id="p" value={sel} onChange={(e) => setSel(e.target.value)}>{linkable.map((p) => <option key={p.slug} value={p.slug}>{p.name} — {p.status.replace("_", " ")}</option>)}</select></div>
        <div style={{ flex: "1 1 200px" }}><label htmlFor="h">Handle / username</label><input id="h" required pattern="[\w.\-@]+" maxLength={120} value={handle} onChange={(e) => setHandle(e.target.value)} /></div>
        <button className="btn primary" disabled={busy}>{busy ? "Checking…" : "Link"}</button>
        <p className="muted" style={{ fontSize: 12, flexBasis: "100%" }}>{plats.find((p) => p.slug === sel)?.limitations}</p>
      </form>
      <div><h2 style={{ marginBottom: 10 }}>Your profiles</h2>
        {profs.length === 0 ? <div className="card"><p className="muted">No profiles linked yet.</p></div> : <div className="grid">{profs.map((p) => <div key={p.id} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}><div><b>{p.name}</b> <span className="mono muted">{p.handle}</span> <span className={`st ${p.data_level === "public_api" ? "mastered" : p.data_level === "user_imported" ? "learning" : "unexplored"}`}>{LEVEL[p.data_level]}</span>
            <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>{p.last_synced_at ? `Last synced ${new Date(p.last_synced_at).toLocaleString()}` : "Never synced"}{p.last_error && <span className="err"> · {p.last_error}</span>}</p><p className="muted" style={{ fontSize: 12, marginTop: 2 }}>History limits: {p.history_limitations}</p></div>
            <div className="row">{p.capabilities.includes("submissions") && <button className="btn" onClick={() => sync(p)}>Sync now</button>}
              <label className="btn" style={{ margin: 0, cursor: "pointer" }}>Import CSV/JSON<input type="file" accept=".csv,.json" hidden onChange={(e) => imp(p, e.target.files?.[0])} /></label><button className="btn" onClick={() => unlink(p)}>Unlink</button></div></div></div>)}</div>}
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Import format: columns <span className="mono">problem, verdict (AC/WA/TLE/MLE/RE/CE/OTHER), submitted_at (ISO-8601), language</span>. Problem may be a URL.</p></div>
      {jobs.length > 0 && <div><h2 style={{ marginBottom: 10 }}>Sync activity</h2><div className="card" style={{ padding: 0, overflowX: "auto" }}><table className="t"><thead><tr><th>#</th><th>Platform</th><th>Status</th><th>Attempts</th><th>Result</th></tr></thead><tbody>{jobs.slice(0, 8).map((j) => <tr key={j.id}><td className="mono">{j.id}</td><td>{j.platform}</td><td><span className={`st ${j.status === "succeeded" ? "mastered" : j.status === "dead" || j.status === "failed" ? "weak" : "learning"}`}>{j.status}</span></td><td>{j.attempts}</td><td className="muted" style={{ fontSize: 12 }}>{j.error ?? JSON.stringify(j.stats).slice(0, 110)}</td></tr>)}</tbody></table></div></div>}
      <div><h2 style={{ marginBottom: 6 }}>Capability matrix</h2><p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>{plats.length} platforms tracked. Platforms marked “not investigated” have no verified claims; only a profile link and manual import are offered.</p>
        <div className="card" style={{ padding: 0, overflowX: "auto" }}><table className="t"><thead><tr><th>Platform</th><th>Status</th><th>Capabilities</th><th>Evidence</th></tr></thead><tbody>{plats.map((p) => <>
          <tr key={p.slug} style={{ cursor: "pointer" }} onClick={() => setOpen(open === p.slug ? null : p.slug)}><td><b>{p.name}</b></td><td><span className={`st ${STATUS_CLASS[p.status] ?? "unexplored"}`}>{p.status.replace("_", " ")}</span></td>
            <td>{p.capabilities.map((c) => <span key={c} className="chip" style={{ marginRight: 4 }}>{c.replace("_", " ")}</span>)}</td><td className="muted" style={{ fontSize: 12 }}>{p.verified_on ? `verified ${p.verified_on}` : "not investigated"}</td></tr>
          {open === p.slug && <tr key={p.slug + "x"}><td colSpan={4} style={{ background: "rgba(255,255,255,.03)" }}><p style={{ fontSize: 13 }}><b>Auth:</b> {p.auth} · <b>Rate limit:</b> {p.rate_limit}</p><p style={{ fontSize: 13, marginTop: 4 }}><b>Limitations:</b> {p.limitations || "—"}</p>{p.evidence && <p style={{ fontSize: 13, marginTop: 4 }}><b>Evidence:</b> {p.evidence}</p>}
            <p style={{ fontSize: 13, marginTop: 4 }}><a href={p.url} target="_blank" rel="noreferrer noopener">Website ↗</a>{p.api_docs && <> · <a href={p.api_docs} target="_blank" rel="noreferrer noopener">API docs ↗</a></>}</p></td></tr>}</>)}</tbody></table></div></div>
    </div>
  );
}

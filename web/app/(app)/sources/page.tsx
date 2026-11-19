"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Comp = Record<string, number>;
type Src = { slug: string; name: string; url: string; group: string; listing: string; backfill: string; detail: string; topics: string; difficulty: string; contest: string; submissions: string; profile: string; incremental: string;
  official_api: string; auth: string; data_rights: string; evidence: string; adapter: string | null; verified_on: string; can_backfill: boolean; unresolved_failures: number;
  records: { records: number; active: number; missing_upstream: number; inaccessible: number; completeness: Comp } | null;
  sync: { done: boolean; discovered: number | null; retrieved: number; completed_at: string | null; updated_at: string } | null };
type Data = { verified_on: string; sources: Src[]; note: string; references: { slug: string; name: string; url: string; note: string }[];
  totals: { platform_records: number; canonical_urls: number; contests: number; sheets: number; sheet_memberships: number; statistics_snapshots: number; unresolved_failures: number; missing_upstream: number; inaccessible: number; last_sync: string | null } };
type An = { problems_per_platform: Record<string, number>; codeforces_rating_distribution: Record<string, number>; top_tags: [string, number][]; sheet_overlap: { problems_on_2plus_sheets: number; problems_on_any_sheet: number }; note: string };
const CAPS: [keyof Src, string][] = [["listing", "List"], ["backfill", "Backfill"], ["detail", "Detail"], ["topics", "Topics"], ["difficulty", "Difficulty"], ["contest", "Contest"], ["submissions", "Subs"], ["profile", "Profile"], ["incremental", "Incr."]];
const CLS: Record<string, string> = { Supported: "mastered", Partial: "learning", Unavailable: "unexplored" };
const RIGHTS: Record<string, string> = { Verified: "mastered", Restricted: "weak", Unclear: "learning" };

function Bars({ data, color = "var(--violet)" }: { data: [string, number][]; color?: string }) {
  const max = Math.max(1, ...data.map((d) => d[1]));
  return <div className="grid" style={{ gap: 6 }}>{data.map(([k, v]) => <div key={k} className="row" style={{ gap: 8, flexWrap: "nowrap" }}><span className="mono muted" style={{ width: 92, fontSize: 11 }}>{k}</span>
    <div className="bar" style={{ flex: 1, height: 10 }}><i style={{ width: `${(v / max) * 100}%`, background: color }} /></div><span className="mono" style={{ width: 62, textAlign: "right", fontSize: 11 }}>{v.toLocaleString()}</span></div>)}</div>;
}

export default function Sources() {
  const [d, setD] = useState<Data | null>(null), [err, setErr] = useState(""), [msg, setMsg] = useState(""), [open, setOpen] = useState<string | null>(null), [f, setF] = useState("active");
  const load = useCallback(() => { api<Data>("/sources").then(setD).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);
  async function backfill(s: Src) { setMsg(""); setErr(""); try { await api(`/admin/backfill/${s.slug}`, { method: "POST" }); setMsg(`Backfill queued for ${s.name}. Progress appears below as pages are checkpointed.`); setTimeout(load, 4000); } catch (e) { setErr((e as Error).message); } }
  if (!d) return err ? <p className="err" role="alert">{err}</p> : <div className="skeleton" style={{ height: 240 }} />;
  const t = d.totals;
  const rows = d.sources.filter((s) => f === "all" || (f === "active" ? s.records || s.can_backfill : f === "restricted" ? s.data_rights === "Restricted" : !s.records));
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Global problem <span className="grad-text">data sources</span></h1>
        <p className="muted">{d.sources.length} sources investigated on {d.verified_on}. Coverage is reported against what each source itself says it lists; nothing is called complete without that evidence.</p></div>
      <div className="grid g3">{[["Platform records", t.platform_records], ["Contests", t.contests], ["Sheet memberships", t.sheet_memberships], ["Statistic snapshots", t.statistics_snapshots], ["Missing upstream", t.missing_upstream], ["Unresolved failures", t.unresolved_failures]].map(([k, v]) =>
        <div key={k as string} className="card"><p className="muted" style={{ fontSize: 12 }}>{k}</p><h1 className="mono" style={{ fontSize: 30 }}>{(v as number).toLocaleString()}</h1></div>)}</div>
      {err && <p className="err" role="alert">{err}</p>}{msg && <p role="status" style={{ color: "var(--lime)" }}>{msg}</p>}
      <div className="seg">{[["active", "Ingested / ingestible"], ["restricted", "Restricted"], ["none", "No data"], ["all", "All"]].map(([k, l]) => <button key={k} className={`btn ${f === k ? "primary" : ""}`} onClick={() => setF(k)}>{l}</button>)}</div>
      <div className="grid">{rows.map((s) => { const r = s.records, cp = s.sync; const pct = cp?.discovered ? Math.min(100, (cp.retrieved / cp.discovered) * 100) : cp?.done ? 100 : 0;
        return <div key={s.slug} className="card" style={{ padding: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", cursor: "pointer" }} onClick={() => setOpen(open === s.slug ? null : s.slug)}>
            <div><b style={{ fontSize: 16 }}>{s.name}</b> <span className={`st ${RIGHTS[s.data_rights]}`}>rights: {s.data_rights}</span> <span className="chip">API: {s.official_api}</span> <span className="chip">auth: {s.auth}</span></div>
            <div className="row">{r ? <span className="mono"><b>{r.records.toLocaleString()}</b> records</span> : <span className="muted">no records</span>}
              {s.unresolved_failures > 0 && <span className="st weak">{s.unresolved_failures} failures</span>}
              {s.can_backfill && <button className="btn" onClick={(e) => { e.stopPropagation(); backfill(s); }}>Backfill / refresh</button>}</div></div>
          <div className="row" style={{ gap: 4, margin: "10px 0" }}>{CAPS.map(([k, l]) => <span key={k} className={`st ${CLS[s[k] as string]}`} title={`${l}: ${s[k]}`}>{l} {s[k] === "Supported" ? "✓" : s[k] === "Partial" ? "◐" : "–"}</span>)}</div>
          {cp && <div style={{ marginBottom: 8 }}><div className="row" style={{ justifyContent: "space-between" }}><span className="muted" style={{ fontSize: 12 }}>Enumeration {cp.done ? "complete" : "in progress"}: {cp.retrieved.toLocaleString()}{cp.discovered ? ` of ${cp.discovered.toLocaleString()} the source lists` : ""}</span>
            <span className="muted mono" style={{ fontSize: 11 }}>{cp.completed_at ? `last complete ${new Date(cp.completed_at).toLocaleString()}` : "not yet complete"}</span></div><div className="bar" style={{ marginTop: 4 }}><i style={{ width: `${pct}%` }} /></div></div>}
          {r && <div className="row" style={{ gap: 14 }}>{Object.entries(r.completeness).map(([k, v]) => <span key={k} className="mono muted" style={{ fontSize: 11 }}>{k} <b style={{ color: v > 80 ? "var(--lime)" : v > 20 ? "var(--amber)" : "var(--rose)" }}>{v}%</b></span>)}</div>}
          {open === s.slug && <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--card-b)" }}><p style={{ fontSize: 13 }}><b>Evidence ({s.verified_on}):</b> {s.evidence}</p><p style={{ fontSize: 13, marginTop: 6 }}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.url} ↗</a>{s.adapter && <span className="muted"> · adapter: {s.adapter}</span>}</p></div>}
        </div>; })}</div>
      <div className="card"><h2>Reference sources</h2>{d.references.map((r) => <p key={r.slug} style={{ fontSize: 13, marginTop: 8 }}><a href={r.url} target="_blank" rel="noreferrer noopener"><b>{r.name}</b></a> — <span className="muted">{r.note}</span></p>)}</div>
    </div>
  );
}

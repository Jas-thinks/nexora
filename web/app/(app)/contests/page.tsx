"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type C = { id: number; platform: string; name: string; start_time: string; duration_seconds: number | null; url: string; rated: boolean | null; synced_at: string };
type R = { items: C[]; last_synced: Record<string, string>; note: string };
const fmtDur = (s: number | null) => (s == null ? "—" : s >= 86400 ? `${Math.round(s / 86400)}d` : `${Math.floor(s / 3600)}h${s % 3600 ? ` ${Math.round((s % 3600) / 60)}m` : ""}`);
const countdown = (ms: number) => { if (ms <= 0) return "started"; const s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m ${s % 60}s`; };
const ics = (c: C) => { const f = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, ""); const s = new Date(c.start_time), e = new Date(s.getTime() + (c.duration_seconds ?? 7200) * 1000);
  const body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Nexora//EN", "BEGIN:VEVENT", `UID:nexora-${c.platform}-${c.id}@nexora`, `DTSTAMP:${f(new Date())}`, `DTSTART:${f(s)}`, `DTEND:${f(e)}`, `SUMMARY:${c.name.replace(/[\n,;]/g, " ")} (${c.platform})`, `URL:${c.url}`, "BEGIN:VALARM", "TRIGGER:-PT30M", "ACTION:DISPLAY", "DESCRIPTION:Contest starts in 30 minutes", "END:VALARM", "END:VEVENT", "END:VCALENDAR"].join("\r\n");
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([body], { type: "text/calendar" })); a.download = `${c.platform}-${c.id}.ics`; a.click(); URL.revokeObjectURL(a.href); };

export default function Contests() {
  const [r, setR] = useState<R | null>(null), [err, setErr] = useState(""), [pf, setPf] = useState(""), [now, setNow] = useState(Date.now());
  useEffect(() => { api<R>(`/contests?limit=300${pf ? `&platform=${pf}` : ""}`).then(setR).catch((e) => setErr(e.message)); }, [pf]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const platforms = useMemo(() => (r ? Object.keys(r.last_synced) : []), [r]);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>Contest <span className="grad-text">calendar</span></h1><p className="muted">Straight from each platform&apos;s own source. Times shown in your timezone ({tz}). Nothing is invented: if a platform isn&apos;t synced, it isn&apos;t listed.</p></div>
      {err && <p className="err" role="alert">{err}</p>}
      <div className="row"><div className="seg"><button className={`btn ${pf === "" ? "primary" : ""}`} onClick={() => setPf("")}>All</button>{platforms.map((p) => <button key={p} className={`btn ${pf === p ? "primary" : ""}`} onClick={() => setPf(p)}>{p}</button>)}</div></div>
      {r && <p className="muted" style={{ fontSize: 12 }}>Last synchronised: {Object.entries(r.last_synced).map(([p, t]) => `${p} ${new Date(t).toLocaleString()}`).join(" · ") || "never"}</p>}
      {!r ? <div className="skeleton" style={{ height: 160 }} /> : r.items.length === 0 ? <div className="card"><p>{r.note}</p><p className="muted" style={{ marginTop: 6 }}>An admin can run contest syncs via POST /admin/sync/contests/&#123;platform&#125;.</p></div> :
        <div className="grid">{r.items.map((c) => { const ms = new Date(c.start_time).getTime() - now; return <div key={c.id} className="card hover" style={{ padding: 16 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div style={{ minWidth: 0 }}><span className="chip">{c.platform}</span>{c.rated && <span className="chip" style={{ marginLeft: 6 }}>rated</span>}<h2 style={{ fontSize: 17, margin: "8px 0 4px" }}><a href={c.url} target="_blank" rel="noreferrer noopener">{c.name} ↗</a></h2>
              <p className="muted" style={{ fontSize: 13 }}>{new Date(c.start_time).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} · {fmtDur(c.duration_seconds)}</p></div>
            <div className="row"><span className="mono pill" style={{ background: "rgba(34,211,238,.12)", color: "var(--cyan)" }}>{countdown(ms)}</span><button className="btn" onClick={() => ics(c)}>+ Calendar</button></div></div></div>; })}</div>}
    </div>
  );
}

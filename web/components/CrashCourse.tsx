"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { celebrate } from "@/components/Confetti";

type Task = { id: string; kind: string; title: string; url?: string; href?: string; difficulty?: string; est_min: number; note: string; done: boolean; auto: boolean; day?: number };
type Day = { day: number; date: string; theme: string; minutes: number; complete: boolean; tasks: Task[] };
type Course = { id: number | null; message?: string; days: number; track: string; level: string; target: string; hours: number; day_number: number; status: string; progress: { done: number; total: number; ratio: number }; streak_days: number; overdue_count: number; overdue: Task[]; plan: Day[]; summary: { dsa_problems: number; design_tasks: number; mocks: number }; note: string };
type Opts = { tracks: Record<string, string>; levels: Record<string, string>; tiers: Record<string, string> };
const ICON: Record<string, string> = { learn: "📖", problem: "💻", design: "🧩", mock: "🎤", review: "↻" };
const DIFF: Record<string, string> = { Easy: "mastered", Medium: "learning", Hard: "weak" };

function Ring({ v, size = 96 }: { v: number; size?: number }) {
  const r = size / 2 - 8, c = 2 * Math.PI * r;
  return <svg width={size} height={size} role="img" aria-label={`${Math.round(v * 100)}% complete`}><circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="8" /><circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="url(#g)" strokeWidth="8" strokeLinecap="round" strokeDasharray={`${c * v} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dasharray .6s" }} />
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" /></linearGradient></defs><text x="50%" y="52%" textAnchor="middle" dominantBaseline="middle" fill="currentColor" className="mono" fontSize={size / 4.2} fontWeight="700">{Math.round(v * 100)}%</text></svg>;
}

function TaskRow({ t, onToggle }: { t: Task; onToggle: (id: string) => void }) {
  const open = t.url ? <a className="btn" href={t.url} target="_blank" rel="noreferrer noopener">Open ↗</a> : t.href ? <Link className="btn" href={t.href}>Start</Link> : null;
  return <div className="row" style={{ justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid var(--card-b)", opacity: t.done ? 0.6 : 1 }}>
    <label style={{ display: "flex", gap: 10, alignItems: "flex-start", cursor: t.auto ? "default" : "pointer", flex: 1 }}>
      <input type="checkbox" checked={t.done} disabled={t.auto} onChange={() => onToggle(t.id)} aria-label={`Mark done: ${t.title}`} style={{ marginTop: 4 }} />
      <span><span style={{ textDecoration: t.done ? "line-through" : "none" }}>{ICON[t.kind]} <b>{t.title}</b></span> {t.difficulty && <span className={`st ${DIFF[t.difficulty]}`}>{t.difficulty}</span>} <span className="chip">{t.est_min} min</span> {t.auto && <span className="chip" style={{ color: "var(--lime)" }}>auto: solved</span>}
        <br /><span className="muted" style={{ fontSize: 12 }}>{t.note}</span></span></label>{open}</div>;
}

function Setup({ onCreated }: { onCreated: (c: Course) => void }) {
  const [o, setO] = useState<Opts | null>(null), [f, setF] = useState({ days: 30, track: "both", level: "entry", target: "service", hours: 2 }), [companies, setCompanies] = useState<{ slug: string; name: string }[]>([]), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  useEffect(() => { api<Opts>("/planner/crash-course/options").then(setO).catch((e) => setErr(e.message)); api<{ items: { slug: string; name: string }[] }>("/resources/companies?limit=200").then((d) => setCompanies(d.items)).catch(() => {}); }, []);
  async function go() { setBusy(true); setErr(""); try { onCreated(await api<Course>("/planner/crash-course", { method: "POST", body: JSON.stringify(f) })); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  if (!o) return err ? <p className="err">{err}</p> : <div className="skeleton" style={{ height: 160 }} />;
  const Opt = ({ k, v, label, sub }: { k: "days" | "track" | "level" | "hours"; v: string | number; label: string; sub?: string }) => <button type="button" onClick={() => setF({ ...f, [k]: v })} aria-pressed={f[k] === v} className="card" style={{ cursor: "pointer", textAlign: "left", padding: "12px 16px", borderColor: f[k] === v ? "var(--violet)" : undefined, boxShadow: f[k] === v ? "0 0 0 1px var(--violet), 0 0 24px -8px var(--violet)" : undefined }}><b>{label}</b>{sub && <div className="muted" style={{ fontSize: 12 }}>{sub}</div>}</button>;
  return <div className="grid" style={{ gap: 14 }}>
    <div className="card"><h2>Pick your sprint</h2><div className="grid g2" style={{ marginTop: 10 }}><Opt k="days" v={30} label="30 days" sub="Fast: the highest-value topics, a mock every week" /><Opt k="days" v={60} label="60 days" sub="Deeper: more problems per topic and more design questions" /></div></div>
    <div className="card"><h2>What are you preparing?</h2><div className="grid g3" style={{ marginTop: 10 }}>{Object.entries(o.tracks).map(([k, v]) => <Opt key={k} k="track" v={k} label={v} />)}</div></div>
    <div className="card"><h2>Your level</h2><div className="grid g3" style={{ marginTop: 10 }}>{Object.entries(o.levels).map(([k, v]) => <Opt key={k} k="level" v={k} label={v} />)}</div></div>
    <div className="card"><h2>Target companies</h2><div className="row" style={{ marginTop: 10 }}><div style={{ flex: "1 1 260px" }}><label htmlFor="tg2">Group or a specific company</label><select id="tg2" value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })}><optgroup label="Groups">{Object.entries(o.tiers).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</optgroup><optgroup label="Companies">{companies.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}</optgroup></select></div>
      <div><label>Hours per day</label><div className="row" style={{ gap: 6 }}>{[1, 2, 3, 4, 6].map((h) => <button type="button" key={h} className={`btn ${f.hours === h ? "primary" : ""}`} onClick={() => setF({ ...f, hours: h })}>{h}h</button>)}</div></div></div>
      <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Problems come from what these companies are <i>reported</i> to ask (community data, not official) and skip what you already solved.</p></div>
    {err && <p className="err" role="alert">{err}</p>}
    <button className="btn primary" disabled={busy} onClick={go} style={{ justifyContent: "center", padding: "14px 18px", fontSize: 16 }}>{busy ? "Building your plan…" : `🚀 Build my ${f.days}-day plan`}</button></div>;
}

export default function CrashCourse() {
  const [c, setC] = useState<Course | null>(null), [err, setErr] = useState(""), [open, setOpen] = useState<number | null>(null), [view, setView] = useState<"today" | "all">("today");
  const load = useCallback(() => api<Course>("/planner/crash-course").then((x) => { setC(x); setOpen(x.day_number); }).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);
  async function toggle(id: string) { try { const before = c?.progress.done ?? 0; const x = await api<Course>(`/planner/crash-course/tasks/${id}/toggle`, { method: "POST" }); setC(x); if (x.progress.done > before) { window.dispatchEvent(new Event("nexora:refresh")); if (x.plan.some((d) => d.complete && d.day === x.day_number)) celebrate(); } } catch (e) { setErr((e as Error).message); } }
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!c) return <div className="skeleton" style={{ height: 200 }} />;
  if (!c.id) return <Setup onCreated={(x) => { setC(x); setOpen(x.day_number); }} />;
  const today = c.plan.find((d) => d.day === Math.min(Math.max(c.day_number, 1), c.days))!;
  return <div className="grid" style={{ gap: 16 }}>
    <div className="card row" style={{ justifyContent: "space-between", gap: 20 }}>
      <div className="row" style={{ gap: 20 }}><Ring v={c.progress.ratio} /><div><h2>{c.days}-day crash course · {c.status === "not_started" ? "starts soon" : c.status === "finished" ? "finished" : `day ${c.day_number} of ${c.days}`}</h2>
        <div className="row" style={{ gap: 6, marginTop: 8 }}><span className="chip">{c.progress.done}/{c.progress.total} tasks</span><span className="chip">🔥 {c.streak_days}-day streak</span><span className="chip">{c.summary.dsa_problems} problems</span><span className="chip">{c.summary.design_tasks} designs</span><span className="chip">{c.summary.mocks} mocks</span>{c.overdue_count > 0 && <span className="st weak">{c.overdue_count} behind</span>}</div></div></div>
      <button className="btn" onClick={async () => { if (confirm("Stop this course and start a new one?")) { await api("/planner/crash-course", { method: "DELETE" }); load(); } }}>Change plan</button></div>
    <div className="seg"><button className={`btn ${view === "today" ? "primary" : ""}`} onClick={() => setView("today")}>Today</button><button className={`btn ${view === "all" ? "primary" : ""}`} onClick={() => setView("all")}>All {c.days} days</button></div>
    {view === "today" ? <>
      <div className="card"><h2>Day {today.day}: {today.theme || "Rest"} <span className="muted" style={{ fontSize: 13 }}>· ~{today.minutes} min · {today.date}</span></h2>{today.tasks.length === 0 ? <p className="muted">Nothing scheduled. Rest or catch up.</p> : today.tasks.map((t) => <TaskRow key={t.id} t={t} onToggle={toggle} />)}</div>
      {c.overdue_count > 0 && <details className="card"><summary><h2 style={{ display: "inline" }}>Catch up ▸ {c.overdue_count} unfinished from earlier days</h2></summary>{c.overdue.map((t) => <TaskRow key={t.id} t={t} onToggle={toggle} />)}</details>}</> :
      <div style={{ display: "grid", gap: 8 }}><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(54px,1fr))", gap: 6 }}>{c.plan.map((d) => <button key={d.day} onClick={() => setOpen(open === d.day ? null : d.day)} aria-label={`Day ${d.day}${d.complete ? ", complete" : ""}`} className="card" style={{ padding: "8px 4px", cursor: "pointer", textAlign: "center", borderColor: d.day === c.day_number ? "var(--cyan)" : d.complete ? "var(--lime)" : undefined, background: d.complete ? "rgba(163,230,53,.12)" : undefined }}><b className="mono">{d.day}</b><div style={{ fontSize: 10 }}>{d.complete ? "✓" : d.tasks.some((t) => t.kind === "mock") ? "🎤" : d.tasks.some((t) => t.kind === "design") ? "🧩" : "💻"}</div></button>)}</div>
        {open && c.plan.find((d) => d.day === open) && (() => { const d = c.plan.find((x) => x.day === open)!; return <div className="card"><h2>Day {d.day}: {d.theme} <span className="muted" style={{ fontSize: 13 }}>· {d.date} · ~{d.minutes} min</span></h2>{d.tasks.map((t) => <TaskRow key={t.id} t={t} onToggle={toggle} />)}</div>; })()}</div>}
    <p className="muted" style={{ fontSize: 12 }}>{c.note}</p></div>;
}

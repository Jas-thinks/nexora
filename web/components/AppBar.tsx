"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { celebrate } from "@/components/Confetti";

type G = { xp: number; level: number; level_progress: number; level_needed: number; badges_earned: number; streak: { current: number; active_today: boolean }; goals: { daily: { target: number; progress: number } } };

/** Persistent progress strip: level, XP, streak, daily goal. Celebrates level-ups and new badges (once). */
function Bell() {
  const [n, setN] = useState<{ unread: number; items: { id: number; title: string; body: string; href: string; read: boolean }[] } | null>(null), [open, setOpen] = useState(false);
  const load = useCallback(() => api<NonNullable<typeof n>>("/notifications").then(setN).catch(() => {}), []);
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, [load]);
  async function toggle() { const o = !open; setOpen(o); if (o && n?.unread) { await api("/notifications/read", { method: "POST" }).catch(() => {}); setN({ ...n, unread: 0 }); } }
  return <div style={{ position: "relative", marginLeft: "auto" }}><button aria-label={`Notifications${n?.unread ? `, ${n.unread} unread` : ""}`} aria-expanded={open} onClick={toggle} className="chip" style={{ cursor: "pointer" }}>🔔{n?.unread ? <b style={{ color: "var(--rose)" }}> {n.unread}</b> : null}</button>
    {open && <div className="card" role="dialog" aria-label="Notifications" style={{ position: "absolute", right: 0, top: 36, width: 320, maxHeight: 360, overflowY: "auto", zIndex: 50 }}>{!n?.items.length ? <p className="muted">Nothing new.</p> : n.items.map((i) => <Link key={i.id} href={i.href || "/dashboard"} onClick={() => setOpen(false)} style={{ display: "block", padding: "8px 0", borderTop: "1px solid var(--card-b)" }}><b style={{ fontSize: 13 }}>{i.title}</b><p className="muted" style={{ fontSize: 12 }}>{i.body}</p></Link>)}</div>}</div>;
}

export default function AppBar() {
  const [g, setG] = useState<G | null>(null), [toast, setToast] = useState("");
  const load = useCallback(() => api<G>("/gamification/me").then((x) => {
    setG(x);
    try { const prevL = Number(localStorage.getItem("nexora.level") || 0), prevB = Number(localStorage.getItem("nexora.badges") || -1);
      if (prevL && x.level > prevL) { setToast(`Level ${x.level} reached!`); celebrate(); } else if (prevB >= 0 && x.badges_earned > prevB) { setToast("New badge earned!"); celebrate(); }
      localStorage.setItem("nexora.level", String(x.level)); localStorage.setItem("nexora.badges", String(x.badges_earned)); } catch {}
  }).catch(() => {}), []);
  useEffect(() => { load(); window.addEventListener("nexora:refresh", load); return () => window.removeEventListener("nexora:refresh", load); }, [load]);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(""), 4500); return () => clearTimeout(t); }, [toast]);
  if (!g) return <div className="appbar" />;
  const d = g.goals.daily;
  return (<>
    <div className="appbar" role="status">
      <Link href="/progress" className="row" style={{ gap: 10 }} title="Your progress"><span className="pill mono" style={{ background: "rgba(139,92,246,.2)", color: "var(--violet)" }}>Lv {g.level}</span>
        <div><div className="xpbar" aria-label={`${g.level_progress} of ${g.level_needed} XP to next level`}><i style={{ width: `${(g.level_progress / g.level_needed) * 100}%` }} /></div><span className="mono muted" style={{ fontSize: 10 }}>{g.xp.toLocaleString()} XP</span></div></Link>
      <Link href="/analytics" title={g.streak.active_today ? "Streak safe for today" : "Solve something today to keep your streak"} className="row" style={{ gap: 6 }}>
        <span className={g.streak.current ? "flame" : ""} style={{ filter: g.streak.active_today || !g.streak.current ? "none" : "grayscale(.8)" }}>🔥</span><b className="mono">{g.streak.current}</b></Link>
      <Link href="/progress" title="Daily goal" className="chip" style={{ color: d.progress >= d.target ? "var(--lime)" : "var(--muted)" }}>{d.progress >= d.target ? "✓ " : ""}Today {d.progress}/{d.target}</Link>
      <Bell />
    </div>
    {toast && <div className="toast" role="alert"><b>🎉 {toast}</b></div>}
  </>);
}

"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Ring } from "@/components/charts";
import Tilt from "@/components/Tilt";

const XPOrb = dynamic(() => import("@/components/XPOrb"), { ssr: false, loading: () => <div className="skeleton" style={{ width: 190, height: 190, borderRadius: 99 }} /> });
type Badge = { id: string; name: string; description: string; earned: boolean; progress: number; goal: number; evidence: string | null };
type G = { streak: { current: number; longest: number; active_today: boolean }; xp: number; level: number; level_progress: number; level_needed: number; weekly_xp: number; goals: { daily: { target: number; progress: number }; weekly: { target: number; progress: number } };
  badges: Badge[]; badges_earned: number; weekly_challenge: { pattern: string; name: string; text: string; target: number; progress: number; prerequisite_for: string | null } | null; recent: { at: string; xp: number; reason: string }[]; rules: Record<string, string>; leaderboard_visible: boolean };
type LB = { entries: { rank: number; name: string; weekly_xp: number; you: boolean }[]; you: { rank: number; weekly_xp: number } | null; participants: number; note: string; week_of: string };
const ICON: Record<string, string> = { "first-solve": "🩸", "streak-3": "🔥", "streak-7": "⚔️", "streak-30": "🚀", century: "💯", explorer: "🧭", master: "👑", "hard-hitter": "🔨", comeback: "↩️", "revision-keeper": "🔁", climber: "📈" };

export default function Progress() {
  const [g, setG] = useState<G | null>(null), [lb, setLb] = useState<LB | null>(null), [err, setErr] = useState("");
  const load = useCallback(() => { api<G>("/gamification/me").then(setG).catch((e) => setErr(e.message)); api<LB>("/gamification/leaderboard").then(setLb).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  async function toggleLb() { if (!g) return; await api("/me/prefs", { method: "PUT", body: JSON.stringify({ leaderboard_visible: !g.leaderboard_visible }) }); load(); }
  if (err) return <p className="err" role="alert">{err}</p>;
  if (!g) return <div className="skeleton" style={{ height: 260 }} />;
  return (
    <div className="grid" style={{ gap: 20 }}>
      <div><h1>My <span className="grad-text">progress</span></h1><p className="muted">XP comes only from real, verified activity: no points for logging in or chatting.</p></div>
      <div className="card row" style={{ gap: 28, justifyContent: "center", background: "radial-gradient(ellipse at 20% 50%, rgba(139,92,246,.18), transparent 60%), var(--card)" }}>
        <XPOrb level={g.level} progress={g.level_progress / g.level_needed} />
        <div className="grid" style={{ gap: 6 }}><h1 className="mono" style={{ fontSize: 42 }}>{g.xp.toLocaleString()} <span className="muted" style={{ fontSize: 16 }}>XP</span></h1>
          <p className="muted">{g.level_needed - g.level_progress} XP to level {g.level + 1} · {g.weekly_xp} XP this week</p><div className="xpbar" style={{ width: 260, height: 10 }}><i style={{ width: `${(g.level_progress / g.level_needed) * 100}%` }} /></div>
          <p style={{ marginTop: 6 }}><span className="flame">🔥</span> <b className="mono">{g.streak.current}</b>-day streak <span className="muted">(best {g.streak.longest})</span>{!g.streak.active_today && g.streak.current > 0 && <span className="st learning" style={{ marginLeft: 8 }}>solve today to keep it</span>}</p></div>
        <div className="row" style={{ gap: 18 }}><Ring value={g.goals.daily.progress} max={g.goals.daily.target} label="Today" color="#22d3ee" /><Ring value={g.goals.weekly.progress} max={g.goals.weekly.target} label="This week" color="#a3e635" /></div></div>
      {g.weekly_challenge && <Tilt className="card" style={{ borderColor: "rgba(163,230,53,.5)" }}><div className="row" style={{ justifyContent: "space-between" }}><div><span className="chip">Weekly challenge · personalised</span><h2 style={{ margin: "8px 0" }}>{g.weekly_challenge.name}</h2><p className="muted" style={{ maxWidth: 640 }}>{g.weekly_challenge.text}</p></div>
        <div style={{ textAlign: "center" }}><Ring value={g.weekly_challenge.progress} max={g.weekly_challenge.target} label="solved" color="#a3e635" size={84} /><Link href={`/patterns/${g.weekly_challenge.pattern}`} className="btn" style={{ marginTop: 8 }}>Open pattern →</Link></div></div></Tilt>}
      <div><h2 style={{ marginBottom: 12 }}>Badges <span className="muted" style={{ fontSize: 14 }}>{g.badges_earned}/{g.badges.length}</span></h2>
        <div className="grid g3">{g.badges.map((b) => <Tilt key={b.id} className="card" style={{ opacity: b.earned ? 1 : 0.55, borderColor: b.earned ? "rgba(251,191,36,.55)" : undefined, boxShadow: b.earned ? "0 0 30px -10px rgba(251,191,36,.6)" : undefined }}>
          <div style={{ fontSize: 34, filter: b.earned ? "none" : "grayscale(1)" }}>{ICON[b.id] ?? "🏅"}</div><b>{b.name}</b><p className="muted" style={{ fontSize: 12, margin: "4px 0 8px" }}>{b.description}</p>
          <div className="bar"><i style={{ width: `${(b.progress / b.goal) * 100}%` }} /></div><p className="mono muted" style={{ fontSize: 11, marginTop: 6 }}>{b.earned ? `✓ ${b.evidence}` : `${b.progress}/${b.goal}`}</p></Tilt>)}</div></div>
      <div className="grid g2">
        <div className="card"><h2>Recent XP</h2>{g.recent.length ? g.recent.map((e, i) => <p key={i} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 8 }}><span>{e.reason}</span><b className="mono" style={{ color: "var(--lime)" }}>+{e.xp}</b></p>) : <p className="muted" style={{ marginTop: 8 }}>No XP yet. Solve a problem or finish the Daily Challenge.</p>}</div>
        <div className="card"><div className="row" style={{ justifyContent: "space-between" }}><h2>Weekly leaderboard</h2><button className="btn" onClick={toggleLb}>{g.leaderboard_visible ? "Leave leaderboard" : "Opt in"}</button></div>
          {lb && (lb.entries.length ? lb.entries.map((e) => <p key={e.rank} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 8, color: e.you ? "var(--cyan)" : undefined }}><span>#{e.rank} {e.name}{e.you ? " (you)" : ""}</span><b className="mono">{e.weekly_xp} XP</b></p>) : <p className="muted" style={{ marginTop: 8 }}>Nobody has opted in yet.</p>)}
          <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>{lb?.note ?? "Opt-in only. Ranks weekly XP, never ratings."}</p></div></div>
      <details className="card"><summary><h2 style={{ display: "inline" }}>How XP works ▸</h2></summary>{Object.entries(g.rules).map(([k, v]) => <p key={k} className="muted" style={{ fontSize: 13, marginTop: 8 }}>• {v}</p>)}</details>
    </div>
  );
}

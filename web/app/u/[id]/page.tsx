"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";

type P = { name: string; member_since: string; level: number; xp: number; streak: number; longest_streak: number; solved: number; badges: { id: string; name: string }[]; mastered_patterns: string[]; ratings: Record<string, { current: number; peak: number; contests: number }>; note: string };
export default function Profile({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params); const [p, setP] = useState<P | null>(null), [err, setErr] = useState("");
  useEffect(() => { api<P>(`/profile/${id}`).then(setP).catch(() => setErr("This profile doesn't exist or isn't shared.")); }, [id]);
  return (
    <main style={{ maxWidth: 820, margin: "0 auto", padding: 24, display: "grid", gap: 16 }}>
      <Link href="/"><b style={{ fontSize: 18 }}><span className="grad-text">Nexora</span> CP Mentor</b></Link>
      {err ? <p className="muted" role="alert">{err}</p> : !p ? <div className="skeleton" style={{ height: 200 }} /> : <>
        <div className="card"><h1>{p.name}</h1><p className="muted">Member since {new Date(p.member_since).toLocaleDateString()}</p>
          <div className="row" style={{ gap: 10, marginTop: 12 }}><span className="chip">Lv {p.level}</span><span className="chip">{p.xp} XP</span><span className="chip">🔥 {p.streak} (best {p.longest_streak})</span><span className="chip">{p.solved} solved</span></div></div>
        {Object.keys(p.ratings).length > 0 && <div className="card"><h2>Ratings</h2>{Object.entries(p.ratings).map(([k, v]) => <p key={k} className="row" style={{ justifyContent: "space-between", marginTop: 8 }}><span>{k}</span><span className="mono">{v.current} <span className="muted">peak {v.peak} · {v.contests} contests</span></span></p>)}</div>}
        {p.mastered_patterns.length > 0 && <div className="card"><h2>Mastered patterns</h2><div className="row" style={{ gap: 6, marginTop: 8, flexWrap: "wrap" }}>{p.mastered_patterns.map((x) => <span key={x} className="chip">{x}</span>)}</div></div>}
        {p.badges.length > 0 && <div className="card"><h2>Badges</h2><div className="row" style={{ gap: 6, marginTop: 8, flexWrap: "wrap" }}>{p.badges.map((b) => <span key={b.id} className="chip">🏅 {b.name}</span>)}</div></div>}
        <p className="muted" style={{ fontSize: 12 }}>{p.note}</p></>}
    </main>
  );
}

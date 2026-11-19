"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { motion } from "framer-motion";

const Hero3D = dynamic(() => import("@/components/Hero3D"), { ssr: false, loading: () => null });

const FEATURES = [
  ["AI mentor that teaches", "A hint ladder from concept to full solution, grounded in notes and your own history. Works with free providers (Gemini, Groq, local Ollama) and degrades honestly offline."],
  ["A pattern galaxy of your skills", "Explore 84 DSA/CP patterns as a 3D star map coloured by your real mastery, with prerequisites and exactly why each is weak or strong."],
  ["Personal analytics, not vanity charts", "Heatmap, difficulty trend, acceptance over time, rating history, abandoned problems and a next-best-action, all from your own submissions."],
  ["Daily Challenge that knows you", "One problem chosen for your weakest evidence-backed pattern, with the reasons shown, revision scheduling and a feedback loop."],
  ["Coding studio with a real sandbox", "Monaco editor, C++17 and Python, run in network-less containers with CPU, memory and process limits."],
  ["System design lab + interviewer", "Draw architectures, get deterministic reviews of single points of failure and missing caches, then defend them to an AI interviewer."],
  ["Algorithm visualiser you can question", "Step through Dijkstra, DP tables and more, then ask why a pointer moved; answers cite the exact frames."],
  ["XP that only rewards real work", "Levels, streaks, badges and weekly challenges from verified solves. Opt-in leaderboards, never ratings."],
];

export default function Landing() {
  return (
    <main style={{ position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, height: 780 }}><Hero3D /></div>
      <nav className="row" style={{ position: "relative", justifyContent: "space-between", padding: "22px 32px" }}>
        <b style={{ fontSize: 20 }}><span className="grad-text">Nexora</span> CP Mentor</b>
        <div className="row"><Link href="/login" className="btn">Sign in</Link><Link href="/login?mode=register" className="btn primary">Get started</Link></div>
      </nav>
      <section style={{ position: "relative", padding: "9vh 32px 12vh", maxWidth: 900, margin: "0 auto", textAlign: "center", pointerEvents: "none" }}>
        <div aria-hidden style={{ position: "absolute", inset: "-10% -20%", background: "radial-gradient(closest-side, rgba(7,6,13,.92) 35%, rgba(7,6,13,0) 100%)", zIndex: -1 }} />
        <motion.span initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="chip">Adaptive · Honest · Built for Codeforces grinders</motion.span>
        <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} style={{ fontSize: "clamp(40px,7vw,76px)", lineHeight: 1.02, margin: "18px 0" }}>
          Stop grinding randomly.<br /><span className="grad-text">Climb on purpose.</span>
        </motion.h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }} className="muted" style={{ fontSize: 18, maxWidth: 640, margin: "0 auto 28px" }}>
          Nexora finds your weak topics, picks the next problem at the right difficulty, explains why, and shows you how the algorithm actually runs.
        </motion.p>
        <div className="row" style={{ justifyContent: "center", pointerEvents: "auto" }}>
          <Link href="/login?mode=register" className="btn primary" style={{ padding: "14px 26px", fontSize: 16 }}>Start climbing →</Link>
          <Link href="/login" className="btn" style={{ padding: "14px 26px", fontSize: 16 }}>I have an account</Link>
        </div>
      </section>
      <section className="grid g2" style={{ position: "relative", maxWidth: 1100, margin: "0 auto", padding: "0 32px 80px" }}>
        {FEATURES.map(([t, d], i) => (
          <motion.div key={t} className="card hover" initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}>
            <h2 className="grad-text" style={{ marginBottom: 8 }}>{t}</h2><p className="muted">{d}</p>
          </motion.div>
        ))}
      </section>
    </main>
  );
}

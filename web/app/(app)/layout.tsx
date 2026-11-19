"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, tokens } from "@/lib/api";
import AppBar from "@/components/AppBar";
import Confetti from "@/components/Confetti";

const NAV: [string, string, string][] = [["", "", "Learn"], ["/dashboard", "◈", "Overview"], ["/daily", "☀", "Daily Challenge"], ["/progress", "★", "My Progress"], ["/analytics", "▤", "My Analytics"], ["/revision", "↻", "Revision"], ["/mistakes", "✎", "Mistake Notebook"], ["/planner", "🗺", "Planner"], ["/patterns", "✦", "Pattern Universe"], ["/visualizer", "◉", "Visualizer"],
  ["", "", "Build"], ["/mentor", "✧", "AI Mentor"], ["/studio", "⌨", "Coding Studio"], ["/stress", "💥", "Stress Tester"], ["/design", "⬡", "System Design"], ["/practice", "⚡", "Practice ladder"], ["/interview", "🎤", "Mock Interview"], ["/arena", "⚔", "Practice Arena"], ["/resources", "🏢", "Interview Resources"], ["/explorer", "⌕", "Problem Explorer"], ["/sheets", "☰", "Sheets"],
  ["", "", "Community"], ["/community", "☍", "Community"], ["/contests", "◷", "Contests"], ["/labels", "🏷", "Label review"],
  ["", "", "Data"], ["/connections", "⛓", "Platforms"], ["/sources", "⛁", "Data sources"], ["/settings", "⚙", "Settings"]];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(), router = useRouter();
  const [name, setName] = useState<string | null>(null);
  useEffect(() => {
    if (!tokens.get()) { router.replace("/login"); return; }
    api<{ display_name: string }>("/auth/me").then((u) => setName(u.display_name)).catch(() => router.replace("/login"));
  }, [router]);
  if (!name) return <div style={{ padding: 40 }}><div className="skeleton" style={{ width: 240, height: 32 }} /></div>;
  return (
    <div className="shell">
      <aside className="side">
        <b style={{ fontSize: 18, padding: "4px 14px 18px" }}><span className="grad-text">Nexora</span></b>
        {NAV.map(([h, i, l]) => h === "" ? <div key={l} className="navgroup t">{l}</div> : <Link key={h} href={h} className={`nav ${path.startsWith(h) ? "on" : ""}`}><span>{i}</span><span className="t">{l}</span></Link>)}
        <div style={{ marginTop: "auto" }} className="nav">
          <span className="t" style={{ flex: 1 }}>{name}</span>
          <button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={async () => { const t = tokens.get(); if (t) await api("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: t.refresh_token }) }).catch(() => {}); tokens.set(null); router.push("/"); }}>Sign out</button>
        </div>
      </aside>
      <div><AppBar /><div className="main">{children}</div><Confetti /></div>
    </div>
  );
}

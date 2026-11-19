"use client";
import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function Form() {
  const token = useSearchParams().get("token") ?? ""; const [pw, setPw] = useState(""), [done, setDone] = useState(false), [err, setErr] = useState("");
  async function go(e: React.FormEvent) { e.preventDefault(); setErr(""); try { await api("/auth/reset", { method: "POST", body: JSON.stringify({ token, password: pw }) }); setDone(true); } catch (x) { setErr((x as Error).message); } }
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}><form onSubmit={go} className="card" style={{ width: "100%", maxWidth: 400, display: "grid", gap: 14 }}>
    <h2>Choose a new password</h2>{done ? <><p role="status" style={{ color: "var(--lime)" }}>Password updated. All other sessions were signed out.</p><Link className="btn primary" href="/login">Sign in</Link></> : <>
    {!token && <p className="err">This link is missing its token.</p>}<div><label htmlFor="p">New password (10+ characters)</label><input id="p" type="password" required minLength={10} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></div>
    {err && <p className="err" role="alert">{err}</p>}<button className="btn primary" disabled={!token}>Update password</button></>}</form></main>;
}
export default function Reset() { return <Suspense><Form /></Suspense>; }

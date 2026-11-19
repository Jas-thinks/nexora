"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

export default function Forgot() {
  const [email, setEmail] = useState(""), [msg, setMsg] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  async function go(e: React.FormEvent) { e.preventDefault(); setBusy(true); setErr(""); try { const r = await api<{ message: string }>("/auth/forgot", { method: "POST", body: JSON.stringify({ email }) }); setMsg(r.message); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } }
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}><form onSubmit={go} className="card" style={{ width: "100%", maxWidth: 400, display: "grid", gap: 14 }}>
    <h2>Reset your password</h2><div><label htmlFor="e">Email</label><input id="e" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
    {msg && <p role="status" style={{ color: "var(--lime)" }}>{msg}</p>}{err && <p className="err" role="alert">{err}</p>}
    <button className="btn primary" disabled={busy}>Send reset link</button><Link href="/login" className="muted">Back to sign in</Link></form></main>;
}

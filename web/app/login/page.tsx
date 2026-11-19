"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authCall } from "@/lib/api";

function Form() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">(useSearchParams().get("mode") === "register" ? "register" : "login");
  const [f, setF] = useState({ email: "", display_name: "", password: "" });
  const [otp, setOtp] = useState(""), [needOtp, setNeedOtp] = useState(false);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await authCall(mode, mode === "login" ? { email: f.email, password: f.password, ...(needOtp ? { otp } : {}) } : f); router.push("/dashboard"); }
    catch (x) { const m = (x as Error).message; if (m === "mfa_required") { setNeedOtp(true); setErr("Enter the 6-digit code from your authenticator app."); } else setErr(m || "Something went wrong"); }
    finally { setBusy(false); }
  }
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}>
      <form onSubmit={submit} className="card" style={{ width: "100%", maxWidth: 400, display: "grid", gap: 14 }}>
        <Link href="/"><b style={{ fontSize: 20 }}><span className="grad-text">Nexora</span> CP Mentor</b></Link>
        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        {mode === "register" && <div><label htmlFor="n">Display name</label><input id="n" required maxLength={80} value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></div>}
        <div><label htmlFor="e">Email</label><input id="e" type="email" required autoComplete="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
        <div><label htmlFor="p">Password {mode === "register" && "(10+ characters)"}</label><input id="p" type="password" required minLength={mode === "register" ? 10 : 1} autoComplete={mode === "login" ? "current-password" : "new-password"} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
        {needOtp && <div><label htmlFor="o">Authenticator code</label><input id="o" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp} onChange={(e) => setOtp(e.target.value)} autoFocus /></div>}
        {mode === "login" && <Link href="/forgot" className="muted" style={{ fontSize: 13 }}>Forgot password?</Link>}
        {err && <p className="err" role="alert">{err}</p>}
        <button className="btn primary" disabled={busy} style={{ justifyContent: "center" }}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
        <button type="button" className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? "New here? Create an account" : "Already registered? Sign in"}
        </button>
      </form>
    </main>
  );
}
export default function Login() { return <Suspense><Form /></Suspense>; }

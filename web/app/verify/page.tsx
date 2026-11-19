"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function V() {
  const token = useSearchParams().get("token") ?? ""; const [s, setS] = useState<"wait" | "ok" | "bad">("wait"), [err, setErr] = useState("");
  useEffect(() => { if (!token) { setS("bad"); setErr("Missing token."); return; } api("/auth/verify", { method: "POST", body: JSON.stringify({ token }) }).then(() => setS("ok")).catch((e) => { setS("bad"); setErr(e.message); }); }, [token]);
  return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 20 }}><div className="card" style={{ maxWidth: 400, display: "grid", gap: 14 }}><h2>Email verification</h2>
    {s === "wait" && <p>Verifying…</p>}{s === "ok" && <p role="status" style={{ color: "var(--lime)" }}>Your email is verified.</p>}{s === "bad" && <p className="err" role="alert">{err || "This link is invalid or expired."}</p>}<Link className="btn" href="/dashboard">Continue</Link></div></main>;
}
export default function Verify() { return <Suspense><V /></Suspense>; }

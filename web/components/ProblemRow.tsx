"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { ratingColor } from "@/lib/rating";

export type P = { id: number; name: string; rating: number | null; tags: string[]; url: string; solved?: boolean; section?: string; reasons?: string[] };

export default function ProblemRow({ p, onDone }: { p: P; onDone?: () => void }) {
  const [state, setState] = useState<"idle" | "busy" | "ok" | "fail">(p.solved ? "ok" : "idle");
  const [err, setErr] = useState("");
  async function report(solved: boolean) {
    setState("busy"); setErr("");
    try { await api("/progress", { method: "POST", body: JSON.stringify({ problem_id: p.id, solved }) }); setState(solved ? "ok" : "fail"); onDone?.(); }
    catch (e) { setErr((e as Error).message); setState("idle"); }
  }
  return (
    <div className="card hover" style={{ padding: 16 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div style={{ minWidth: 0 }}>
          <a href={p.url} target="_blank" rel="noreferrer noopener" style={{ fontWeight: 700 }}>{p.name} ↗</a>
          <div className="row" style={{ marginTop: 8, gap: 6 }}>
            <span className="pill mono" style={{ color: ratingColor(p.rating), background: "rgba(255,255,255,.06)" }}>{p.rating ?? "unrated"}</span>
            {p.tags.slice(0, 4).map((t) => <span key={t} className="chip">{t}</span>)}
          </div>
          {p.reasons?.map((r, i) => <p key={i} className="muted" style={{ fontSize: 12, marginTop: 6 }}>• {r}</p>)}
        </div>
        <div className="row">
          {state === "ok" ? <span className="pill" style={{ color: "var(--lime)", background: "rgba(163,230,53,.12)" }}>✓ Solved</span> : <>
            <button className="btn" disabled={state === "busy"} onClick={() => report(true)}>I solved it</button>
            <button className="btn" disabled={state === "busy"} onClick={() => report(false)}>{state === "fail" ? "Logged ✓" : "Got stuck"}</button></>}
        </div>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
    </div>
  );
}

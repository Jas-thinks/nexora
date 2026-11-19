"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false, loading: () => <div className="skeleton" style={{ height: 360 }} /> });
type Langs = { languages: Record<string, { name: string; ready: boolean }>; templates: Record<string, string>; monaco: Record<string, string> };
type Gens = { contract: string; templates: Record<string, string> };
type CE = { kind: string; input: string; expected?: string; actual?: string; size: number; seed: number; detail?: string; stderr?: string; diff?: { line: number | null; expected_line: string; actual_line: string } };
type R = { status: "found" | "none_found" | "error"; iterations: number; elapsed_s: number; counterexample: CE | null; note: string };
const BRUTE = { python: "# Obviously-correct (slow) reference solution. Same input/output format as your solution.\nn = int(input())\n", cpp17: "// Obviously-correct (slow) reference solution\n#include <bits/stdc++.h>\nint main() {\n    \n}\n" } as Record<string, string>;
type Tab = "solution" | "brute" | "generator";

export default function Stress() {
  const [langs, setLangs] = useState<Langs | null>(null), [gens, setGens] = useState<Gens | null>(null), [err, setErr] = useState("");
  const [sl, setSl] = useState("python"), [bl, setBl] = useState("python"), [tab, setTab] = useState<Tab>("solution");
  const [code, setCode] = useState<Record<Tab, string>>({ solution: "", brute: BRUTE.python, generator: "" });
  const [size, setSize] = useState(8), [busy, setBusy] = useState(false), [res, setRes] = useState<R | null>(null), [ai, setAi] = useState("");
  useEffect(() => { api<Langs>("/execute/languages").then((l) => { setLangs(l); setCode((c) => ({ ...c, solution: l.templates.python })); }).catch((e) => setErr(e.message)); api<Gens>("/stress/generators").then((g) => { setGens(g); setCode((c) => ({ ...c, generator: g.templates.array })); }).catch(() => {}); }, []);
  async function go() { setBusy(true); setErr(""); setRes(null); setAi("");
    try { setRes(await api<R>("/stress", { method: "POST", body: JSON.stringify({ solution_language: sl, solution_code: code.solution, brute_language: bl, brute_code: code.brute, generator_code: code.generator, max_size: size }) })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  const lang = tab === "generator" ? "python" : tab === "solution" ? sl : bl;
  const ce = res?.counterexample;
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div><h1>Stress <span className="grad-text">tester</span></h1><p className="muted">Stuck on a Wrong Answer? Give Nexora your solution, a slow-but-obviously-correct brute force and a random-input generator. It hunts for the <b>smallest input where they disagree</b> and shows exactly where your output diverges.</p></div>
      {err && <p className="err" role="alert">{err}</p>}
      <div className="card">
        <div className="row" style={{ marginBottom: 10, justifyContent: "space-between" }}>
          <div className="seg" role="tablist">{(["solution", "brute", "generator"] as Tab[]).map((t) => <button key={t} role="tab" aria-selected={tab === t} className={`btn ${tab === t ? "primary" : ""}`} onClick={() => setTab(t)}>{t === "brute" ? "brute force" : t}</button>)}</div>
          <div className="row">
            {tab !== "generator" && langs && <select aria-label="Language" value={tab === "solution" ? sl : bl} onChange={(e) => { const v = e.target.value; if (tab === "solution") setSl(v); else { setBl(v); setCode((c) => ({ ...c, brute: BRUTE[v] ?? langs.templates[v] })); } }} style={{ width: 180 }}>{Object.entries(langs.languages).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}</select>}
            {tab === "generator" && gens && <select aria-label="Generator template" onChange={(e) => setCode((c) => ({ ...c, generator: gens.templates[e.target.value] }))} defaultValue="array" style={{ width: 180 }}>{Object.keys(gens.templates).map((k) => <option key={k} value={k}>template: {k}</option>)}</select>}
          </div></div>
        {tab === "generator" && <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{gens?.contract} Written in Python.</p>}
        <Editor height="360px" language={langs?.monaco[lang] ?? lang} value={code[tab]} onChange={(v) => setCode((c) => ({ ...c, [tab]: v ?? "" }))} theme="nexora" options={{ minimap: { enabled: false }, fontSize: 14 }} />
        <div className="row" style={{ marginTop: 12 }}><div><label htmlFor="sz">Max input size</label><input id="sz" type="number" min={1} max={30} value={size} onChange={(e) => setSize(+e.target.value)} style={{ width: 100 }} /></div>
          <button className="btn primary" disabled={busy} onClick={go} style={{ alignSelf: "flex-end" }}>{busy ? "Hunting… (up to 40 s)" : "Find a counterexample"}</button></div>
      </div>
      {res && <div className="card" aria-live="polite">
        {res.status === "found" && ce && <>
          <h2>💥 Counterexample found <span className="chip">size {ce.size}</span> <span className="chip">{ce.kind.replace("solution_", "")}</span></h2>
          <div className="grid g3" style={{ marginTop: 12 }}>
            <div><p className="muted">Input</p><pre className="mono" style={{ margin: 0, overflow: "auto" }}>{ce.input}</pre></div>
            <div><p className="muted">Brute force says</p><pre className="mono" style={{ margin: 0, overflow: "auto" }}>{ce.expected}</pre></div>
            <div><p className="muted">Your solution says</p><pre className="mono" style={{ margin: 0, overflow: "auto", color: "var(--rose)" }}>{ce.actual || "(nothing)"}</pre>{ce.stderr && <pre className="mono muted" style={{ fontSize: 11 }}>{ce.stderr}</pre>}</div></div>
          {ce.diff?.line && <p style={{ marginTop: 12 }}>First difference on output line <b>{ce.diff.line}</b>: expected <code className="mono">{ce.diff.expected_line}</code>, got <code className="mono" style={{ color: "var(--rose)" }}>{ce.diff.actual_line}</code></p>}
          <div className="row" style={{ marginTop: 12 }}><button className="btn" onClick={async () => { setAi("…"); try { const r = await api<{ answer: string }>("/mentor/chat", { method: "POST", body: JSON.stringify({ message: `My solution fails on this tiny input.\nInput:\n${ce.input}\nExpected:\n${ce.expected}\nGot:\n${ce.actual}\n${ce.stderr ?? ""}\nHelp me find the bug without giving the full solution.`, mode: "debug", code: code.solution.slice(0, 20000) }) }); setAi(r.answer); } catch (e) { setAi((e as Error).message); } }}>Ask the mentor why</button></div>
          {ai && <div className="bubble ai" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>{ai}</div>}</>}
        {res.status === "none_found" && <><h2>No disagreement found</h2><p style={{ marginTop: 8 }}>{res.note}</p></>}
        {res.status === "error" && <><h2>Could not run the test</h2><p className="err" style={{ marginTop: 8 }}>{res.note}</p></>}
        <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>{res.iterations} random inputs tried in {res.elapsed_s}s. {res.status === "found" ? res.note : ""}</p></div>}
    </div>
  );
}

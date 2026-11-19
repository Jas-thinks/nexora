"use client";
import dynamic from "next/dynamic";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { streamChat } from "@/lib/stream";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false, loading: () => <div className="skeleton" style={{ height: 460 }} /> });
type Langs = { docker: boolean; languages: Record<string, { name: string; ready: boolean }>; templates: Record<string, string>; monaco: Record<string, string>; limits: { time_s: number; memory_mb: number }; note: string };
type Run = { verdict: string; stdout: string; stderr: string; wall_ms: number; compile_ms: number | null; truncated: boolean; note: string; tests: { n: number; verdict: string; wall_ms: number; stdout: string; expected: string; stderr: string }[] };
const VC: Record<string, string> = { OK: "mastered", WA: "weak", CE: "learning", RE: "weak", TLE: "learning", MLE: "learning", OLE: "learning", ERR: "weak" };
const AI: [string, string, string][] = [["Explain", "concept", "Explain what this code does, step by step."], ["Find bugs", "debug", "Find potential bugs and edge cases in this code. Do not rewrite it."], ["Complexity", "complexity", "State the time and space complexity and why."],
  ["Review", "review", "Review this code for correctness, style and possible optimisations."], ["Edge cases", "concept", "List edge cases and 5 extra test inputs for this code."]];

function Studio() {
  const q = useSearchParams(), pid = q.get("problem"); const key = pid ? `problem:${pid}` : "scratch";
  const [langs, setLangs] = useState<Langs | null>(null), [lang, setLang] = useState("cpp17"), [code, setCode] = useState(""), [stdin, setStdin] = useState(""), [tests, setTests] = useState<{ input: string; expected: string }[]>([{ input: "", expected: "" }]);
  const [run, setRun] = useState<Run | null>(null), [busy, setBusy] = useState(""), [err, setErr] = useState(""), [saved, setSaved] = useState(""), [prob, setProb] = useState<{ name: string; url: string; platform: string } | null>(null);
  const [ai, setAi] = useState(""), [aiBusy, setAiBusy] = useState(false), [hist, setHist] = useState<{ id: number; verdict: string; language: string; created_at: string; kind: string }[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null), loaded = useRef(false);
  useEffect(() => { api<Langs>("/execute/languages").then(setLangs).catch((e) => setErr(e.message)); if (pid) api<{ name: string; url: string; platform: string }>(`/problems/${pid}`).then(setProb).catch(() => {}); }, [pid]);
  const loadHist = useCallback(() => api<typeof hist>(`/runs?limit=8${pid ? `&problem_id=${pid}` : ""}`).then(setHist).catch(() => {}), [pid]);
  useEffect(() => { loadHist(); }, [loadHist]);
  useEffect(() => { if (!langs) return; loaded.current = false; api<{ code: string | null }>(`/drafts/${key}?language=${lang}`).then((d) => { setCode(d.code ?? langs.templates[lang]); loaded.current = true; }).catch(() => { setCode(langs.templates[lang]); loaded.current = true; }); }, [langs, lang, key]);
  useEffect(() => { if (!loaded.current || !code) return; if (timer.current) clearTimeout(timer.current); timer.current = setTimeout(() => api(`/drafts/${key}`, { method: "PUT", body: JSON.stringify({ language: lang, code }) }).then(() => setSaved(new Date().toLocaleTimeString())).catch(() => {}), 1500); return () => { if (timer.current) clearTimeout(timer.current); }; }, [code, lang, key]);
  async function exec(judge: boolean) {
    setBusy(judge ? "judge" : "run"); setErr(""); setRun(null);
    try { const body: Record<string, unknown> = { language: lang, code, stdin, problem_id: pid ? +pid : null }; if (judge) body.tests = tests.filter((t) => t.input || t.expected);
      setRun(await api<Run>("/execute", { method: "POST", body: JSON.stringify(body) })); loadHist(); } catch (e) { setErr((e as Error).message); } finally { setBusy(""); } }
  async function ask(mode: string, message: string) {
    setAiBusy(true); setAi(""); try { await streamChat({ message, mode, code, problem_id: pid ? +pid : null, hint_level: 2 }, (d) => setAi((a) => a + d)).then((f) => setAi(f.answer)); } catch (e) { setAi(`⚠ ${(e as Error).message}`); } finally { setAiBusy(false); } }
  const ready = langs?.languages[lang]?.ready;
  return (
    <div className="grid" style={{ gap: 14 }} onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); exec(false); } }}>
      <div className="row" style={{ justifyContent: "space-between" }}><div><h1>Coding <span className="grad-text">studio</span></h1>
        <p className="muted">{prob ? <>Working on <a href={prob.url} target="_blank" rel="noreferrer noopener"><b>{prob.name}</b> ↗</a> ({prob.platform}). Statements stay on the platform.</> : "Scratchpad: runs in an isolated, network-less sandbox."}</p></div>
        <div className="row"><select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} style={{ width: 190 }}>{langs && Object.entries(langs.languages).map(([k, v]) => <option key={k} value={k}>{v.name}{v.ready ? "" : " (unavailable)"}</option>)}</select>
          <button className="btn" onClick={() => langs && confirm("Reset to template?") && setCode(langs.templates[lang])}>Reset</button><span className="mono muted" style={{ fontSize: 11 }}>{saved ? `saved ${saved}` : ""}</span></div></div>
      {langs && !langs.docker && <div className="card" style={{ borderColor: "rgba(251,191,36,.5)" }}><p><b>Code execution is unavailable</b>: no Docker daemon reachable by the API. You can still write code; see docs/CODE_EXECUTION.md.</p></div>}
      {err && <p className="err" role="alert">{err}</p>}
      <div className="grid g2" style={{ alignItems: "start" }}>
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <Editor height="480px" language={langs?.monaco[lang] ?? "cpp"} value={code} onChange={(v) => setCode(v ?? "")} theme="nexora"
            beforeMount={(m) => { m.editor.defineTheme("nexora", { base: "vs-dark", inherit: true, rules: [{ token: "comment", foreground: "6b6685", fontStyle: "italic" }, { token: "keyword", foreground: "a78bfa" }, { token: "string", foreground: "a3e635" }, { token: "number", foreground: "fbbf24" }], colors: { "editor.background": "#0b0912", "editor.lineHighlightBackground": "#171327", "editorLineNumber.foreground": "#4b4668", "editor.selectionBackground": "#8b5cf655" } }); }}
            options={{ fontFamily: "var(--font-mono), monospace", fontSize: 14, minimap: { enabled: false }, scrollBeyondLastLine: false, padding: { top: 14 }, smoothScrolling: true, cursorSmoothCaretAnimation: "on", tabSize: 4, automaticLayout: true }} />
          <div className="row" style={{ padding: 12, borderTop: "1px solid var(--card-b)" }}>
            <button className="btn primary" disabled={!ready || !!busy} onClick={() => exec(false)}>{busy === "run" ? "Running…" : "▶ Run (Ctrl+Enter)"}</button><button className="btn" disabled={!ready || !!busy} onClick={() => exec(true)}>{busy === "judge" ? "Judging…" : "✓ Run sample tests"}</button>
            <span className="muted" style={{ fontSize: 11 }}>limits: {langs?.limits.time_s}s wall · {langs?.limits.memory_mb} MB · no network</span></div></div>
        <div className="grid" style={{ gap: 14 }}>
          <div className="card"><label htmlFor="in">Input (stdin)</label><textarea id="in" className="mono" rows={4} value={stdin} onChange={(e) => setStdin(e.target.value)} /></div>
          <div className="card"><div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}><h2>Output {run && <span className={`st ${VC[run.verdict] ?? "weak"}`}>{run.verdict}</span>}</h2>{run && <span className="mono muted" style={{ fontSize: 11 }}>{run.wall_ms} ms wall{run.compile_ms ? ` · compile ${run.compile_ms} ms` : ""}</span>}</div>
            {!run && !busy && <p className="muted">Run your code to see output here.</p>}{busy && <div className="skeleton" style={{ height: 60 }} />}
            {run && <>{run.note && <p className="muted" style={{ fontSize: 12 }}>{run.note}</p>}{run.stdout && <pre className="mono" style={{ background: "rgba(255,255,255,.04)", padding: 10, borderRadius: 10, overflowX: "auto", maxHeight: 200, fontSize: 13 }}>{run.stdout}</pre>}{run.truncated && <p className="err" style={{ fontSize: 12 }}>Output truncated.</p>}
              {run.stderr && <pre className="mono" style={{ background: "rgba(251,113,133,.08)", color: "var(--rose)", padding: 10, borderRadius: 10, overflowX: "auto", maxHeight: 160, fontSize: 12, marginTop: 8 }}>{run.stderr}</pre>}
              {run.tests.length > 0 && <table className="t" style={{ marginTop: 8 }}><thead><tr><th>#</th><th>Verdict</th><th>Got</th><th>Expected</th></tr></thead><tbody>{run.tests.map((t) => <tr key={t.n}><td>{t.n}</td><td><span className={`st ${VC[t.verdict] ?? "weak"}`}>{t.verdict}</span></td><td className="mono">{t.stdout.slice(0, 60)}</td><td className="mono">{t.expected.slice(0, 60)}</td></tr>)}</tbody></table>}</>}
            <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>Peak memory isn&apos;t measured. Passing sample tests is not a verified solve; submit on the platform.</p></div>
          <div className="card"><div className="row" style={{ justifyContent: "space-between" }}><h2>Sample tests</h2><button className="btn" onClick={() => setTests([...tests, { input: "", expected: "" }])}>+ add</button></div>
            {tests.map((t, i) => <div key={i} className="grid g2" style={{ gap: 8, marginTop: 8 }}><textarea className="mono" rows={2} placeholder="input" value={t.input} onChange={(e) => setTests(tests.map((x, j) => j === i ? { ...x, input: e.target.value } : x))} /><textarea className="mono" rows={2} placeholder="expected output" value={t.expected} onChange={(e) => setTests(tests.map((x, j) => j === i ? { ...x, expected: e.target.value } : x))} /></div>)}</div>
        </div></div>
      <div className="grid g2">
        <div className="card"><h2>Ask the mentor about this code</h2><div className="row" style={{ gap: 6, margin: "10px 0" }}>{AI.map(([l, m, msg]) => <button key={l} className="btn" disabled={aiBusy || !code.trim()} onClick={() => ask(m, msg)}>{l}</button>)}{pid && <button className="btn" disabled={aiBusy} onClick={() => ask("hint", "Give me a hint for this problem")}>Hint</button>}</div>
          {ai ? <div className="bubble ai">{ai}</div> : <p className="muted" style={{ fontSize: 13 }}>Answers cite Nexora notes and never invent problem links.</p>}</div>
        <div className="card"><h2>Run history</h2>{hist.length ? hist.map((h) => <p key={h.id} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 8 }}><span>{h.kind} · {h.language}</span><span className={`st ${VC[h.verdict] ?? "weak"}`}>{h.verdict}</span><span className="mono muted" style={{ fontSize: 11 }}>{new Date(h.created_at).toLocaleTimeString()}</span></p>) : <p className="muted" style={{ marginTop: 8 }}>No runs yet.</p>}</div></div>
    </div>
  );
}
export default function Page() { return <Suspense><Studio /></Suspense>; }

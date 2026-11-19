"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false, loading: () => <div className="skeleton" style={{ height: 360 }} /> });
type Pl = { name: string; you: boolean; attempts: number; best_passed: number; total: number; solved: boolean };
type M = { id: number; code: string; status: string; minutes: number; max_players: number; seconds_left: number | null; is_creator: boolean; problem: { title: string; level?: string; statement?: string; samples?: { input: string; output: string }[]; hidden_tests?: number }; players: Pl[]; winner: string | null; result: string | null };
type Pr = { key: string; title: string; level: string; hidden_tests: number };
type Langs = { languages: Record<string, { name: string; ready: boolean }>; templates: Record<string, string>; monaco: Record<string, string> };
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function Arena() {
  const [m, setM] = useState<M | null>(null), [probs, setProbs] = useState<Pr[]>([]), [mine, setMine] = useState<M[]>([]), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  const [key, setKey] = useState(""), [mins, setMins] = useState(20), [maxp, setMaxp] = useState(2), [code, setCode] = useState(""), [joinCode, setJoinCode] = useState(""), [langs, setLangs] = useState<Langs | null>(null), [lang, setLang] = useState("python"), [left, setLeft] = useState(0), [last, setLast] = useState<{ verdict?: string; passed?: number; total?: number } | null>(null);
  const loaded = useRef("");
  useEffect(() => { api<Pr[]>("/arena/problems").then((p) => { setProbs(p); setKey(p[0]?.key ?? ""); }).catch((e) => setErr(e.message)); api<M[]>("/arena/matches").then(setMine).catch(() => {}); api<Langs>("/execute/languages").then(setLangs).catch(() => {}); }, []);
  useEffect(() => { if (langs && loaded.current !== lang) { loaded.current = lang; setCode(langs.templates[lang] ?? ""); } }, [langs, lang]);
  useEffect(() => { if (m?.seconds_left != null) setLeft(m.seconds_left); }, [m]);
  useEffect(() => { if (m?.status !== "running") return; const t = setInterval(() => setLeft((x) => Math.max(0, x - 1)), 1000); return () => clearInterval(t); }, [m?.status]);
  const refresh = useCallback(async (id: number) => { try { setM(await api<M>(`/arena/matches/${id}`)); } catch (e) { setErr((e as Error).message); } }, []);
  useEffect(() => { if (!m || m.status === "finished") return; const t = setInterval(() => refresh(m.id), 3000); return () => clearInterval(t); }, [m, refresh]);
  async function act<T>(f: () => Promise<T>) { setErr(""); setBusy(true); try { return await f(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } }
  const create = () => act(async () => setM(await api<M>("/arena/matches", { method: "POST", body: JSON.stringify({ problem_key: key, minutes: mins, max_players: maxp }) })));
  const join = () => act(async () => setM(await api<M>("/arena/matches/join", { method: "POST", body: JSON.stringify({ code: joinCode.trim().toUpperCase() }) })));
  const start = () => m && act(async () => setM(await api<M>(`/arena/matches/${m.id}/start`, { method: "POST" })));
  const submit = () => m && act(async () => { const r = await api<{ verdict?: string; passed?: number; total?: number }>(`/arena/matches/${m.id}/submit`, { method: "POST", body: JSON.stringify({ language: lang, code }) }); setLast(r); await refresh(m.id); window.dispatchEvent(new Event("nexora:refresh")); });
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div><h1>Practice <span className="grad-text">arena</span></h1><p className="muted">Race friends on the same problem. Submissions run against hidden tests in the sandbox; ranking is by who solves first, then tests passed.</p></div>
      {err && <p className="err" role="alert">{err}</p>}
      {!m ? <div className="grid g2">
        <div className="card"><h2>Create a match</h2><div className="grid" style={{ gap: 10, marginTop: 10 }}><div><label htmlFor="pk">Problem</label><select id="pk" value={key} onChange={(e) => setKey(e.target.value)}>{probs.map((p) => <option key={p.key} value={p.key}>{p.title} · {p.level}</option>)}</select></div>
          <div className="row"><div><label htmlFor="mn">Minutes</label><input id="mn" type="number" min={5} max={90} value={mins} onChange={(e) => setMins(+e.target.value)} /></div><div><label htmlFor="mp">Players</label><input id="mp" type="number" min={2} max={8} value={maxp} onChange={(e) => setMaxp(+e.target.value)} /></div></div>
          <button className="btn primary" disabled={busy || !key} onClick={create}>Create</button></div></div>
        <div className="card"><h2>Join with a code</h2><div className="row" style={{ marginTop: 10 }}><input aria-label="Match code" maxLength={8} value={joinCode} onChange={(e) => setJoinCode(e.target.value)} placeholder="ABC123" style={{ width: 160, textTransform: "uppercase" }} /><button className="btn primary" disabled={busy || joinCode.length < 4} onClick={join}>Join</button></div>
          <h2 style={{ marginTop: 18 }}>Your matches</h2>{mine.length === 0 ? <p className="muted" style={{ marginTop: 8 }}>None yet.</p> : mine.map((x) => <p key={x.id} style={{ fontSize: 13, marginTop: 8 }}><button className="muted" style={{ background: "none", border: 0, cursor: "pointer" }} onClick={() => { setLast(null); setM(x); }}>{x.problem.title} · {x.status}{x.winner ? ` · won by ${x.winner}` : ""}</button></p>)}</div></div> : <>
        <div className="card row" style={{ justifyContent: "space-between" }}><div><span className="chip">code <b className="mono">{m.code}</b></span> <span className="chip">{m.status}</span><h2 style={{ marginTop: 8 }}>{m.problem.title}</h2></div>
          <div style={{ textAlign: "center" }}>{m.status === "running" ? <h1 className="mono" style={{ color: left < 60 ? "var(--rose)" : undefined }}>{mmss(left)}</h1> : m.status === "waiting" && m.is_creator ? <button className="btn primary" disabled={busy || m.players.length < 2} onClick={start}>{m.players.length < 2 ? "Waiting for players…" : "Start match"}</button> : <span className="muted">{m.status}</span>}</div></div>
        <div className="card"><h2>Players</h2>{m.players.map((p) => <div key={p.name + p.you} className="row" style={{ justifyContent: "space-between", marginTop: 8 }}><span>{p.name}{p.you ? " (you)" : ""} {p.solved && <span className="st mastered">solved</span>}</span><span className="mono muted" style={{ fontSize: 13 }}>{p.best_passed}/{p.total || m.problem.hidden_tests || "?"} tests · {p.attempts} attempts</span></div>)}
          {m.status === "finished" && <p style={{ marginTop: 10 }}>🏁 {m.winner ? `Winner: ${m.winner}` : "No winner"} <span className="muted">{m.result}</span></p>}</div>
        {m.status !== "waiting" && m.problem.statement && <div className="card"><p style={{ whiteSpace: "pre-wrap" }}>{m.problem.statement}</p>{m.problem.samples?.map((s, i) => <div key={i} className="grid g2" style={{ marginTop: 10 }}><pre className="mono" style={{ margin: 0 }}>{s.input}</pre><pre className="mono" style={{ margin: 0 }}>{s.output}</pre></div>)}</div>}
        {m.status === "running" && <div className="card"><div className="row" style={{ marginBottom: 8 }}><select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} style={{ width: 180 }}>{langs && Object.entries(langs.languages).map(([k, v]) => <option key={k} value={k}>{v.name}{v.ready ? "" : " (unavailable)"}</option>)}</select><button className="btn primary" disabled={busy} onClick={submit}>{busy ? "Judging…" : "Submit"}</button>{last && <span className={`st ${last.verdict === "accepted" ? "mastered" : "weak"}`}>{last.verdict} {last.passed}/{last.total}</span>}</div>
          <Editor height="420px" language={langs?.monaco[lang] ?? "python"} value={code} onChange={(v) => setCode(v ?? "")} theme="nexora" options={{ minimap: { enabled: false }, fontSize: 14 }} /></div>}
        <button className="btn" onClick={() => { setM(null); setLast(null); api<M[]>("/arena/matches").then(setMine).catch(() => {}); }}>← Back</button></>}
    </div>
  );
}

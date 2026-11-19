"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, tokens } from "@/lib/api";

type P = { training_opt_in: boolean; leaderboard_visible: boolean; share_progress: boolean; experiment_opt_out: boolean; email_notifications: boolean; daily_goal: number; weekly_goal: number };
type St = { configured: string[]; offline: boolean; providers: Record<string, { model: string; ready: boolean }>; tokens_used_24h: number };

type Tok = { id: number; label: string; prefix: string; created_at: string; last_used_at: string | null; revoked: boolean };
function Extension() {
  const [toks, setToks] = useState<Tok[]>([]), [fresh, setFresh] = useState(""), [err, setErr] = useState("");
  const load = () => api<Tok[]>("/capture/tokens").then(setToks).catch(() => {});
  useEffect(() => { load(); }, []);
  async function create() { setErr(""); try { const r = await api<{ token: string }>("/capture/tokens", { method: "POST", body: JSON.stringify({ label: "browser extension" }) }); setFresh(r.token); load(); } catch (e) { setErr((e as Error).message); } }
  return <div className="card"><h2>Browser extension</h2>
    <p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>Install the Nexora Capture extension (see <code>extension/README.md</code>) to record the verdicts of your own LeetCode submissions. It never reads or sends your code. Captured rows are labelled <b>captured, not verified</b> and never auto-complete a Daily Challenge.</p>
    <button className="btn" onClick={create}>Create capture token</button>
    {fresh && <div style={{ marginTop: 10 }}><p className="muted" style={{ fontSize: 12 }}>Copy it now; it is shown only once. Paste it in the extension&apos;s options.</p><code className="mono" style={{ wordBreak: "break-all" }}>{fresh}</code></div>}
    {err && <p className="err" role="alert">{err}</p>}
    {toks.filter((t) => !t.revoked).map((t) => <p key={t.id} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 8 }}><span className="mono">{t.prefix}… <span className="muted">{t.last_used_at ? `last used ${new Date(t.last_used_at).toLocaleString()}` : "never used"}</span></span><button className="btn" onClick={async () => { await api(`/capture/tokens/${t.id}`, { method: "DELETE" }); load(); }}>Revoke</button></p>)}</div>;
}

type Me = { email: string; email_verified: boolean; mfa_enabled: boolean };
function Security() {
  const [me, setMe] = useState<Me | null>(null), [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null), [code, setCode] = useState(""), [pw, setPw] = useState(""), [msg, setMsg] = useState(""), [err, setErr] = useState("");
  const load = () => api<Me>("/auth/me").then(setMe).catch(() => {});
  useEffect(() => { load(); }, []);
  async function run(f: () => Promise<unknown>, ok: string) { setErr(""); setMsg(""); try { await f(); setMsg(ok); await load(); } catch (e) { setErr((e as Error).message); } }
  if (!me) return null;
  return <div className="card"><h2>Account security</h2>
    <p style={{ marginTop: 10, fontSize: 14 }}>Email {me.email}: {me.email_verified ? <span className="st mastered">verified</span> : <><span className="st weak">not verified</span> <button className="btn" onClick={() => run(() => api("/auth/verify/request", { method: "POST" }), "Verification link sent (if SMTP is configured).")}>Send verification</button></>}</p>
    <div style={{ marginTop: 14 }}><b>Two-factor authentication:</b> {me.mfa_enabled ? <span className="st mastered">on</span> : <span className="st learning">off</span>}
      {!me.mfa_enabled && !setup && <button className="btn" style={{ marginLeft: 10 }} onClick={() => run(async () => setSetup(await api("/auth/mfa/setup", { method: "POST" })), "")}>Set up</button>}
      {setup && <div className="grid" style={{ gap: 8, marginTop: 10 }}><p className="muted" style={{ fontSize: 13 }}>Add this secret to an authenticator app (or paste the URI), then enter a code:</p><code className="mono" style={{ wordBreak: "break-all" }}>{setup.secret}</code><code className="mono muted" style={{ fontSize: 11, wordBreak: "break-all" }}>{setup.otpauth_uri}</code>
        <div className="row"><input aria-label="6-digit code" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 120 }} /><button className="btn primary" onClick={() => run(async () => { await api("/auth/mfa/enable", { method: "POST", body: JSON.stringify({ code }) }); setSetup(null); setCode(""); }, "Two-factor authentication enabled.")}>Enable</button></div></div>}
      {me.mfa_enabled && <div className="row" style={{ marginTop: 10 }}><input aria-label="Code to disable" placeholder="current code" inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 140 }} /><input aria-label="Password" type="password" placeholder="password" value={pw} onChange={(e) => setPw(e.target.value)} style={{ width: 160 }} /><button className="btn" onClick={() => run(() => api("/auth/mfa/disable", { method: "POST", body: JSON.stringify({ code, password: pw }) }), "Two-factor authentication disabled.")}>Disable</button></div>}</div>
    {msg && <p role="status" style={{ color: "var(--lime)", marginTop: 8 }}>{msg}</p>}{err && <p className="err" role="alert" style={{ marginTop: 8 }}>{err}</p>}</div>;
}

export default function Settings() {
  const router = useRouter(); const [p, setP] = useState<P | null>(null), [st, setSt] = useState<St | null>(null), [msg, setMsg] = useState(""), [err, setErr] = useState("");
  useEffect(() => { api<P>("/me/prefs").then(setP).catch((e) => setErr(e.message)); api<St>("/mentor/status").then(setSt).catch(() => {}); }, []);
  async function save(patch: Partial<P>) { try { setP(await api<P>("/me/prefs", { method: "PUT", body: JSON.stringify(patch) })); setMsg("Saved."); setTimeout(() => setMsg(""), 1800); window.dispatchEvent(new Event("nexora:refresh")); } catch (e) { setErr((e as Error).message); } }
  async function exportData() { const d = await api<object>("/auth/me/export"); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); a.download = "nexora-export.json"; a.click(); }
  async function del() { if (!confirm("Permanently delete your account and data? This cannot be undone.")) return; await api("/auth/me", { method: "DELETE" }); tokens.set(null); router.push("/"); }
  if (!p) return err ? <p className="err" role="alert">{err}</p> : <div className="skeleton" style={{ height: 200 }} />;
  const Sw = ({ k, label, hint }: { k: "training_opt_in" | "leaderboard_visible" | "share_progress" | "experiment_opt_out" | "email_notifications"; label: string; hint: string }) => <label style={{ display: "flex", gap: 12, alignItems: "flex-start", margin: "12px 0", cursor: "pointer" }}><input type="checkbox" style={{ width: "auto", marginTop: 3 }} checked={p[k]} onChange={(e) => save({ [k]: e.target.checked })} /><span><b style={{ color: "var(--text)", fontSize: 14 }}>{label}</b><br /><span className="muted" style={{ fontSize: 12 }}>{hint}</span></span></label>;
  return (
    <div className="grid" style={{ gap: 18, maxWidth: 820 }}>
      <div><h1>Settings</h1><p className="muted">You control what is shared and what is learned from your activity. Defaults are the private ones.</p></div>
      {err && <p className="err" role="alert">{err}</p>}{msg && <p role="status" style={{ color: "var(--lime)" }}>{msg}</p>}
      <div className="card"><h2>Privacy</h2><Sw k="training_opt_in" label="Use my mentor chats to improve Nexora's models" hint="Off by default. Stored without your user id; you can opt out any time (already-exported examples can't be recalled)." /><Sw k="leaderboard_visible" label="Show me on the weekly leaderboard" hint="Shows your display name and weekly XP only. Never ratings." /><Sw k="share_progress" label="Allow sharing my progress" hint="Reserved for profile sharing; nothing is public today." /></div>
      <div className="card"><h2>Notifications & research</h2><Sw k="email_notifications" label="Email me contest and revision reminders" hint="Off by default. Requires the server to have SMTP configured; otherwise nothing is sent." /><Sw k="experiment_opt_out" label="Exclude me from the recommendation experiment" hint="A small share of users get a simple baseline daily challenge so we can measure whether the personalised one helps. Opting out always gives you the personalised version." /></div>
      <Security />
      <Extension />
      <div className="card"><h2>Goals</h2><div className="row" style={{ marginTop: 10 }}><div><label htmlFor="dg">Daily solves</label><input id="dg" type="number" min={1} max={20} defaultValue={p.daily_goal} onBlur={(e) => save({ daily_goal: Math.min(20, Math.max(1, +e.target.value || 1)) })} /></div><div><label htmlFor="wg">Weekly solves</label><input id="wg" type="number" min={1} max={100} defaultValue={p.weekly_goal} onBlur={(e) => save({ weekly_goal: Math.min(100, Math.max(1, +e.target.value || 1)) })} /></div></div></div>
      <div className="card"><h2>AI providers</h2>{st && <><p className="muted" style={{ fontSize: 13, margin: "8px 0" }}>{st.offline ? "No provider is available: the mentor runs offline from Nexora's notes." : `Active: ${st.configured.join(" → ")}`}. Tokens used in the last 24 h: {st.tokens_used_24h.toLocaleString()}.</p>
        {Object.entries(st.providers).map(([k, v]) => <p key={k} className="row" style={{ justifyContent: "space-between", fontSize: 13, marginTop: 6 }}><span className="mono">{k} <span className="muted">{v.model}</span></span><span className={`st ${v.ready ? "mastered" : "unexplored"}`}>{v.ready ? "ready" : "not configured"}</span></p>)}</>}
        <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>Keys are server-side environment variables (see .env.example); they are never shown in the app.</p></div>
      <div className="card"><h2>Your data</h2><div className="row" style={{ marginTop: 10 }}><button className="btn" onClick={exportData}>Download my data (JSON)</button><button className="btn" style={{ borderColor: "var(--rose)", color: "var(--rose)" }} onClick={del}>Delete my account</button></div></div>
    </div>
  );
}

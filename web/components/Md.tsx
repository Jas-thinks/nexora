import { Fragment } from "react";

/** Minimal, safe markdown for mentor answers: **bold**, `code`, bullets, numbered lines, and bold-only lines as headings. No HTML is ever injected. */
function inline(s: string) {
  return s.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : p.startsWith("`") && p.endsWith("`") ? <code key={i} className="mono">{p.slice(1, -1)}</code> : p.startsWith("*") && p.endsWith("*") && p.length > 2 ? <i key={i}>{p.slice(1, -1)}</i> : <Fragment key={i}>{p}</Fragment>);
}
export default function Md({ text }: { text: string }) {
  const lines = text.split("\n");
  return <div style={{ display: "grid", gap: 6, lineHeight: 1.55 }}>{lines.map((l, i) => {
    const t = l.trim();
    if (!t) return <div key={i} style={{ height: 2 }} />;
    if (/^\*\*[^*]+\*\*:?$/.test(t) || /^#{1,4}\s/.test(t)) return <h3 key={i} style={{ marginTop: 10, fontSize: 15 }}>{inline(t.replace(/^#{1,4}\s/, "").replace(/^\*\*|\*\*:?$/g, ""))}</h3>;
    const b = /^[-*•]\s+(.*)/.exec(t), n = /^(\d+)[.)]\s+(.*)/.exec(t);
    if (b) return <div key={i} style={{ display: "flex", gap: 8, paddingLeft: 6 }}><span className="muted">•</span><span>{inline(b[1])}</span></div>;
    if (n) return <div key={i} style={{ display: "flex", gap: 8, paddingLeft: 6 }}><span className="muted mono">{n[1]}.</span><span>{inline(n[2])}</span></div>;
    return <p key={i}>{inline(t)}</p>;
  })}</div>;
}

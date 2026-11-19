"use client";
import { useEffect, useRef } from "react";

export const celebrate = () => window.dispatchEvent(new Event("nexora:celebrate"));

/** Lightweight canvas confetti (no dependency). Triggered by celebrate(). Respects prefers-reduced-motion. */
export default function Confetti() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current!; const ctx = cv.getContext("2d")!; let raf = 0; let ps: { x: number; y: number; vx: number; vy: number; r: number; c: string; a: number; v: number }[] = [];
    const fit = () => { cv.width = window.innerWidth; cv.height = window.innerHeight; }; fit(); window.addEventListener("resize", fit);
    const tick = () => { ctx.clearRect(0, 0, cv.width, cv.height); ps = ps.filter((p) => p.y < cv.height + 20 && p.a > 0.02);
      for (const p of ps) { p.x += p.vx; p.y += p.vy; p.vy += 0.16; p.a -= 0.006; p.r += p.v; ctx.save(); ctx.globalAlpha = Math.max(p.a, 0); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.fillRect(-4, -2, 8, 4); ctx.restore(); }
      raf = ps.length ? requestAnimationFrame(tick) : 0; };
    const go = () => { if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return; const cols = ["#8b5cf6", "#22d3ee", "#a3e635", "#fbbf24", "#fb7185"];
      for (let i = 0; i < 140; i++) ps.push({ x: cv.width / 2 + (Math.random() - 0.5) * 200, y: cv.height * 0.35, vx: (Math.random() - 0.5) * 14, vy: -Math.random() * 12 - 3, r: Math.random() * 6, c: cols[i % 5], a: 1, v: (Math.random() - 0.5) * 0.3 });
      if (!raf) raf = requestAnimationFrame(tick); };
    window.addEventListener("nexora:celebrate", go);
    return () => { window.removeEventListener("nexora:celebrate", go); window.removeEventListener("resize", fit); cancelAnimationFrame(raf); };
  }, []);
  return <canvas ref={ref} aria-hidden style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 60 }} />;
}

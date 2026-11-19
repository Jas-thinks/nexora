"use client";
import { useRef } from "react";

/** Subtle 3D tilt on hover (CSS perspective). Disabled for reduced-motion users via CSS. */
export default function Tilt({ children, className = "", max = 8, style }: { children: React.ReactNode; className?: string; max?: number; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.MouseEvent) => { const el = ref.current; if (!el) return; const r = el.getBoundingClientRect(); const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(900px) rotateX(${(-y * max).toFixed(2)}deg) rotateY(${(x * max).toFixed(2)}deg) translateZ(6px)`; el.style.setProperty("--gx", `${(x + 0.5) * 100}%`); el.style.setProperty("--gy", `${(y + 0.5) * 100}%`); };
  const leave = () => { if (ref.current) ref.current.style.transform = ""; };
  return <div ref={ref} className={`tilt ${className}`} style={style} onMouseMove={move} onMouseLeave={leave}>{children}</div>;
}

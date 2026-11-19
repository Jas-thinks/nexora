"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, Line, OrbitControls, Stars } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

export type GNode = { id: string; name: string; parent: string; status: string; score: number };
export type GCat = { id: string; name: string };
const COLOR: Record<string, string> = { mastered: "#a3e635", practised: "#22d3ee", learning: "#fbbf24", weak: "#fb7185", unexplored: "#6b6685", unmeasured: "#3b3556" };

const hash = (s: string) => { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; };

function Scene({ nodes, cats, edges, onPick }: { nodes: GNode[]; cats: GCat[]; edges: [string, string][]; onPick: (id: string) => void }) {
  const group = useRef<THREE.Group>(null!); const [hover, setHover] = useState<string | null>(null);
  const pos = useMemo(() => {
    const m: Record<string, THREE.Vector3> = {}; const n = cats.length;
    const center: Record<string, THREE.Vector3> = {};
    cats.forEach((c, i) => { const phi = Math.acos(1 - 2 * (i + 0.5) / n), th = Math.PI * (1 + Math.sqrt(5)) * i; center[c.id] = new THREE.Vector3(Math.cos(th) * Math.sin(phi), Math.sin(th) * Math.sin(phi), Math.cos(phi)).multiplyScalar(5.2); });
    nodes.forEach((p) => { const c = center[p.parent] ?? new THREE.Vector3(); const a = hash(p.id) * Math.PI * 2, b = hash(p.id + "z") * Math.PI; m[p.id] = c.clone().add(new THREE.Vector3(Math.cos(a) * Math.sin(b), Math.sin(a) * Math.sin(b), Math.cos(b)).multiplyScalar(1.05 + hash(p.id + "r") * 0.6)); });
    return m;
  }, [nodes, cats]);
  useFrame((_, dt) => { if (!hover) group.current.rotation.y += dt * 0.05; });
  return (
    <group ref={group}>
      {edges.map(([a, b], i) => pos[a] && pos[b] && <Line key={i} points={[pos[a], pos[b]]} color="#8b5cf6" transparent opacity={0.16} lineWidth={1} />)}
      {nodes.map((p) => { const r = 0.09 + p.score * 0.17; const c = COLOR[p.status] ?? "#6b6685"; return (
        <mesh key={p.id} position={pos[p.id]} onPointerOver={(e) => { e.stopPropagation(); setHover(p.id); document.body.style.cursor = "pointer"; }} onPointerOut={() => { setHover(null); document.body.style.cursor = ""; }} onClick={(e) => { e.stopPropagation(); onPick(p.id); }}>
          <sphereGeometry args={[hover === p.id ? r * 1.5 : r, 16, 16]} /><meshStandardMaterial color={c} emissive={c} emissiveIntensity={p.status === "unmeasured" ? 0.25 : p.status === "unexplored" ? 0.5 : 1.7} />
          {hover === p.id && <Html distanceFactor={9} center style={{ pointerEvents: "none" }}><div style={{ background: "rgba(13,11,23,.92)", border: "1px solid rgba(255,255,255,.15)", borderRadius: 10, padding: "6px 10px", whiteSpace: "nowrap", fontSize: 12, color: "#ece9f8", transform: "translateY(-26px)" }}><b>{p.name}</b><br /><span style={{ color: c }}>{p.status}</span> · {Math.round(p.score * 100)}%</div></Html>}
        </mesh>); })}
      {cats.map((c, i) => { const n = cats.length; const phi = Math.acos(1 - 2 * (i + 0.5) / n), th = Math.PI * (1 + Math.sqrt(5)) * i; const v = new THREE.Vector3(Math.cos(th) * Math.sin(phi), Math.sin(th) * Math.sin(phi), Math.cos(phi)).multiplyScalar(6.9);
        return <Html key={c.id} position={v} center distanceFactor={11} style={{ pointerEvents: "none" }}><span style={{ color: "#9a95b5", fontSize: 11, letterSpacing: ".08em", textTransform: "uppercase", whiteSpace: "nowrap", textShadow: "0 0 8px #000" }}>{c.name}</span></Html>; })}
    </group>
  );
}

export default function Galaxy3D({ nodes, cats, edges, onPick, height = 520 }: { nodes: GNode[]; cats: GCat[]; edges: [string, string][]; onPick: (id: string) => void; height?: number }) {
  return (
    <div style={{ height, borderRadius: 16, overflow: "hidden", background: "radial-gradient(ellipse at center, rgba(139,92,246,.12), rgba(7,6,13,.9) 70%)", border: "1px solid var(--card-b)" }}>
      <Canvas camera={{ position: [0, 0, 15], fov: 55 }} dpr={[1, 1.6]} aria-label="3D map of patterns coloured by your mastery">
        <ambientLight intensity={0.6} /><pointLight position={[8, 8, 8]} intensity={30} /><Stars radius={60} depth={30} count={900} factor={3} fade speed={0.4} />
        <Scene nodes={nodes} cats={cats} edges={edges} onPick={onPick} /><OrbitControls enablePan={false} minDistance={8} maxDistance={24} />
      </Canvas>
    </div>
  );
}

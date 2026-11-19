"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, MeshDistortMaterial } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";

function Orb({ progress, level }: { progress: number; level: number }) {
  const ring = useRef<THREE.Mesh>(null!), core = useRef<THREE.Mesh>(null!);
  useFrame((_, dt) => { ring.current.rotation.z -= dt * 0.25; core.current.rotation.y += dt * 0.3; });
  const hue = ["#8b5cf6", "#22d3ee", "#a3e635", "#fbbf24", "#fb7185"][Math.min(4, Math.floor((level - 1) / 5))];
  return (
    <Float speed={2} rotationIntensity={0.3} floatIntensity={0.6}>
      <mesh ref={core}><icosahedronGeometry args={[1, 6]} /><MeshDistortMaterial color={hue} emissive={hue} emissiveIntensity={0.7} distort={0.28 + Math.min(level, 20) * 0.01} speed={2.2} roughness={0.2} metalness={0.4} /></mesh>
      <mesh ref={ring} rotation={[Math.PI / 2.6, 0, 0]}><torusGeometry args={[1.55, 0.045, 16, 100, Math.max(0.05, progress) * Math.PI * 2]} /><meshBasicMaterial color="#ece9f8" /></mesh>
      <mesh rotation={[Math.PI / 2.6, 0, 0]}><torusGeometry args={[1.55, 0.02, 16, 100]} /><meshBasicMaterial color="#ffffff" transparent opacity={0.12} /></mesh>
    </Float>
  );
}

export default function XPOrb({ level, progress, size = 190 }: { level: number; progress: number; size?: number }) {
  return (
    <div style={{ width: size, height: size, position: "relative" }}>
      <Canvas camera={{ position: [0, 0, 4.6], fov: 45 }} dpr={[1, 1.5]} aria-label={`Level ${level}`}><ambientLight intensity={0.8} /><pointLight position={[3, 3, 4]} intensity={25} /><Orb progress={progress} level={level} /></Canvas>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", pointerEvents: "none" }}><div style={{ textAlign: "center", textShadow: "0 2px 12px #000" }}><div className="muted" style={{ fontSize: 10, letterSpacing: ".14em" }}>LEVEL</div><div className="mono" style={{ fontSize: 38, fontWeight: 800 }}>{level}</div></div></div>
    </div>
  );
}

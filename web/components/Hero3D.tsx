"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line, Stars } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";

// A knowledge graph you can look around in: nodes = concepts, edges = prerequisites.
function Graph() {
  const group = useRef<THREE.Group>(null!);
  const { nodes, edges } = useMemo(() => {
    const n: THREE.Vector3[] = [];
    for (let i = 0; i < 38; i++) {
      const phi = Math.acos(1 - 2 * (i + 0.5) / 38), th = Math.PI * (1 + Math.sqrt(5)) * i;
      n.push(new THREE.Vector3(Math.cos(th) * Math.sin(phi), Math.sin(th) * Math.sin(phi), Math.cos(phi)).multiplyScalar(2.3));
    }
    const e: [THREE.Vector3, THREE.Vector3][] = [];
    n.forEach((a, i) => n.forEach((b, j) => { if (j > i && a.distanceTo(b) < 1.45) e.push([a, b]); }));
    return { nodes: n, edges: e };
  }, []);
  useFrame(({ pointer }, dt) => {
    group.current.rotation.y += dt * 0.12;
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, pointer.y * 0.4, 0.05);
    group.current.rotation.z = THREE.MathUtils.lerp(group.current.rotation.z, -pointer.x * 0.25, 0.05);
  });
  return (
    <group ref={group}>
      {edges.map(([a, b], i) => <Line key={i} points={[a, b]} color={i % 3 ? "#8b5cf6" : "#22d3ee"} lineWidth={1} transparent opacity={0.35} />)}
      {nodes.map((p, i) => (
        <Float key={i} speed={1.5} floatIntensity={0.4}>
          <mesh position={p}>
            <sphereGeometry args={[i % 7 === 0 ? 0.14 : 0.075, 16, 16]} />
            <meshStandardMaterial color={i % 7 === 0 ? "#a3e635" : i % 2 ? "#22d3ee" : "#8b5cf6"} emissive={i % 7 === 0 ? "#a3e635" : i % 2 ? "#22d3ee" : "#8b5cf6"} emissiveIntensity={1.6} />
          </mesh>
        </Float>
      ))}
      <mesh><icosahedronGeometry args={[1.25, 1]} /><meshBasicMaterial color="#8b5cf6" wireframe transparent opacity={0.25} /></mesh>
    </group>
  );
}

export default function Hero3D() {
  return (
    <Canvas camera={{ position: [0, 0, 6.2], fov: 50 }} dpr={[1, 1.75]} aria-hidden>
      <ambientLight intensity={0.5} /><pointLight position={[5, 5, 5]} intensity={20} />
      <Stars radius={60} depth={30} count={1500} factor={3} fade speed={0.6} />
      <Graph />
    </Canvas>
  );
}

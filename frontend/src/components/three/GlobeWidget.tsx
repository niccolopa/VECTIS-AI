import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

// Generic tactical wireframe globe — a slowly spinning planet that reads as
// "global intelligence" without pinning the platform to any one region.
// Interactive: drag to orbit, scroll to zoom (OrbitControls). Pure visual widget.

const NEON = "#39ff14";
const R = 2;

function Globe() {
  const group = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.15;
  });

  return (
    <group ref={group}>
      {/* Wireframe sphere — the graticule reads as a global grid. */}
      <mesh>
        <sphereGeometry args={[R, 28, 28]} />
        <meshBasicMaterial color={NEON} wireframe transparent opacity={0.28} />
      </mesh>
      {/* Solid inner shell for depth. */}
      <mesh scale={0.985}>
        <sphereGeometry args={[R, 32, 32]} />
        <meshBasicMaterial color="#001a0d" transparent opacity={0.6} />
      </mesh>
    </group>
  );
}

export function GlobeWidget({ className }: { className?: string }) {
  return (
    <div className={className} style={{ width: "100%", height: "100%" }}>
      <Canvas camera={{ position: [0, 1.2, 5], fov: 45 }} dpr={[1, 2]}>
        <ambientLight intensity={0.5} />
        <Globe />
        <OrbitControls enablePan={false} minDistance={3.2} maxDistance={8} autoRotate={false} />
      </Canvas>
    </div>
  );
}

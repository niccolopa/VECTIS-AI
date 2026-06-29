import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";

// Tactical green wireframe globe. Plots the Liguria region and
// its provinces as glowing nodes on a slowly spinning sphere. Interactive: drag to
// orbit, scroll to zoom (OrbitControls). Pure visual widget — coordinates are the
// real province centroids so it reads as "our Liguria data", not decoration.

const NEON = "#39ff14";
const CYAN = "#00ffd5";

// Province centroids (lat, lon). Liguria, NW Italy.
const PROVINCES: { name: string; lat: number; lon: number }[] = [
  { name: "Genova", lat: 44.41, lon: 8.93 },
  { name: "Savona", lat: 44.31, lon: 8.48 },
  { name: "Imperia", lat: 43.89, lon: 8.04 },
  { name: "La Spezia", lat: 44.1, lon: 9.83 },
];

const R = 2;

function toVec3(lat: number, lon: number, r = R): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta),
  );
}

function Globe() {
  const group = useRef<THREE.Group>(null);

  // Orient so Liguria faces the camera at rest.
  const centroid = useMemo(() => toVec3(44.2, 8.8), []);
  const markers = useMemo(() => PROVINCES.map((p) => ({ ...p, pos: toVec3(p.lat, p.lon) })), []);

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.15;
  });

  return (
    <group
      ref={group}
      // Rotate Liguria toward +Z (camera) on first paint.
      rotation={[0, -Math.atan2(centroid.x, centroid.z), 0]}
    >
      {/* Wireframe sphere */}
      <mesh>
        <sphereGeometry args={[R, 28, 28]} />
        <meshBasicMaterial color={NEON} wireframe transparent opacity={0.28} />
      </mesh>
      {/* Solid inner shell for depth */}
      <mesh scale={0.985}>
        <sphereGeometry args={[R, 32, 32]} />
        <meshBasicMaterial color="#001a0d" transparent opacity={0.6} />
      </mesh>
      {/* Province nodes + radial spikes */}
      {markers.map((m) => (
        <group key={m.name}>
          <mesh position={m.pos}>
            <sphereGeometry args={[0.06, 12, 12]} />
            <meshBasicMaterial color={CYAN} />
          </mesh>
          <line>
            <bufferGeometry
              attach="geometry"
              onUpdate={(g) =>
                g.setFromPoints([m.pos.clone().multiplyScalar(1.0), m.pos.clone().multiplyScalar(1.18)])
              }
            />
            <lineBasicMaterial attach="material" color={CYAN} transparent opacity={0.8} />
          </line>
        </group>
      ))}
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

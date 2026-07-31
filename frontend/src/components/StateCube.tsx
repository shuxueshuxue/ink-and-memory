import React, { useState, useRef, useEffect } from 'react';

interface State {
  id: string;
  cn: string;
  en: string;
  locked: boolean;
  isEmpty?: boolean;  // @@@ Mark empty grid positions (not displayed)
}

interface CubeFace {
  name: string;
  states: State[];
  unlocked: boolean;
  color: string;
}

// @@@ Quaternion class for smooth 3D rotation
class Quaternion {
  w: number;
  x: number;
  y: number;
  z: number;

  constructor(w: number, x: number, y: number, z: number) {
    this.w = w;
    this.x = x;
    this.y = y;
    this.z = z;
  }

  static identity(): Quaternion {
    return new Quaternion(1, 0, 0, 0);
  }

  static fromAxisAngle(axis: { x: number; y: number; z: number }, angle: number): Quaternion {
    const halfAngle = angle / 2;
    const s = Math.sin(halfAngle);
    return new Quaternion(
      Math.cos(halfAngle),
      axis.x * s,
      axis.y * s,
      axis.z * s
    );
  }

  multiply(q: Quaternion): Quaternion {
    return new Quaternion(
      this.w * q.w - this.x * q.x - this.y * q.y - this.z * q.z,
      this.w * q.x + this.x * q.w + this.y * q.z - this.z * q.y,
      this.w * q.y - this.x * q.z + this.y * q.w + this.z * q.x,
      this.w * q.z + this.x * q.y - this.y * q.x + this.z * q.w
    );
  }

  normalize(): Quaternion {
    const mag = Math.sqrt(this.w * this.w + this.x * this.x + this.y * this.y + this.z * this.z);
    return new Quaternion(this.w / mag, this.x / mag, this.y / mag, this.z / mag);
  }

  // @@@ Spherical linear interpolation for smooth animation
  slerp(target: Quaternion, t: number): Quaternion {
    let { w, x, y, z } = this;
    let { w: tw, x: tx, y: ty, z: tz } = target;

    // Compute dot product
    let dot = w * tw + x * tx + y * ty + z * tz;

    // If dot is negative, negate one quaternion to take shorter path
    if (dot < 0) {
      w = -w; x = -x; y = -y; z = -z;
      dot = -dot;
    }

    // If quaternions are very close, use linear interpolation
    if (dot > 0.9995) {
      const result = new Quaternion(
        w + t * (tw - w),
        x + t * (tx - x),
        y + t * (ty - y),
        z + t * (tz - z)
      );
      return result.normalize();
    }

    // Use slerp
    const theta = Math.acos(dot);
    const sinTheta = Math.sin(theta);
    const a = Math.sin((1 - t) * theta) / sinTheta;
    const b = Math.sin(t * theta) / sinTheta;

    return new Quaternion(
      w * a + tw * b,
      x * a + tx * b,
      y * a + ty * b,
      z * a + tz * b
    );
  }

  toRotationMatrix(): string {
    const { w, x, y, z } = this;

    const m00 = 1 - 2 * (y * y + z * z);
    const m01 = 2 * (x * y - w * z);
    const m02 = 2 * (x * z + w * y);

    const m10 = 2 * (x * y + w * z);
    const m11 = 1 - 2 * (x * x + z * z);
    const m12 = 2 * (y * z - w * x);

    const m20 = 2 * (x * z - w * y);
    const m21 = 2 * (y * z + w * x);
    const m22 = 1 - 2 * (x * x + y * y);

    return `matrix3d(${m00},${m10},${m20},0,${m01},${m11},${m21},0,${m02},${m12},${m22},0,0,0,0,1)`;
  }

  // @@@ Transform a vector by this quaternion's rotation
  transformVector(v: { x: number; y: number; z: number }): { x: number; y: number; z: number } {
    const { w, x, y, z } = this;
    const { x: vx, y: vy, z: vz } = v;

    // q * v * q^-1
    const ix = w * vx + y * vz - z * vy;
    const iy = w * vy + z * vx - x * vz;
    const iz = w * vz + x * vy - y * vx;
    const iw = -x * vx - y * vy - z * vz;

    return {
      x: ix * w + iw * -x + iy * -z - iz * -y,
      y: iy * w + iw * -y + iz * -x - ix * -z,
      z: iz * w + iw * -z + ix * -y - iy * -x
    };
  }
}

// @@@ Canonical orientations for each face (facing camera)
const FACE_ORIENTATIONS: Record<string, Quaternion> = {
  front: Quaternion.identity(),
  back: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, Math.PI),
  left: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, Math.PI / 2),
  right: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, -Math.PI / 2),
  top: Quaternion.fromAxisAngle({ x: 1, y: 0, z: 0 }, Math.PI / 2),  // Swapped
  bottom: Quaternion.fromAxisAngle({ x: 1, y: 0, z: 0 }, -Math.PI / 2)  // Swapped
};

interface StateCubeProps {
  onStateSelect?: (stateId: string) => void;
  stateConfig: { states: Record<string, { name: string; prompt: string }> };
}

export function StateCube({ onStateSelect, stateConfig }: StateCubeProps) {
  const [rotation, setRotation] = useState(() => FACE_ORIENTATIONS.front);
  const [isDragging, setIsDragging] = useState(false);
  const [isSnapping, setIsSnapping] = useState(false);
  const [clickedState, setClickedState] = useState<string | null>(null);
  const dragStartRef = useRef({ x: 0, y: 0, rotation: Quaternion.identity() });
  const snapAnimationRef = useRef<number | null>(null);

  // @@@ Get states from config (only first 3 for middle row)
  const configStates = Object.entries(stateConfig.states).slice(0, 3).map(([id, data]) => ({
    id,
    cn: data.name,
    en: '',
    locked: false
  }));

  // @@@ Create 9-item grid with states only in middle row (indices 3, 4, 5)
  const createGridStates = () => {
    const grid = Array(9).fill(null).map((_, i) => ({
      id: `empty-${i}`,
      cn: '',
      en: '',
      locked: false,
      isEmpty: true
    }));

    // Place actual states in middle row (indices 3, 4, 5)
    if (configStates.length > 0) {
      grid[3] = { ...configStates[0], isEmpty: false };
      if (configStates.length > 1) grid[4] = { ...configStates[1], isEmpty: false };
      if (configStates.length > 2) grid[5] = { ...configStates[2], isEmpty: false };
    } else {
      // Fallback defaults in middle row
      grid[3] = { id: 'happy', cn: 'Happy', en: '', locked: false, isEmpty: false };
      grid[4] = { id: 'ok', cn: 'OK', en: '', locked: false, isEmpty: false };
      grid[5] = { id: 'unhappy', cn: 'Unhappy', en: '', locked: false, isEmpty: false };
    }

    return grid;
  };

  // @@@ Define 6 faces with 9 states each
  const faces: CubeFace[] = [
    {
      name: 'front',
      unlocked: true,
      color: '#a3d5ff',
      states: createGridStates()
    },
    {
      name: 'back',
      unlocked: false,
      color: '#ffb3d9',
      states: Array(9).fill(null).map((_, i) => ({
        id: `back-${i}`,
        cn: '?',
        en: '',
        locked: true
      }))
    },
    {
      name: 'left',
      unlocked: false,
      color: '#b3ffb3',
      states: Array(9).fill(null).map((_, i) => ({
        id: `left-${i}`,
        cn: '?',
        en: '',
        locked: true
      }))
    },
    {
      name: 'right',
      unlocked: false,
      color: '#ffff43',
      states: Array(9).fill(null).map((_, i) => ({
        id: `right-${i}`,
        cn: '?',
        en: '',
        locked: true
      }))
    },
    {
      name: 'top',
      unlocked: false,
      color: '#ddb3ff',
      states: Array(9).fill(null).map((_, i) => ({
        id: `top-${i}`,
        cn: '?',
        en: '',
        locked: true
      }))
    },
    {
      name: 'bottom',
      unlocked: false,
      color: '#ffd4a3',
      states: Array(9).fill(null).map((_, i) => ({
        id: `bottom-${i}`,
        cn: '?',
        en: '',
        locked: true
      }))
    }
  ];

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      rotation: rotation
    };
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;

    const deltaX = e.clientX - dragStartRef.current.x;
    const deltaY = e.clientY - dragStartRef.current.y;

    // @@@ Convert screen-space drag to rotation axis and angle
    const sensitivity = 0.005;
    const angle = Math.sqrt(deltaX * deltaX + deltaY * deltaY) * sensitivity;

    if (angle > 0.0001) {
      // Rotation axis perpendicular to drag direction (in screen space)
      // deltaY → rotation around X axis, deltaX → rotation around Y axis
      const axis = {
        x: -deltaY,
        y: deltaX,
        z: 0
      };

      // Normalize axis
      const axisMag = Math.sqrt(axis.x * axis.x + axis.y * axis.y);
      if (axisMag > 0) {
        axis.x /= axisMag;
        axis.y /= axisMag;
      }

      // Create delta quaternion and multiply with start rotation
      const deltaQuat = Quaternion.fromAxisAngle(axis, angle);
      const newRotation = deltaQuat.multiply(dragStartRef.current.rotation).normalize();
      setRotation(newRotation);
    }
  };

  // @@@ Find the nearest canonical face orientation
  const findNearestFace = (currentRotation: Quaternion): { name: string; orientation: Quaternion } => {
    let maxDot = -Infinity;
    let nearestFace = 'front';
    let nearestOrientation = FACE_ORIENTATIONS.front;

    // Camera direction (looking at cube from user's perspective)
    const cameraDir = { x: 0, y: 0, z: 1 };

    // Face normals in their local space (each face points toward +Z in its local coords)
    const faceNormals: Record<string, { x: number; y: number; z: number }> = {
      front: { x: 0, y: 0, z: 1 },
      back: { x: 0, y: 0, z: -1 },
      left: { x: -1, y: 0, z: 0 },
      right: { x: 1, y: 0, z: 0 },
      top: { x: 0, y: 1, z: 0 },
      bottom: { x: 0, y: -1, z: 0 }
    };

    for (const [faceName, faceOrientation] of Object.entries(FACE_ORIENTATIONS)) {
      // Get which direction this face is pointing in current rotation
      const localNormal = faceNormals[faceName];
      const worldNormal = currentRotation.transformVector(localNormal);

      // Dot product: how much does this face point toward camera?
      const dot = worldNormal.x * cameraDir.x +
                  worldNormal.y * cameraDir.y +
                  worldNormal.z * cameraDir.z;

      if (dot > maxDot) {
        maxDot = dot;
        nearestFace = faceName;
        nearestOrientation = faceOrientation;
      }
    }

    return { name: nearestFace, orientation: nearestOrientation };
  };

  // @@@ Animate snap to target orientation
  const snapToFace = (targetOrientation: Quaternion) => {
    if (snapAnimationRef.current !== null) {
      cancelAnimationFrame(snapAnimationRef.current);
    }

    const startRotation = rotation;
    const startTime = performance.now();
    const duration = 500; // ms

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const t = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);

      const interpolated = startRotation.slerp(targetOrientation, eased);
      setRotation(interpolated);

      if (t < 1) {
        snapAnimationRef.current = requestAnimationFrame(animate);
      } else {
        setIsSnapping(false);
        snapAnimationRef.current = null;
      }
    };

    setIsSnapping(true);
    snapAnimationRef.current = requestAnimationFrame(animate);
  };

  const handleMouseUp = () => {
    setIsDragging(false);

    // @@@ Snap to nearest face
    const { orientation } = findNearestFace(rotation);
    snapToFace(orientation);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, rotation]);

  // @@@ Cleanup animation on unmount
  useEffect(() => {
    return () => {
      if (snapAnimationRef.current !== null) {
        cancelAnimationFrame(snapAnimationRef.current);
      }
    };
  }, []);

  // @@@ Idle animation: slowly rotate cube after 3 seconds of inactivity
  useEffect(() => {
    if (isDragging || isSnapping) return;

    let idleTimeoutId: number;
    let idleAnimationId: number;
    const baseRotation = rotation; // Capture current rotation when idle starts

    // Wait 3 seconds before starting idle animation
    idleTimeoutId = window.setTimeout(() => {
      const startTime = performance.now();
      const idleRotationSpeed = 0.0002; // Very slow rotation

      const animateIdle = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const angle = elapsed * idleRotationSpeed;

        // Rotate slowly around Y axis (left-right)
        const idleRotation = Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, angle);
        const newRotation = idleRotation.multiply(baseRotation);

        setRotation(newRotation);
        idleAnimationId = requestAnimationFrame(animateIdle);
      };

      idleAnimationId = requestAnimationFrame(animateIdle);
    }, 3000);

    return () => {
      if (idleTimeoutId) {
        clearTimeout(idleTimeoutId);
      }
      if (idleAnimationId) {
        cancelAnimationFrame(idleAnimationId);
      }
    };
  }, [isDragging, isSnapping]);

  // @@@ Simple SVG icon generator for each state
  const getStateIcon = (stateId: string) => {
    const iconProps = { width: 40, height: 40, viewBox: "0 0 100 100", style: { margin: '0 auto' } };

    switch(stateId.toLowerCase()) {
      case 'happy':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#FFD93D" strokeWidth="6"/>
            <path d="M 35 60 Q 50 75 65 60" fill="none" stroke="#FFD93D" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#FFD93D"/>
            <circle cx="62" cy="40" r="4" fill="#FFD93D"/>
          </svg>
        );
      case 'ok':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#95D5B2" strokeWidth="6"/>
            <line x1="35" y1="60" x2="65" y2="60" stroke="#95D5B2" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#95D5B2"/>
            <circle cx="62" cy="40" r="4" fill="#95D5B2"/>
          </svg>
        );
      case 'unhappy':
        return (
          <svg {...iconProps}>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#A8DADC" strokeWidth="6"/>
            <path d="M 35 65 Q 50 50 65 65" fill="none" stroke="#A8DADC" strokeWidth="6" strokeLinecap="round"/>
            <circle cx="38" cy="40" r="4" fill="#A8DADC"/>
            <circle cx="62" cy="40" r="4" fill="#A8DADC"/>
          </svg>
        );
      default:
        return (
          <svg {...iconProps} style={{ ...iconProps.style, color: 'var(--color-text-muted)' }}>
            <circle cx="50" cy="50" r="35" fill="none" stroke="currentColor" strokeWidth="4"/>
          </svg>
        );
    }
  };

  const renderFace = (face: CubeFace, transform: string) => {
    return (
      <div
        style={{
          position: 'absolute',
          width: '300px',
          height: '300px',
          transform,
          backfaceVisibility: 'hidden',
          background: face.unlocked
            ? `linear-gradient(135deg, ${face.color}40, ${face.color}80)`
            : 'linear-gradient(135deg, var(--color-bg-surface) 0%, var(--color-bg-paper) 100%)',
          opacity: face.unlocked ? 1 : 0.6,
          border: '2px solid var(--color-border-paper)',
          borderRadius: '8px',
          padding: '10px',
          boxSizing: 'border-box',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gridTemplateRows: 'repeat(3, 1fr)',
          gap: '8px'
        }}
      >
        {face.states.map((state) => {
          const isClicked = clickedState === state.id;
          return (
            <div
              key={state.id}
              onClick={() => {
                if (!state.locked && !state.isEmpty && onStateSelect) {
                  setClickedState(state.id);
                  setTimeout(() => {
                    onStateSelect(state.id);
                    setClickedState(null);
                  }, 200);
                }
              }}
              style={{
                background: state.isEmpty
                  ? 'transparent'
                  : isClicked
                    ? 'var(--color-bg-active)'
                    : 'var(--color-bg-surface)',
                borderRadius: '4px',
                padding: '8px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '11px',
                fontFamily: "'Excalifont', 'Xiaolai', sans-serif",
                cursor: state.isEmpty || state.locked ? 'default' : 'pointer',
                transition: 'all 0.2s ease',
                userSelect: 'none',
                transform: isClicked ? 'scale(0.95)' : 'scale(1)',
                boxShadow: isClicked ? '0 0 12px var(--color-bg-active-hover)' : 'none',
                pointerEvents: face.unlocked && !state.isEmpty ? 'auto' : 'none'
              }}
              onMouseEnter={(e) => {
                if (face.unlocked && !isClicked && !state.isEmpty) {
                  e.currentTarget.style.transform = 'scale(1.05)';
                  e.currentTarget.style.background = 'var(--color-bg-surface-solid)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isClicked && !state.isEmpty) {
                  e.currentTarget.style.transform = 'scale(1)';
                  e.currentTarget.style.background = 'var(--color-bg-surface)';
                }
              }}
            >
              {!face.unlocked || state.isEmpty ? null : (
                <>
                  {getStateIcon(state.id)}
                  <div style={{ marginTop: '4px', fontWeight: 500, color: 'var(--color-text-body)' }}>
                    {state.cn}
                  </div>
                </>
              )}
            </div>
          );
        })}

        {/* @@@ Single semi-transparent lock overlay for locked faces */}
        {!face.unlocked && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'color-mix(in srgb, var(--color-border-paper) 40%, transparent)',
            borderRadius: '8px',
            pointerEvents: 'none'
          }}>
            <svg width="80" height="80" viewBox="0 0 100 100" style={{ opacity: 0.6 }}>
              <rect x="30" y="45" width="40" height="35" rx="4" fill="none" stroke="var(--color-text-secondary)" strokeWidth="6"/>
              <path d="M 35 45 V 35 Q 35 20 50 20 Q 65 20 65 35 V 45" fill="none" stroke="var(--color-text-secondary)" strokeWidth="6" strokeLinecap="round"/>
              <circle cx="50" cy="62" r="4" fill="var(--color-text-secondary)"/>
            </svg>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        perspective: '1200px',
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '16px'
      }}
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          width: '300px',
          height: '300px',
          position: 'relative',
          transformStyle: 'preserve-3d',
          transform: rotation.toRotationMatrix(),
          transition: (isDragging || isSnapping) ? 'none' : 'transform 0.3s ease-out'
        }}
      >
        {/* Front face */}
        {renderFace(faces[0], 'translateZ(150px)')}

        {/* Back face */}
        {renderFace(faces[1], 'translateZ(-150px) rotateY(180deg)')}

        {/* Left face */}
        {renderFace(faces[2], 'rotateY(-90deg) translateZ(150px)')}

        {/* Right face */}
        {renderFace(faces[3], 'rotateY(90deg) translateZ(150px)')}

        {/* Top face */}
        {renderFace(faces[4], 'rotateX(90deg) translateZ(150px)')}

        {/* Bottom face */}
        {renderFace(faces[5], 'rotateX(-90deg) translateZ(150px)')}
      </div>
    </div>
  );
}

import { useState, useRef, useCallback, useEffect } from "react";

/*
 * Lava Lamp Simulator
 *
 * Physics: Blobs exist in a 3D cylindrical container. A heat source at
 * the bottom warms nearby wax, reducing its density so it rises via
 * buoyancy. At the top, wax cools, becomes denser, and sinks. Simple
 * viscous drag and inter-blob repulsion keep things organic.
 *
 * Rendering: 2D metaball field evaluation. For each pixel we compute
 * Σ(rᵢ² / dᵢ²) across all blobs (using projected 2D positions with
 * depth-adjusted radii). Where the field exceeds a threshold, we draw
 * "wax" with temperature-based coloring and fake 3D lighting.
 *
 * Runs at reduced resolution and upscales for smooth 60fps with 6 blobs.
 */

// ─── Blob physics ───
class Blob {
  constructor(x, y, z, radius) {
    this.x = x;       // -1 to 1 (horizontal)
    this.y = y;       // 0 to 1 (bottom to top)
    this.z = z;       // -1 to 1 (depth)
    this.vx = 0;
    this.vy = 0;
    this.vz = 0;
    this.radius = radius;
    this.baseRadius = radius;
    this.temperature = 0.0; // 0=cold, 1=hot — start cold
    this.mass = radius * radius * radius;
  }
}

function createBlobs(count) {
  const blobs = [];
  // All blobs start pooled at the bottom, like cold wax sitting on
  // the base before the lamp is switched on
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2;
    const spreadR = 0.12 + Math.random() * 0.1;
    blobs.push(new Blob(
      Math.cos(angle) * spreadR + (Math.random() - 0.5) * 0.06,
      0.04 + Math.random() * 0.08,   // near the bottom
      Math.sin(angle) * spreadR + (Math.random() - 0.5) * 0.06,
      0.09 + Math.random() * 0.07
    ));
  }
  // Large pool blob sitting right on the base
  blobs.push(new Blob(0, 0.04, 0, 0.20));
  return blobs;
}

function updatePhysics(blobs, dt, heatStrength, flowSpeed, warmupFactor) {
  // warmupFactor: 0→1 over ~20s, simulates the bulb warming up
  const effectiveHeat = heatStrength * warmupFactor;
  const gravity = -0.35 * flowSpeed;
  const buoyancyScale = 0.9 * flowSpeed;
  const drag = 3.5;
  const wallRadius = 0.42;
  const heatZone = 0.25;
  const coolZone = 0.75;
  // Wax needs to reach a "melting" temperature before it becomes buoyant
  // During early warmup the blobs just sit and glow
  const meltThreshold = 0.35;

  for (const b of blobs) {
    // Heat transfer — only effective once lamp is warming up
    if (b.y < heatZone && effectiveHeat > 0.01) {
      const proximity = 1 - b.y / heatZone;
      const heatRate = proximity * 1.8 * effectiveHeat;
      b.temperature = Math.min(1, b.temperature + heatRate * dt);
    }
    if (b.y > coolZone) {
      const coolRate = ((b.y - coolZone) / (1 - coolZone)) * 1.2;
      b.temperature = Math.max(0, b.temperature - coolRate * dt);
    }
    // Ambient cooling everywhere
    b.temperature = Math.max(0, b.temperature - 0.05 * dt);

    // Temperature affects radius (hot wax expands)
    b.radius = b.baseRadius * (1 + b.temperature * 0.25);

    // Buoyancy: only kicks in once wax is above melt threshold
    // Below threshold, wax is solid/dense and just sits at the bottom
    let buoyancy;
    if (b.temperature > meltThreshold) {
      const meltedFraction = (b.temperature - meltThreshold) / (1 - meltThreshold);
      buoyancy = meltedFraction * buoyancyScale;
    } else {
      buoyancy = -0.1; // extra weight when cold — sinks firmly
    }
    const fy = gravity + buoyancy;

    // Viscous drag
    b.vx += -drag * b.vx * dt;
    b.vy += (fy - drag * b.vy) * dt;
    b.vz += -drag * b.vz * dt;

    // Gentle random drift
    b.vx += (Math.random() - 0.5) * 0.02 * dt;
    b.vz += (Math.random() - 0.5) * 0.02 * dt;

    // Update position
    b.x += b.vx * dt;
    b.y += b.vy * dt;
    b.z += b.vz * dt;

    // Cylindrical wall constraint
    const hr = Math.sqrt(b.x * b.x + b.z * b.z);
    const maxR = wallRadius - b.radius * 0.5;
    if (hr > maxR && hr > 0.001) {
      const nx = b.x / hr;
      const nz = b.z / hr;
      b.x = nx * maxR;
      b.z = nz * maxR;
      // Reflect velocity
      const vn = b.vx * nx + b.vz * nz;
      if (vn > 0) {
        b.vx -= 1.5 * vn * nx;
        b.vz -= 1.5 * vn * nz;
      }
    }

    // Floor and ceiling
    const minY = b.radius * 0.4;
    const maxY = 1 - b.radius * 0.4;
    if (b.y < minY) { b.y = minY; b.vy = Math.abs(b.vy) * 0.3; }
    if (b.y > maxY) { b.y = maxY; b.vy = -Math.abs(b.vy) * 0.3; }
  }

  // Inter-blob soft repulsion
  for (let i = 0; i < blobs.length; i++) {
    for (let j = i + 1; j < blobs.length; j++) {
      const a = blobs[i], b = blobs[j];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dz = b.z - a.z;
      const dist = Math.sqrt(dx*dx + dy*dy + dz*dz) || 0.001;
      const minDist = (a.radius + b.radius) * 0.6;
      if (dist < minDist) {
        const force = (minDist - dist) * 0.5;
        const nx = dx / dist, ny = dy / dist, nz = dz / dist;
        const massRatio = a.mass / (a.mass + b.mass);
        a.vx -= nx * force * (1 - massRatio);
        a.vy -= ny * force * (1 - massRatio);
        a.vz -= nz * force * (1 - massRatio);
        b.vx += nx * force * massRatio;
        b.vy += ny * force * massRatio;
        b.vz += nz * force * massRatio;
      }
    }
  }
}

// ─── Color helpers ───
function tempToColor(t, field) {
  // Warm wax: deep red → orange → bright yellow
  const r = Math.min(255, 140 + t * 115);
  const g = Math.min(255, 20 + t * 120);
  const b_ = Math.min(255, 5 + t * 30);
  // Brighten at high field values (center of blob)
  const bright = Math.min(1.0, (field - 1.0) * 0.6);
  return [
    Math.min(255, r + bright * 60) | 0,
    Math.min(255, g + bright * 80) | 0,
    Math.min(255, b_ + bright * 20) | 0,
  ];
}

// ─── Lamp geometry ───
function getLampRadius(y01) {
  // Tapered cylinder shape: slightly wider in middle
  const bulge = 1.0 + 0.06 * Math.sin(y01 * Math.PI);
  // Taper at top and bottom caps
  let taper = 1.0;
  if (y01 < 0.05) taper = y01 / 0.05;
  if (y01 > 0.95) taper = (1 - y01) / 0.05;
  return 0.46 * bulge * Math.max(taper, 0.3);
}

// ─── Main Component ───
export default function LavaLamp() {
  const canvasRef = useRef(null);
  const blobsRef = useRef(null);
  const frameRef = useRef(null);
  const lastTimeRef = useRef(0);

  const [blobCount, setBlobCount] = useState(6);
  const [heatStrength, setHeatStrength] = useState(1.0);
  const [flowSpeed, setFlowSpeed] = useState(1.0);
  const [colorScheme, setColorScheme] = useState("classic");
  const [showHelp, setShowHelp] = useState(false);
  const [paused, setPaused] = useState(false);
  const [warmupPct, setWarmupPct] = useState(0);
  const pausedRef = useRef(false);
  const warmupTimeRef = useRef(0);     // seconds since lamp "switched on"
  const WARMUP_DURATION = 18;          // seconds for full warmup

  const RENDER_SCALE = 0.35; // render at 35% res for speed
  const LAMP_W = 220;
  const LAMP_H = 520;
  const CANVAS_W = LAMP_W;
  const CANVAS_H = LAMP_H;

  // Color schemes
  const schemes = {
    classic: { name: "Classic Red", base: [180, 30, 10], hot: [255, 180, 40], bg: [20, 8, 5], liquid: [45, 15, 8] },
    blue: { name: "Cosmic Blue", base: [20, 40, 180], hot: [80, 180, 255], bg: [5, 8, 25], liquid: [8, 12, 45] },
    green: { name: "Acid Green", base: [30, 160, 20], hot: [180, 255, 60], bg: [5, 20, 5], liquid: [8, 35, 10] },
    purple: { name: "Nebula", base: [120, 20, 160], hot: [220, 100, 255], bg: [15, 5, 20], liquid: [30, 10, 40] },
    gold: { name: "Molten Gold", base: [180, 120, 10], hot: [255, 220, 80], bg: [20, 14, 5], liquid: [40, 28, 8] },
  };

  const getWaxColor = useCallback((t, field, scheme) => {
    const s = schemes[scheme] || schemes.classic;
    const r = s.base[0] + (s.hot[0] - s.base[0]) * t;
    const g = s.base[1] + (s.hot[1] - s.base[1]) * t;
    const b = s.base[2] + (s.hot[2] - s.base[2]) * t;
    const bright = Math.min(1.0, Math.max(0, (field - 1.0) * 0.5));
    return [
      Math.min(255, r + bright * 50) | 0,
      Math.min(255, g + bright * 60) | 0,
      Math.min(255, b + bright * 30) | 0,
    ];
  }, []);

  // Initialize blobs
  useEffect(() => {
    blobsRef.current = createBlobs(blobCount);
    warmupTimeRef.current = 0;
    setWarmupPct(0);
  }, [blobCount]);

  // Main render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Offscreen buffer at reduced resolution
    const rw = Math.floor(CANVAS_W * RENDER_SCALE);
    const rh = Math.floor(CANVAS_H * RENDER_SCALE);
    const offscreen = document.createElement("canvas");
    offscreen.width = rw;
    offscreen.height = rh;
    const offCtx = offscreen.getContext("2d");

    const loop = (timestamp) => {
      frameRef.current = requestAnimationFrame(loop);

      const dt = Math.min((timestamp - (lastTimeRef.current || timestamp)) / 1000, 0.05);
      lastTimeRef.current = timestamp;

      const blobs = blobsRef.current;
      if (!blobs) return;

      // Physics
      if (!pausedRef.current) {
        // Advance warmup — lamp gradually heats up after being "switched on"
        warmupTimeRef.current += dt;
        const warmupFactor = Math.min(1.0, warmupTimeRef.current / WARMUP_DURATION);
        // Ease-in curve: slow start then accelerates (like a bulb warming up)
        const easedWarmup = warmupFactor * warmupFactor * (3 - 2 * warmupFactor);
        updatePhysics(blobs, dt, heatStrength, flowSpeed, easedWarmup);
        // Update display (throttled to avoid too many re-renders)
        const pct = Math.round(warmupFactor * 100);
        if (pct % 5 === 0 || pct >= 100) setWarmupPct(pct);
      }

      // Get current scheme
      const s = schemes[colorScheme] || schemes.classic;

      // Render metaballs at low res
      const imgData = offCtx.createImageData(rw, rh);
      const data = imgData.data;
      const threshold = 1.0;

      for (let py = 0; py < rh; py++) {
        const y01 = py / rh; // 0=top, 1=bottom
        const blobY = 1 - y01; // flip: 0=bottom, 1=top in blob space
        const lampR = getLampRadius(1 - y01);

        for (let px = 0; px < rw; px++) {
          const x01 = (px / rw - 0.5) * 2; // -1 to 1
          const idx = (py * rw + px) * 4;

          // Outside lamp?
          if (Math.abs(x01) > lampR * 2.1) {
            data[idx] = 0; data[idx+1] = 0; data[idx+2] = 0; data[idx+3] = 0;
            continue;
          }

          // Compute metaball field
          let field = 0;
          let weightedTemp = 0;
          let totalWeight = 0;

          for (const b of blobs) {
            // Project 3D → 2D: x maps directly, z affects apparent radius
            const projX = b.x * 2; // scale to -1..1 range
            const projY = b.y;
            const depthFactor = 1.0 / (1.0 + b.z * 0.3); // subtle depth scaling
            const projR = b.radius * depthFactor * 2.5;

            const dx = x01 - projX;
            const dy = blobY - projY;
            const dist2 = dx * dx + dy * dy;
            const r2 = projR * projR;

            if (dist2 < r2 * 9) { // skip far blobs
              const contribution = r2 / (dist2 + 0.001);
              field += contribution;
              weightedTemp += b.temperature * contribution;
              totalWeight += contribution;
            }
          }

          if (field > threshold && Math.abs(x01) < lampR * 2) {
            // Inside wax
            const temp = totalWeight > 0 ? weightedTemp / totalWeight : 0.3;
            const [cr, cg, cb] = getWaxColor(temp, field, colorScheme);

            // Fake 3D: darken at edges
            const edgeDist = Math.abs(x01) / (lampR * 2);
            const shade = 1.0 - edgeDist * edgeDist * 0.4;

            // Highlight on the left side (fake specular)
            const spec = Math.max(0, 1 - Math.abs(x01 + lampR * 0.6) / (lampR * 0.8));
            const specPow = spec * spec * spec * 0.3;

            data[idx] = Math.min(255, cr * shade + specPow * 200) | 0;
            data[idx+1] = Math.min(255, cg * shade + specPow * 150) | 0;
            data[idx+2] = Math.min(255, cb * shade + specPow * 80) | 0;
            data[idx+3] = 255;
          } else if (Math.abs(x01) < lampR * 2) {
            // Inside lamp but not wax — liquid background
            const edgeDist = Math.abs(x01) / (lampR * 2);
            const shade = 1.0 - edgeDist * edgeDist * 0.5;

            // Subtle glow near wax
            const glow = Math.min(1, field * 0.3) * 0.4;

            data[idx] = Math.min(255, (s.liquid[0] + glow * s.base[0] * 0.3) * shade) | 0;
            data[idx+1] = Math.min(255, (s.liquid[1] + glow * s.base[1] * 0.3) * shade) | 0;
            data[idx+2] = Math.min(255, (s.liquid[2] + glow * s.base[2] * 0.3) * shade) | 0;
            data[idx+3] = 255;
          } else {
            data[idx+3] = 0;
          }
        }
      }

      offCtx.putImageData(imgData, 0, 0);

      // Draw to main canvas with upscaling
      ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(offscreen, 0, 0, CANVAS_W, CANVAS_H);

      // Draw glass overlay
      const warmupGlow = Math.min(1, warmupTimeRef.current / WARMUP_DURATION);
      drawGlassOverlay(ctx, CANVAS_W, CANVAS_H, s, warmupGlow);
    };

    frameRef.current = requestAnimationFrame(loop);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [heatStrength, flowSpeed, colorScheme, getWaxColor]);

  // Sync paused ref
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  function drawGlassOverlay(ctx, w, h, s, warmupGlow) {
    // Glass cylinder highlight (left edge)
    const hlGrad = ctx.createLinearGradient(w * 0.15, 0, w * 0.45, 0);
    hlGrad.addColorStop(0, "rgba(255,255,255,0)");
    hlGrad.addColorStop(0.3, "rgba(255,255,255,0.06)");
    hlGrad.addColorStop(0.5, "rgba(255,255,255,0.02)");
    hlGrad.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = hlGrad;
    ctx.fillRect(0, h * 0.03, w, h * 0.94);

    // Top cap
    const capGrad = ctx.createLinearGradient(0, 0, 0, h * 0.04);
    capGrad.addColorStop(0, "#3a3530");
    capGrad.addColorStop(1, "#2a2520");
    ctx.fillStyle = capGrad;
    ctx.beginPath();
    ctx.ellipse(w / 2, h * 0.015, w * 0.38, h * 0.015, 0, 0, Math.PI * 2);
    ctx.fill();

    // Bottom cap / base
    const baseGrad = ctx.createLinearGradient(0, h * 0.96, 0, h);
    baseGrad.addColorStop(0, "#2a2520");
    baseGrad.addColorStop(1, "#1a1510");
    ctx.fillStyle = baseGrad;
    ctx.beginPath();
    ctx.ellipse(w / 2, h * 0.985, w * 0.42, h * 0.018, 0, 0, Math.PI * 2);
    ctx.fill();

    // Glow at bottom (heat source) — intensity follows warmup
    const glowAlpha = 0.03 + warmupGlow * 0.18;
    const glowGrad = ctx.createRadialGradient(w/2, h * 0.97, 0, w/2, h * 0.97, w * 0.4);
    glowGrad.addColorStop(0, `rgba(${s.base[0]},${s.base[1]},${s.base[2]},${glowAlpha.toFixed(2)})`);
    glowGrad.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = glowGrad;
    ctx.fillRect(0, h * 0.85, w, h * 0.15);
  }

  const sliderStyle = { width: "100%", accentColor: "#c47830" };
  const labelStyle = {
    display: "flex", justifyContent: "space-between",
    fontSize: 11, color: "#b8a890", marginBottom: 2,
    fontFamily: "'Georgia', serif",
  };
  const btnStyle = (active) => ({
    padding: "6px 11px", fontSize: 11, border: "1px solid #4a4035",
    borderRadius: 5, cursor: "pointer",
    fontFamily: "'Georgia', serif",
    background: active ? "#5a4a35" : "#2a2218",
    color: active ? "#f0d8b0" : "#a09080",
    transition: "all 0.2s",
  });

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(170deg, #0a0806 0%, #1a1410 40%, #0d0a08 100%)",
      display: "flex", flexDirection: "column", alignItems: "center",
      padding: "20px 12px",
      fontFamily: "'Georgia', serif", color: "#c8b8a0",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <h1 style={{
          fontSize: 24, fontWeight: 300, letterSpacing: 5, margin: 0,
          background: "linear-gradient(90deg, #e8a040, #f0c870, #e8a040)",
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
        }}>
          LAVA LAMP
        </h1>
        <div style={{ fontSize: 10, letterSpacing: 3, color: "#6a5a48", marginTop: 2 }}>
          METABALL FLUID SIMULATION
        </div>
      </div>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", justifyContent: "center" }}>
        {/* Lamp */}
        <div style={{
          position: "relative",
          filter: `drop-shadow(0 0 30px rgba(${(schemes[colorScheme]||schemes.classic).base.join(",")},0.2))`,
        }}>
          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            style={{
              width: CANVAS_W, height: CANVAS_H,
              borderRadius: "50% / 3%",
              display: "block",
            }}
          />
          {/* Ambient glow beneath */}
          <div style={{
            position: "absolute", bottom: -20, left: "10%", width: "80%", height: 40,
            background: `radial-gradient(ellipse, rgba(${(schemes[colorScheme]||schemes.classic).base.join(",")},0.25) 0%, transparent 70%)`,
            borderRadius: "50%", filter: "blur(8px)", pointerEvents: "none",
          }} />
        </div>

        {/* Controls */}
        <div style={{ width: 220, display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Color scheme */}
          <div>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 2, color: "#6a5a48", marginBottom: 6 }}>
              Color
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {Object.entries(schemes).map(([key, s]) => (
                <button key={key} onClick={() => setColorScheme(key)} style={{
                  ...btnStyle(colorScheme === key),
                  display: "flex", alignItems: "center", gap: 4,
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: "50%", display: "inline-block",
                    background: `rgb(${s.base[0]},${s.base[1]},${s.base[2]})`,
                    boxShadow: `0 0 4px rgba(${s.hot[0]},${s.hot[1]},${s.hot[2]},0.5)`,
                  }} />
                  {s.name}
                </button>
              ))}
            </div>
          </div>

          {/* Heat */}
          <div>
            <div style={labelStyle}><span>Heat</span><span>{(heatStrength * 100).toFixed(0)}%</span></div>
            <input type="range" min={20} max={200} value={heatStrength * 100}
              onChange={e => setHeatStrength(Number(e.target.value) / 100)} style={sliderStyle} />
          </div>

          {/* Flow speed */}
          <div>
            <div style={labelStyle}><span>Flow Speed</span><span>{(flowSpeed * 100).toFixed(0)}%</span></div>
            <input type="range" min={20} max={200} value={flowSpeed * 100}
              onChange={e => setFlowSpeed(Number(e.target.value) / 100)} style={sliderStyle} />
          </div>

          {/* Blob count */}
          <div>
            <div style={labelStyle}><span>Wax Blobs</span><span>{blobCount}</span></div>
            <input type="range" min={3} max={10} value={blobCount}
              onChange={e => setBlobCount(Number(e.target.value))} style={sliderStyle} />
          </div>

          {/* Warmup status */}
          <div style={{
            padding: "8px 10px", borderRadius: 6,
            background: warmupPct < 100 ? "#1a1510" : "#15201a",
            border: `1px solid ${warmupPct < 100 ? "#3a3025" : "#2a4030"}`,
            transition: "all 0.5s",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
              <span style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 2, color: "#6a5a48" }}>
                {warmupPct < 100 ? "Warming Up…" : "Lamp Ready"}
              </span>
              <span style={{ fontSize: 11, color: warmupPct < 100 ? "#c47830" : "#60a060" }}>
                {warmupPct}%
              </span>
            </div>
            <div style={{
              height: 3, borderRadius: 2,
              background: "#2a2218",
              overflow: "hidden",
            }}>
              <div style={{
                height: "100%", borderRadius: 2,
                width: `${warmupPct}%`,
                background: warmupPct < 100
                  ? `linear-gradient(90deg, #6a3a10, #c47830)`
                  : "#60a060",
                transition: "width 0.3s, background 0.5s",
              }} />
            </div>
          </div>

          {/* Pause / Reset */}
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => setPaused(!paused)} style={btnStyle(paused)}>
              {paused ? "▶ Play" : "⏸ Pause"}
            </button>
            <button onClick={() => { blobsRef.current = createBlobs(blobCount); warmupTimeRef.current = 0; setWarmupPct(0); }} style={btnStyle(false)}>
              ↻ Reset
            </button>
          </div>

          {/* Help */}
          <button onClick={() => setShowHelp(!showHelp)} style={btnStyle(false)}>
            {showHelp ? "Hide Info" : "? Info"}
          </button>

          {showHelp && (
            <div style={{
              fontSize: 11, lineHeight: 1.6, color: "#9a8a78",
              background: "#1a1510", padding: 12, borderRadius: 6,
              border: "1px solid #3a3025",
            }}>
              <strong style={{ color: "#c8a870" }}>Physics</strong><br/>
              Wax blobs are heated from below, reducing their density
              so they rise via buoyancy. At the top they cool, become
              denser, and sink back down.<br/><br/>
              <strong style={{ color: "#c8a870" }}>Rendering</strong><br/>
              Uses metaball field evaluation — for each pixel, the
              contribution from all blobs is summed as Σ(r²/d²). Where
              the field exceeds a threshold, wax is drawn with
              temperature-based coloring and fake 3D lighting.<br/><br/>
              <strong style={{ color: "#c8a870" }}>Inter-blob forces</strong><br/>
              Soft repulsion prevents blobs from fully overlapping,
              while the metaball rendering creates the visual merging
              and splitting characteristic of real lava lamps.
            </div>
          )}

          {/* Attribution */}
          <div style={{ fontSize: 9, color: "#4a4035", lineHeight: 1.4, marginTop: 8 }}>
            Simulation uses buoyancy-driven convection with viscous
            drag in a cylindrical container. Metaball rendering at
            {((RENDER_SCALE * 100) | 0)}% resolution, upscaled with
            bilinear filtering.
          </div>
        </div>
      </div>
    </div>
  );
}

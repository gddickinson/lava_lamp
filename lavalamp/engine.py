"""
Lava lamp physics engine.

Manages blob state and runs the thermodynamic / buoyancy simulation.
All state is in simple arrays for easy numpy vectorisation in the renderer.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blob
# ---------------------------------------------------------------------------

@dataclass
class Blob:
    """A single wax blob in 3-D space."""
    x: float = 0.0          # -1..1 horizontal
    y: float = 0.0          # 0..1 (bottom→top)
    z: float = 0.0          # -1..1 depth
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    warm_radius: float = 0.12
    cold_radius: float = 0.0   # set in __post_init__
    radius: float = 0.0
    base_radius: float = 0.12
    temperature: float = 0.0   # 0=cold, 1=hot
    mass: float = 0.0
    detached: bool = False

    def __post_init__(self):
        self.cold_radius = self.warm_radius * 0.35
        self.radius = self.cold_radius
        self.base_radius = self.warm_radius
        self.mass = self.warm_radius ** 3


# ---------------------------------------------------------------------------
# Physics parameters (user-tunable)
# ---------------------------------------------------------------------------

@dataclass
class PhysicsParams:
    """All tuneable physics constants.

    Attributes are grouped by category and have sensible defaults
    matching the tested React version.
    """
    # Forces
    gravity: float = 0.18
    buoyancy_max: float = 0.65
    h_drag: float = 2.5
    v_drag: float = 1.6

    # Thermal
    heat_strength: float = 1.0
    heat_zone: float = 0.30     # bottom fraction where heating occurs
    cool_zone: float = 0.65     # above this fraction, cooling occurs
    melt_temp: float = 0.28     # temperature needed for buoyancy
    mid_cool_rate: float = 0.08 # ambient cooling in mid-zone
    top_cool_rate: float = 2.5  # cooling rate at the top

    # Blob interaction
    repulsion_strength: float = 1.5
    thermal_separation: float = 0.6

    # Geometry
    wall_radius: float = 0.42

    # Warmup
    warmup_duration: float = 18.0  # seconds

    # Expansion
    cold_radius_fraction: float = 0.35  # fraction of warm radius when cold

    # Speed
    flow_speed: float = 1.0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class LavaLampEngine:
    """Manages blob creation, physics stepping, and warmup state.

    Parameters:
        blob_count: Number of wax blobs (plus one large pool blob).
        params:     Physics parameters (or defaults).
        seed:       RNG seed for reproducibility (None = random).
    """

    def __init__(
        self,
        blob_count: int = 6,
        params: Optional[PhysicsParams] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.params = params or PhysicsParams()
        self.rng = np.random.default_rng(seed)
        self.warmup_time: float = 0.0
        self.blobs: List[Blob] = []
        self.reset(blob_count)

    # ── blob management ───────────────────────────────────────────────────

    def reset(self, blob_count: Optional[int] = None) -> None:
        """Reset all blobs to cold compact state at the bottom."""
        if blob_count is not None:
            self._blob_count = blob_count
        self.warmup_time = 0.0
        self.blobs = self._create_blobs(self._blob_count)
        logger.info("Engine reset: %d blobs (+1 pool)", self._blob_count)

    def _create_blobs(self, count: int) -> List[Blob]:
        blobs: List[Blob] = []
        frac = self.params.cold_radius_fraction
        for i in range(count):
            angle = (i / max(count, 1)) * math.pi * 2 + self.rng.uniform(-0.25, 0.25)
            spread = 0.04 + self.rng.uniform(0, 0.05)
            r = 0.10 + self.rng.uniform(0, 0.06)
            b = Blob(
                x=math.cos(angle) * spread,
                y=0.02 + self.rng.uniform(0, 0.03),
                z=math.sin(angle) * spread,
                warm_radius=r,
            )
            b.cold_radius = r * frac
            b.radius = b.cold_radius
            blobs.append(b)
        # Large pool blob
        pool = Blob(x=0.0, y=0.02, z=0.0, warm_radius=0.19)
        pool.cold_radius = 0.19 * frac
        pool.radius = pool.cold_radius
        blobs.append(pool)
        return blobs

    @property
    def blob_count(self) -> int:
        return self._blob_count

    @property
    def warmup_fraction(self) -> float:
        """0→1 warmup progress."""
        if self.params.warmup_duration <= 0:
            return 1.0
        return min(1.0, self.warmup_time / self.params.warmup_duration)

    # ── physics step ──────────────────────────────────────────────────────

    def step(self, dt: float) -> None:
        """Advance simulation by *dt* seconds."""
        dt = min(dt, 0.05)  # clamp large steps
        self.warmup_time += dt

        p = self.params
        wf = self.warmup_fraction
        # Ease-in: slow start then accelerates
        eased_warmup = wf * wf * (3.0 - 2.0 * wf)
        effective_heat = p.heat_strength * eased_warmup

        gravity = -p.gravity * p.flow_speed
        buoy_max = p.buoyancy_max * p.flow_speed

        for b in self.blobs:
            # ── Heat transfer ──
            if b.y < p.heat_zone and effective_heat > 0.01:
                proximity = max(0.0, 1.0 - b.y / p.heat_zone)
                mass_scale = 0.6 + 0.8 * (1.0 - b.mass / 0.007)
                heat_rate = proximity * proximity * 3.0 * effective_heat * mass_scale
                b.temperature = min(1.0, b.temperature + heat_rate * dt)

            # Cooling
            if b.y > p.cool_zone:
                cool_frac = (b.y - p.cool_zone) / (1.0 - p.cool_zone)
                b.temperature = max(0.0, b.temperature - cool_frac * p.top_cool_rate * dt)
            elif b.y > p.heat_zone:
                b.temperature = max(0.0, b.temperature - p.mid_cool_rate * dt)

            # ── Expansion ──
            expand_t = max(0.0, min(1.0, b.temperature / 0.6))
            expand_eased = expand_t * expand_t * (3.0 - 2.0 * expand_t)
            b.radius = b.cold_radius + (b.warm_radius - b.cold_radius) * expand_eased

            # ── Buoyancy ──
            if b.temperature > p.melt_temp:
                melt_frac = (b.temperature - p.melt_temp) / (1.0 - p.melt_temp)
                ramp = math.sqrt(melt_frac)
                net_vertical = gravity + ramp * (buoy_max - gravity)

                if not b.detached and ramp > 0.35:
                    b.detached = True
                    b.vy += 0.12 + self.rng.uniform(0, 0.08)
            else:
                net_vertical = gravity

            # ── Apply forces ──
            b.vx += (-p.h_drag * b.vx) * dt
            b.vy += (net_vertical - p.v_drag * b.vy) * dt
            b.vz += (-p.h_drag * b.vz) * dt

            drift = 0.06 if b.detached else 0.008
            b.vx += self.rng.uniform(-0.5, 0.5) * drift * dt
            b.vz += self.rng.uniform(-0.5, 0.5) * drift * dt

            # ── Update position ──
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.z += b.vz * dt

            # ── Cylindrical wall ──
            hr = math.sqrt(b.x * b.x + b.z * b.z)
            max_r = p.wall_radius - b.radius * 0.4
            if hr > max_r and hr > 0.001:
                nx = b.x / hr
                nz = b.z / hr
                b.x = nx * max_r
                b.z = nz * max_r
                vn = b.vx * nx + b.vz * nz
                if vn > 0:
                    b.vx -= 1.5 * vn * nx
                    b.vz -= 1.5 * vn * nz

            # ── Floor / ceiling ──
            min_y = b.radius * 0.25
            max_y = 1.0 - b.radius * 0.25
            if b.y < min_y:
                b.y = min_y
                b.vy = abs(b.vy) * 0.15
                b.detached = False
            if b.y > max_y:
                b.y = max_y
                b.vy = -abs(b.vy) * 0.25

        # ── Inter-blob forces ──
        blobs = self.blobs
        for i in range(len(blobs)):
            for j in range(i + 1, len(blobs)):
                a, bj = blobs[i], blobs[j]
                dx = bj.x - a.x
                dy = bj.y - a.y
                dz = bj.z - a.z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 0.001
                min_dist = (a.radius + bj.radius) * 0.7

                if dist < min_dist:
                    overlap = (min_dist - dist) / min_dist
                    force = overlap * p.repulsion_strength
                    nx_ = dx / dist
                    ny_ = dy / dist
                    nz_ = dz / dist
                    mr = a.mass / (a.mass + bj.mass)

                    a.vx -= nx_ * force * (1 - mr)
                    a.vy -= ny_ * force * (1 - mr)
                    a.vz -= nz_ * force * (1 - mr)
                    bj.vx += nx_ * force * mr
                    bj.vy += ny_ * force * mr
                    bj.vz += nz_ * force * mr

                    temp_diff = a.temperature - bj.temperature
                    if abs(temp_diff) > 0.1:
                        sep = temp_diff * overlap * p.thermal_separation
                        a.vy += sep
                        bj.vy -= sep

    # ── mixing / stirring ─────────────────────────────────────────────────

    def stir(self, strength: float = 0.3) -> None:
        """Apply a random lateral impulse to all blobs (like shaking)."""
        for b in self.blobs:
            b.vx += self.rng.uniform(-1, 1) * strength
            b.vz += self.rng.uniform(-1, 1) * strength
            b.vy += self.rng.uniform(-0.3, 0.3) * strength

    def heat_burst(self, strength: float = 0.3) -> None:
        """Instant temperature boost to all blobs (like turning up heat)."""
        for b in self.blobs:
            b.temperature = min(1.0, b.temperature + strength)

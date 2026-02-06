"""
Lava lamp physics engine.

Manages blob state and runs the thermodynamic / buoyancy simulation.
Each blob can have individual "wax type" properties that affect its
density, heat sensitivity, viscosity, and expansion ratio.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wax types — per-blob material properties
# ---------------------------------------------------------------------------

@dataclass
class WaxType:
    """Material properties for a wax blob.

    All values are multipliers relative to the global physics params,
    so 1.0 = "standard wax".
    """
    name: str = "Standard"
    density: float = 1.0         # >1 heavier (sinks more), <1 lighter (rises faster)
    heat_sensitivity: float = 1.0  # >1 heats/cools faster, <1 slower (thermal inertia)
    viscosity: float = 1.0       # >1 more sluggish, <1 zippier
    expansion: float = 1.0      # >1 expands more when hot, <1 stays compact


# Built-in wax types
WAX_TYPES: Dict[str, WaxType] = {
    "standard": WaxType("Standard",      density=1.0, heat_sensitivity=1.0, viscosity=1.0, expansion=1.0),
    "heavy":    WaxType("Heavy",          density=1.6, heat_sensitivity=0.7, viscosity=1.3, expansion=0.8),
    "light":    WaxType("Light",          density=0.6, heat_sensitivity=1.3, viscosity=0.7, expansion=1.2),
    "sluggish": WaxType("Sluggish",       density=1.2, heat_sensitivity=0.5, viscosity=2.0, expansion=0.9),
    "volatile": WaxType("Volatile",       density=0.8, heat_sensitivity=2.0, viscosity=0.5, expansion=1.5),
    "giant":    WaxType("Giant Globule",  density=1.1, heat_sensitivity=0.6, viscosity=1.5, expansion=1.4),
}

WAX_TYPE_NAMES = list(WAX_TYPES.keys())


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
    # Per-blob colour (None = use scheme default)
    color: Optional[Tuple[int, int, int]] = None
    hot_color: Optional[Tuple[int, int, int]] = None
    # Per-blob material properties
    wax: WaxType = None  # type: ignore[assignment]
    # Label for UI
    label: str = ""

    def __post_init__(self):
        self.cold_radius = self.warm_radius * 0.35
        self.radius = self.cold_radius
        self.base_radius = self.warm_radius
        self.mass = self.warm_radius ** 3
        if self.wax is None:
            self.wax = WaxType()


# ---------------------------------------------------------------------------
# Physics parameters (user-tunable)
# ---------------------------------------------------------------------------

@dataclass
class PhysicsParams:
    """All tuneable physics constants."""
    # Forces
    gravity: float = 0.18
    buoyancy_max: float = 0.65
    h_drag: float = 2.5
    v_drag: float = 1.6

    # Thermal
    heat_strength: float = 1.0
    heat_zone: float = 0.30
    cool_zone: float = 0.65
    melt_temp: float = 0.28
    mid_cool_rate: float = 0.08
    top_cool_rate: float = 2.5

    # Blob interaction — close range (overlap)
    repulsion_strength: float = 1.5
    thermal_separation: float = 0.6

    # Blob interaction — medium range (displacement)
    displacement_range: float = 1.8    # interaction radius as multiple of combined radii
    displacement_strength: float = 0.4  # lateral push strength
    approach_deflection: float = 0.6    # velocity-dependent lateral deflection

    # Geometry
    wall_radius: float = 0.42

    # Warmup
    warmup_duration: float = 18.0

    # Expansion
    cold_radius_fraction: float = 0.35

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
                label=f"Blob {i+1}",
            )
            b.cold_radius = r * frac
            b.radius = b.cold_radius
            blobs.append(b)
        # Large pool blob
        pool = Blob(x=0.0, y=0.02, z=0.0, warm_radius=0.19, label="Pool")
        pool.cold_radius = 0.19 * frac
        pool.radius = pool.cold_radius
        blobs.append(pool)
        return blobs

    @property
    def blob_count(self) -> int:
        return self._blob_count

    @property
    def warmup_fraction(self) -> float:
        if self.params.warmup_duration <= 0:
            return 1.0
        return min(1.0, self.warmup_time / self.params.warmup_duration)

    # ── physics step ──────────────────────────────────────────────────────

    def step(self, dt: float) -> None:
        """Advance simulation by *dt* seconds."""
        dt = min(dt, 0.05)
        self.warmup_time += dt

        p = self.params
        wf = self.warmup_fraction
        eased_warmup = wf * wf * (3.0 - 2.0 * wf)
        effective_heat = p.heat_strength * eased_warmup

        base_gravity = -p.gravity * p.flow_speed
        base_buoy_max = p.buoyancy_max * p.flow_speed

        for b in self.blobs:
            w = b.wax  # per-blob wax properties

            # Effective per-blob parameters
            gravity = base_gravity * w.density
            buoy_max = base_buoy_max / max(w.density, 0.1)
            b_h_drag = p.h_drag * w.viscosity
            b_v_drag = p.v_drag * w.viscosity

            # ── Heat transfer ──
            if b.y < p.heat_zone and effective_heat > 0.01:
                proximity = max(0.0, 1.0 - b.y / p.heat_zone)
                mass_scale = 0.6 + 0.8 * (1.0 - b.mass / 0.007)
                heat_rate = proximity * proximity * 3.0 * effective_heat * mass_scale
                heat_rate *= w.heat_sensitivity
                b.temperature = min(1.0, b.temperature + heat_rate * dt)

            # Cooling
            if b.y > p.cool_zone:
                cool_frac = (b.y - p.cool_zone) / (1.0 - p.cool_zone)
                b.temperature = max(0.0, b.temperature - cool_frac * p.top_cool_rate * w.heat_sensitivity * dt)
            elif b.y > p.heat_zone:
                b.temperature = max(0.0, b.temperature - p.mid_cool_rate * w.heat_sensitivity * dt)

            # ── Expansion (scaled by wax expansion factor) ──
            expand_t = max(0.0, min(1.0, b.temperature / 0.6))
            expand_eased = expand_t * expand_t * (3.0 - 2.0 * expand_t)
            expansion_range = (b.warm_radius - b.cold_radius) * w.expansion
            b.radius = b.cold_radius + expansion_range * expand_eased

            # ── Buoyancy ──
            if b.temperature > p.melt_temp:
                melt_frac = (b.temperature - p.melt_temp) / (1.0 - p.melt_temp)
                ramp = math.sqrt(melt_frac)
                net_vertical = gravity + ramp * (buoy_max - gravity)

                if not b.detached and ramp > 0.35:
                    b.detached = True
                    b.vy += (0.12 + self.rng.uniform(0, 0.08)) / max(w.viscosity, 0.1)
            else:
                net_vertical = gravity

            # ── Apply forces (per-blob drag) ──
            b.vx += (-b_h_drag * b.vx) * dt
            b.vy += (net_vertical - b_v_drag * b.vy) * dt
            b.vz += (-b_h_drag * b.vz) * dt

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
        self._inter_blob_forces(dt)

    def _inter_blob_forces(self, dt: float) -> None:
        """Two-tier blob interaction.

        1) Close range (dist < 0.7 * combined radii):
           Hard repulsion + thermal separation.

        2) Medium range (dist < displacement_range * combined radii):
           - Positional repulsion: gentle push to spread blobs out.
           - Velocity-dependent lateral deflection: when blobs approach
             each other vertically (one rising, one sinking), push them
             sideways.  This is the incompressible-fluid displacement
             effect — a rising blob must push surrounding material aside.
        """
        p = self.params
        blobs = self.blobs
        n = len(blobs)

        for i in range(n):
            for j in range(i + 1, n):
                a, bj = blobs[i], blobs[j]
                dx = bj.x - a.x
                dy = bj.y - a.y
                dz = bj.z - a.z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 0.001

                combined_r = a.radius + bj.radius
                close_dist = combined_r * 0.7
                far_dist = combined_r * p.displacement_range

                if dist >= far_dist:
                    continue

                nx_ = dx / dist
                ny_ = dy / dist
                nz_ = dz / dist
                mr = a.mass / (a.mass + bj.mass)

                # ── CLOSE RANGE: hard repulsion + thermal separation ──
                if dist < close_dist:
                    overlap = (close_dist - dist) / close_dist
                    force = overlap * p.repulsion_strength

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

                # ── MEDIUM RANGE: displacement + approach deflection ──
                # Smooth quadratic falloff from close_dist to far_dist
                t = (far_dist - dist) / (far_dist - close_dist + 0.001)
                t = max(0.0, min(1.0, t))
                t2 = t * t

                # (a) Gentle positional repulsion
                pos_force = t2 * p.displacement_strength * 0.3
                a.vx -= nx_ * pos_force * (1 - mr) * dt
                a.vy -= ny_ * pos_force * (1 - mr) * dt * 0.3
                a.vz -= nz_ * pos_force * (1 - mr) * dt
                bj.vx += nx_ * pos_force * mr * dt
                bj.vy += ny_ * pos_force * mr * dt * 0.3
                bj.vz += nz_ * pos_force * mr * dt

                # (b) Velocity-dependent lateral deflection
                rel_vx = bj.vx - a.vx
                rel_vy = bj.vy - a.vy
                rel_vz = bj.vz - a.vz
                approach = -(rel_vx * nx_ + rel_vy * ny_ + rel_vz * nz_)

                if approach > 0.01:
                    # Lateral direction perpendicular to connection axis
                    lat_x = -nz_
                    lat_z = nx_
                    lat_len = math.sqrt(lat_x * lat_x + lat_z * lat_z)
                    if lat_len < 0.01:
                        angle = self.rng.uniform(0, 2 * math.pi)
                        lat_x = math.cos(angle)
                        lat_z = math.sin(angle)
                    else:
                        lat_x /= lat_len
                        lat_z /= lat_len

                    deflect = approach * t2 * p.approach_deflection

                    a.vx -= lat_x * deflect * (1 - mr)
                    a.vz -= lat_z * deflect * (1 - mr)
                    bj.vx += lat_x * deflect * mr
                    bj.vz += lat_z * deflect * mr

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

    # ── per-blob property access ──────────────────────────────────────────

    def set_blob_wax(self, index: int, wax_type: str) -> None:
        """Set a blob's wax type by name."""
        if 0 <= index < len(self.blobs):
            if wax_type in WAX_TYPES:
                self.blobs[index].wax = WAX_TYPES[wax_type]
            else:
                logger.warning("Unknown wax type: %s", wax_type)

    def set_blob_wax_custom(
        self, index: int,
        density: float = 1.0,
        heat_sensitivity: float = 1.0,
        viscosity: float = 1.0,
        expansion: float = 1.0,
    ) -> None:
        """Set custom wax properties on a single blob."""
        if 0 <= index < len(self.blobs):
            self.blobs[index].wax = WaxType(
                name="Custom",
                density=density,
                heat_sensitivity=heat_sensitivity,
                viscosity=viscosity,
                expansion=expansion,
            )

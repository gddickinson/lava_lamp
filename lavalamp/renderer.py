"""
Metaball renderer — numpy-vectorised 2D rendering of 3D blob state.

Renders at a reduced resolution and returns an (H, W, 4) RGBA uint8
array suitable for display in a QImage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Tuple

import numpy as np

if TYPE_CHECKING:
    from .engine import LavaLampEngine
    from .palettes import ColorScheme

logger = logging.getLogger(__name__)


def lamp_radius(y01: np.ndarray) -> np.ndarray:
    """Compute lamp silhouette radius at normalised height(s).

    Returns a value ~0.46 in the middle with slight bulge and
    tapered caps at top/bottom.
    """
    bulge = 1.0 + 0.06 * np.sin(y01 * np.pi)
    taper = np.ones_like(y01)
    taper = np.where(y01 < 0.05, y01 / 0.05, taper)
    taper = np.where(y01 > 0.95, (1.0 - y01) / 0.05, taper)
    taper = np.maximum(taper, 0.3)
    return 0.46 * bulge * taper


def render_frame(
    engine: "LavaLampEngine",
    scheme: "ColorScheme",
    width: int = 220,
    height: int = 520,
    render_scale: float = 0.35,
) -> np.ndarray:
    """Render one frame → (height, width, 4) uint8 RGBA array.

    Parameters:
        engine:       The lava lamp engine with current blob state.
        scheme:       Colour scheme for wax and liquid.
        width:        Output width in pixels.
        height:       Output height in pixels.
        render_scale: Fraction to render at (e.g. 0.35 = 35%).
    """
    rw = max(4, int(width * render_scale))
    rh = max(4, int(height * render_scale))

    # Pixel coordinate grids
    py_idx = np.arange(rh)
    px_idx = np.arange(rw)
    py_grid, px_grid = np.meshgrid(py_idx, px_idx, indexing="ij")

    # Normalised coordinates
    y01 = py_grid / rh                         # 0=top, 1=bottom
    blob_y = 1.0 - y01                          # 0=bottom, 1=top (blob space)
    x01 = (px_grid / rw - 0.5) * 2.0           # -1..1

    # Lamp silhouette
    lamp_r = lamp_radius(1.0 - y01)
    inside_lamp = np.abs(x01) < lamp_r * 2.0

    # ── Metaball field evaluation ──────────────────────────────────────
    field = np.zeros((rh, rw), dtype=np.float64)
    weighted_temp = np.zeros((rh, rw), dtype=np.float64)
    total_weight = np.zeros((rh, rw), dtype=np.float64)

    blobs = engine.blobs
    for b in blobs:
        proj_x = b.x * 2.0
        proj_y = b.y
        depth_factor = 1.0 / (1.0 + b.z * 0.3)
        proj_r = b.radius * depth_factor * 3.0

        dx = x01 - proj_x
        dy = blob_y - proj_y
        dist2 = dx * dx + dy * dy
        r2 = proj_r * proj_r

        # Only compute where blob is close enough to contribute
        mask = dist2 < r2 * 9.0
        contribution = np.where(mask, r2 / (dist2 + 0.001), 0.0)
        field += contribution
        weighted_temp += b.temperature * contribution
        total_weight += contribution

    threshold = 1.0
    is_wax = (field > threshold) & inside_lamp

    # Temperature per pixel
    temp = np.where(total_weight > 0, weighted_temp / np.maximum(total_weight, 1e-10), 0.0)

    # ── Colour computation ────────────────────────────────────────────
    img = np.zeros((rh, rw, 4), dtype=np.uint8)

    # Wax colour: interpolate base→hot based on temperature
    base = np.array(scheme.base, dtype=np.float64)
    hot = np.array(scheme.hot, dtype=np.float64)
    t3 = temp[..., np.newaxis]  # (rh, rw, 1)
    wax_rgb = base + (hot - base) * t3

    # Brighten at high field values (centre of blob)
    bright = np.clip((field - 1.0) * 0.5, 0, 1.0)[..., np.newaxis]
    wax_rgb = np.minimum(255, wax_rgb + bright * np.array([50, 60, 30]))

    # Fake 3D shading: darken at horizontal edges
    edge_dist = np.abs(x01) / np.maximum(lamp_r * 2.0, 0.01)
    shade = (1.0 - edge_dist * edge_dist * 0.4)[..., np.newaxis]
    wax_rgb *= shade

    # Specular highlight on left side
    spec = np.maximum(0, 1.0 - np.abs(x01 + lamp_r * 0.6) / np.maximum(lamp_r * 0.8, 0.01))
    spec_pow = (spec ** 3 * 0.3)[..., np.newaxis]
    wax_rgb = np.minimum(255, wax_rgb + spec_pow * np.array([200, 150, 80]))

    # Apply wax pixels
    wax_rgb_u8 = np.clip(wax_rgb, 0, 255).astype(np.uint8)
    img[is_wax, 0] = wax_rgb_u8[is_wax, 0]
    img[is_wax, 1] = wax_rgb_u8[is_wax, 1]
    img[is_wax, 2] = wax_rgb_u8[is_wax, 2]
    img[is_wax, 3] = 255

    # Liquid background (inside lamp, not wax)
    is_liquid = inside_lamp & ~is_wax
    liq = np.array(scheme.liquid, dtype=np.float64)
    glow = np.clip(field * 0.3, 0, 1.0)[..., np.newaxis]
    liq_rgb = liq + glow * base * 0.3
    liq_rgb *= shade
    liq_rgb_u8 = np.clip(liq_rgb, 0, 255).astype(np.uint8)
    img[is_liquid, 0] = liq_rgb_u8[is_liquid, 0]
    img[is_liquid, 1] = liq_rgb_u8[is_liquid, 1]
    img[is_liquid, 2] = liq_rgb_u8[is_liquid, 2]
    img[is_liquid, 3] = 255

    # Outside lamp → transparent / dark
    outside = ~inside_lamp
    img[outside, 3] = 0

    # ── Cap overlays (top and bottom ellipses) ─────────────────────────
    # Bottom heat glow (intensity follows warmup)
    warmup = engine.warmup_fraction
    glow_alpha = 0.03 + warmup * 0.18
    for py in range(max(0, rh - int(rh * 0.15)), rh):
        gy = (py - (rh - int(rh * 0.15))) / max(int(rh * 0.15), 1)
        for px in range(rw):
            gx = (px / rw - 0.5) * 2
            gdist = (gx * gx + gy * gy * 0.5)
            if gdist < 1.0:
                ga = glow_alpha * (1.0 - gdist)
                if img[py, px, 3] > 0:
                    img[py, px, 0] = min(255, int(img[py, px, 0] + base[0] * ga))
                    img[py, px, 1] = min(255, int(img[py, px, 1] + base[1] * ga))
                    img[py, px, 2] = min(255, int(img[py, px, 2] + base[2] * ga))

    return img


def upscale_image(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Simple nearest-neighbour upscale (for QImage display).

    For smoother results, the QWidget painter uses SmoothPixmapTransform
    when drawing the QPixmap.  This just reshapes for initial display.
    """
    h, w = img.shape[:2]
    if h == target_h and w == target_w:
        return img
    # Use numpy repeat for speed
    sy = max(1, target_h // h)
    sx = max(1, target_w // w)
    return np.repeat(np.repeat(img, sy, axis=0), sx, axis=1)[:target_h, :target_w]

"""
Colour schemes for the lava lamp.

Each scheme defines:
  - base:     Cold wax colour (RGB)
  - hot:      Hot wax colour — interpolated with base by temperature
  - liquid:   Background liquid colour (dark)
  - bg:       Widget background tint (very dark)
  - contrast: Optional second wax colour for alternating blobs

Includes utilities for generating complementary / triadic / split
contrast colours from any base hue.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class ColorScheme:
    """Immutable colour scheme for a lava lamp."""
    name: str
    base: RGB
    hot: RGB
    liquid: RGB
    bg: RGB
    contrast: Optional[RGB] = None  # second wax colour for alternating blobs

    @property
    def base_f(self) -> Tuple[float, float, float]:
        return tuple(c / 255.0 for c in self.base)

    @property
    def hot_f(self) -> Tuple[float, float, float]:
        return tuple(c / 255.0 for c in self.hot)


# ── Built-in schemes ─────────────────────────────────────────────────────

SCHEMES: Dict[str, ColorScheme] = {
    "classic": ColorScheme(
        name="Classic Red",
        base=(180, 30, 10), hot=(255, 180, 40),
        bg=(20, 8, 5), liquid=(45, 15, 8),
    ),
    "blue": ColorScheme(
        name="Cosmic Blue",
        base=(20, 40, 180), hot=(80, 180, 255),
        bg=(5, 8, 25), liquid=(8, 12, 45),
    ),
    "green": ColorScheme(
        name="Acid Green",
        base=(30, 160, 20), hot=(180, 255, 60),
        bg=(5, 20, 5), liquid=(8, 35, 10),
    ),
    "purple": ColorScheme(
        name="Nebula",
        base=(120, 20, 160), hot=(220, 100, 255),
        bg=(15, 5, 20), liquid=(30, 10, 40),
    ),
    "gold": ColorScheme(
        name="Molten Gold",
        base=(180, 120, 10), hot=(255, 220, 80),
        bg=(20, 14, 5), liquid=(40, 28, 8),
    ),
    "cyan": ColorScheme(
        name="Cyan Glow",
        base=(10, 150, 160), hot=(60, 240, 255),
        bg=(4, 15, 18), liquid=(6, 30, 35),
    ),
    "magenta": ColorScheme(
        name="Hot Magenta",
        base=(180, 20, 100), hot=(255, 100, 200),
        bg=(20, 4, 12), liquid=(40, 8, 25),
    ),
    "orange": ColorScheme(
        name="Ember",
        base=(200, 80, 5), hot=(255, 200, 50),
        bg=(22, 10, 2), liquid=(45, 20, 4),
    ),
    "white": ColorScheme(
        name="Ghost",
        base=(180, 180, 190), hot=(240, 240, 255),
        bg=(10, 10, 12), liquid=(20, 20, 25),
    ),
    "sunset": ColorScheme(
        name="Sunset",
        base=(200, 50, 30), hot=(255, 180, 80),
        bg=(20, 6, 4), liquid=(40, 12, 8),
        contrast=(80, 20, 140),  # deep purple contrast
    ),
    "ocean_fire": ColorScheme(
        name="Ocean & Fire",
        base=(20, 60, 180), hot=(100, 200, 255),
        bg=(4, 8, 20), liquid=(8, 15, 40),
        contrast=(200, 60, 10),  # fire-orange contrast
    ),
    "toxic": ColorScheme(
        name="Toxic",
        base=(40, 200, 20), hot=(200, 255, 80),
        bg=(5, 22, 3), liquid=(10, 40, 6),
        contrast=(200, 20, 180),  # magenta contrast
    ),
}

DEFAULT_SCHEME = "classic"


# ── Contrast colour generation ────────────────────────────────────────────

def _clamp_rgb(r: float, g: float, b: float) -> RGB:
    return (
        max(0, min(255, int(r * 255))),
        max(0, min(255, int(g * 255))),
        max(0, min(255, int(b * 255))),
    )


def complementary(base: RGB) -> RGB:
    """Return the complementary (opposite hue) colour."""
    h, s, v = colorsys.rgb_to_hsv(base[0]/255, base[1]/255, base[2]/255)
    h2 = (h + 0.5) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h2, s, v)
    return _clamp_rgb(r, g, b)


def triadic(base: RGB) -> Tuple[RGB, RGB]:
    """Return two triadic colours (±120° hue)."""
    h, s, v = colorsys.rgb_to_hsv(base[0]/255, base[1]/255, base[2]/255)
    c1 = colorsys.hsv_to_rgb((h + 1/3) % 1.0, s, v)
    c2 = colorsys.hsv_to_rgb((h + 2/3) % 1.0, s, v)
    return _clamp_rgb(*c1), _clamp_rgb(*c2)


def split_complementary(base: RGB) -> Tuple[RGB, RGB]:
    """Return two split-complementary colours (±150° hue)."""
    h, s, v = colorsys.rgb_to_hsv(base[0]/255, base[1]/255, base[2]/255)
    c1 = colorsys.hsv_to_rgb((h + 5/12) % 1.0, s, v)
    c2 = colorsys.hsv_to_rgb((h + 7/12) % 1.0, s, v)
    return _clamp_rgb(*c1), _clamp_rgb(*c2)


def analogous(base: RGB, offset: float = 0.08) -> Tuple[RGB, RGB]:
    """Return two analogous colours (nearby hues)."""
    h, s, v = colorsys.rgb_to_hsv(base[0]/255, base[1]/255, base[2]/255)
    c1 = colorsys.hsv_to_rgb((h + offset) % 1.0, s, v)
    c2 = colorsys.hsv_to_rgb((h - offset) % 1.0, s, v)
    return _clamp_rgb(*c1), _clamp_rgb(*c2)


def make_liquid_from_base(base: RGB) -> RGB:
    """Generate a dark liquid colour from a base wax colour."""
    return (max(2, base[0] // 5), max(2, base[1] // 5), max(2, base[2] // 5))


def make_hot_from_base(base: RGB) -> RGB:
    """Generate a 'hot' version — brighter, shifted towards yellow/white."""
    h, s, v = colorsys.rgb_to_hsv(base[0]/255, base[1]/255, base[2]/255)
    v2 = min(1.0, v + 0.35)
    s2 = max(0.0, s - 0.2)
    r, g, b = colorsys.hsv_to_rgb(h, s2, v2)
    return _clamp_rgb(r, g, b)


def make_bg_from_base(base: RGB) -> RGB:
    """Generate a very dark background tint from base."""
    return (max(1, base[0] // 12), max(1, base[1] // 12), max(1, base[2] // 12))


def create_custom_scheme(
    name: str,
    base: RGB,
    contrast: Optional[RGB] = None,
    contrast_mode: str = "none",
) -> ColorScheme:
    """Build a complete scheme from just a base wax colour.

    Args:
        name:           Display name.
        base:           Primary wax RGB.
        contrast:       Explicit contrast colour, or None.
        contrast_mode:  One of 'none', 'complementary', 'triadic',
                        'split', 'analogous', 'custom'.
    """
    hot = make_hot_from_base(base)
    liquid = make_liquid_from_base(base)
    bg = make_bg_from_base(base)

    if contrast_mode == "complementary":
        contrast = complementary(base)
    elif contrast_mode == "triadic":
        contrast = triadic(base)[0]
    elif contrast_mode == "split":
        contrast = split_complementary(base)[0]
    elif contrast_mode == "analogous":
        contrast = analogous(base)[0]
    elif contrast_mode == "custom" and contrast is None:
        contrast = complementary(base)

    return ColorScheme(
        name=name, base=base, hot=hot, liquid=liquid, bg=bg, contrast=contrast,
    )


# ── Accessors ─────────────────────────────────────────────────────────────

def get_scheme(name: str) -> ColorScheme:
    if name not in SCHEMES:
        available = ", ".join(sorted(SCHEMES.keys()))
        raise KeyError(f"Unknown scheme '{name}'. Available: {available}")
    return SCHEMES[name]


def list_schemes() -> List[str]:
    return sorted(SCHEMES.keys())


# ── Blob colour modes ─────────────────────────────────────────────────────

# Modes for assigning individual colours to each blob:
#   "uniform"    — all blobs use the scheme's base/hot
#   "contrast"   — alternate between base and contrast colour
#   "rainbow"    — each blob gets a different hue at equal spacing
#   "warm_cool"  — half warm tones, half cool tones
#   "random"     — random hue per blob (fixed saturation/value)
#   "gradient"   — gradient from base hue to contrasting hue
#   "custom"     — user assigns colours individually

BLOB_COLOR_MODES = [
    "uniform", "contrast", "rainbow", "warm_cool",
    "random", "gradient",
]


def _hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return _clamp_rgb(r, g, b)


def assign_blob_colors(
    blob_count: int,
    scheme: ColorScheme,
    mode: str = "uniform",
    seed: int = 42,
) -> List[Tuple[RGB, RGB]]:
    """Generate (base_color, hot_color) pairs for each blob.

    Args:
        blob_count: Total number of blobs (including pool blob).
        scheme:     Current colour scheme.
        mode:       One of BLOB_COLOR_MODES.
        seed:       RNG seed for 'random' mode reproducibility.

    Returns:
        List of (base_rgb, hot_rgb) tuples, one per blob.
    """
    import random as _random
    rng = _random.Random(seed)

    if mode == "uniform" or mode not in BLOB_COLOR_MODES:
        # All blobs same colour
        return [(scheme.base, scheme.hot)] * blob_count

    elif mode == "contrast":
        # Alternate between base and contrast colour
        contrast = scheme.contrast or complementary(scheme.base)
        contrast_hot = make_hot_from_base(contrast)
        colors = []
        for i in range(blob_count):
            if i % 2 == 0:
                colors.append((scheme.base, scheme.hot))
            else:
                colors.append((contrast, contrast_hot))
        return colors

    elif mode == "rainbow":
        # Evenly spaced hues around the colour wheel
        base_h, base_s, base_v = colorsys.rgb_to_hsv(
            scheme.base[0]/255, scheme.base[1]/255, scheme.base[2]/255
        )
        colors = []
        for i in range(blob_count):
            h = (base_h + i / max(blob_count, 1)) % 1.0
            base_c = _hsv_to_rgb(h, max(0.6, base_s), max(0.5, base_v))
            hot_c = make_hot_from_base(base_c)
            colors.append((base_c, hot_c))
        return colors

    elif mode == "warm_cool":
        # First half: warm hues (reds/oranges/yellows)
        # Second half: cool hues (blues/greens/purples)
        colors = []
        for i in range(blob_count):
            frac = i / max(blob_count - 1, 1)
            if frac < 0.5:
                # Warm: hue 0.0–0.12 (red→orange→yellow)
                h = 0.0 + frac * 2 * 0.12
                s, v = 0.85, 0.75
            else:
                # Cool: hue 0.5–0.72 (cyan→blue→purple)
                h = 0.5 + (frac - 0.5) * 2 * 0.22
                s, v = 0.75, 0.7
            base_c = _hsv_to_rgb(h, s, v)
            hot_c = make_hot_from_base(base_c)
            colors.append((base_c, hot_c))
        return colors

    elif mode == "random":
        # Random hues with consistent saturation/value
        base_h, base_s, base_v = colorsys.rgb_to_hsv(
            scheme.base[0]/255, scheme.base[1]/255, scheme.base[2]/255
        )
        colors = []
        for i in range(blob_count):
            h = rng.random()
            s = 0.6 + rng.random() * 0.3
            v = 0.5 + rng.random() * 0.35
            base_c = _hsv_to_rgb(h, s, v)
            hot_c = make_hot_from_base(base_c)
            colors.append((base_c, hot_c))
        return colors

    elif mode == "gradient":
        # Gradient from base hue to contrast hue
        base_h, base_s, base_v = colorsys.rgb_to_hsv(
            scheme.base[0]/255, scheme.base[1]/255, scheme.base[2]/255
        )
        contrast = scheme.contrast or complementary(scheme.base)
        end_h, end_s, end_v = colorsys.rgb_to_hsv(
            contrast[0]/255, contrast[1]/255, contrast[2]/255
        )
        # Find shortest path around hue wheel
        dh = end_h - base_h
        if abs(dh) > 0.5:
            dh = dh - 1.0 if dh > 0 else dh + 1.0

        colors = []
        for i in range(blob_count):
            t = i / max(blob_count - 1, 1)
            h = (base_h + dh * t) % 1.0
            s = base_s + (end_s - base_s) * t
            v = base_v + (end_v - base_v) * t
            base_c = _hsv_to_rgb(h, s, v)
            hot_c = make_hot_from_base(base_c)
            colors.append((base_c, hot_c))
        return colors

    return [(scheme.base, scheme.hot)] * blob_count

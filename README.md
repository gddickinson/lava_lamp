# 🫧 Lava Lamp Simulator

A physics-based lava lamp simulation with metaball rendering, built with Python, PyQt5, and NumPy.

## Physics

Wax blobs sit cold and compact at the bottom of a cylindrical vessel. A heat source gradually warms them over an 18-second warmup phase:

- **Thermal expansion** — hot wax expands from 35% to 100% of its warm radius via smoothstep interpolation
- **√-ramp buoyancy** — once temperature exceeds the melt threshold (28%), buoyancy ramps up with √(meltFraction), giving decisive detachment rather than sluggish hovering
- **Separate H/V drag** — vertical drag (1.6) is lower than horizontal (2.5) so blobs travel the full lamp height, arriving at the cool zone with heat to spare
- **Zone-based cooling** — strong at top, mild in mid-zone, none at bottom; blobs retain enough heat to complete their convection cycle
- **Thermal separation** — when hot and cold blobs overlap, the hot blob gets pushed upward (density-driven separation)
- **Detachment impulse** — a one-time upward kick breaks blobs free from the bottom cluster

## Rendering

2D metaball field evaluation: for each pixel, Σ(rᵢ² / dᵢ²) is computed across all blobs using their 3D→2D projected positions. Where the field exceeds a threshold, wax is drawn with:
- Temperature-based colour interpolation (cold→hot)
- Fake 3D edge shading
- Left-side specular highlight
- Depth-dependent radius scaling

Rendered at 35% resolution (configurable) with bilinear upscaling for smooth ~30fps.

## Installation

```bash
pip install numpy PyQt5
```

## Usage

```bash
# Default: 6 blobs, classic red
python run_lavalamp.py

# Or as a module
python -m lavalamp

# Custom configuration
python run_lavalamp.py --blobs 8 --scheme blue --quality 50

# List available schemes
python run_lavalamp.py --list-schemes

# Verbose logging
python run_lavalamp.py -v
```

## Controls

### Colour Scheme
- **12 built-in schemes**: Classic Red, Cosmic Blue, Acid Green, Nebula, Molten Gold, Cyan Glow, Hot Magenta, Ember, Ghost, Sunset, Ocean & Fire, Toxic
- **Contrast colours**: Complementary, Triadic, Split Complementary, Analogous, or Custom picker
- **Custom base colour**: Pick any base wax colour; hot/liquid/background auto-generated
- **3 schemes with built-in contrast**: Sunset, Ocean & Fire, Toxic

### Physics Parameters
| Control | Range | Default | Description |
|---------|-------|---------|-------------|
| Heat | 10–250% | 100% | Heat source intensity |
| Flow Speed | 10–300% | 100% | Overall simulation speed |
| Gravity | 5–50 | 18 | Downward force |
| Buoyancy | 20–150 | 65 | Peak upward force when hot |
| Vertical Drag | 0.5–5.0 | 1.6 | Resistance to vertical motion |
| Horiz. Drag | 0.5–5.0 | 2.5 | Resistance to lateral motion |
| Melt Temp | 10–60% | 28% | Temperature threshold for buoyancy |
| Warmup Time | 3–60s | 18s | Duration of lamp warmup phase |

### Blob Properties
| Control | Range | Default | Description |
|---------|-------|---------|-------------|
| Count | 3–12 | 6 | Number of wax blobs |
| Cold Size | 15–60% | 35% | Compact radius as fraction of warm |
| Repulsion | 0.5–4.0 | 1.5 | Inter-blob push strength |
| Thermal Sep. | 0–2.0 | 0.6 | Hot/cold separation force |

### Mixing
- **🌀 Stir** — gentle random lateral force
- **💥 Shake** — strong random force (all directions)
- **🔥 Heat Burst** — instant temperature boost
- **❄ Cool Down** — instant temperature reduction
- **Mouse drag** — stir the wax by dragging on the lamp

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `Ctrl+S` | Save image |
| `Space` | Pause / Resume |
| `Ctrl+R` | Reset lamp |
| `S` | Stir |
| `H` | Shake |
| `B` | Heat burst |

## Project Structure

```
lavalamp_app/
├── run_lavalamp.py          # Quick launcher
├── README.md
└── lavalamp/
    ├── __init__.py           # Package metadata
    ├── __main__.py           # python -m entry point
    ├── app.py                # CLI parsing, Qt launch, dark theme
    ├── engine.py             # Blob physics (3D thermodynamic sim)
    ├── renderer.py           # Numpy-vectorised metaball rendering
    ├── palettes.py           # 12 colour schemes + contrast generation
    ├── canvas.py             # Qt canvas + animation timer
    ├── controls.py           # Full control panel
    └── main_window.py        # Main window assembly
```


---
*Built with AI assistance from [Claude (Anthropic)](https://claude.com/).*

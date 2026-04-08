# Lava Lamp Simulator — Interface Map

## Package: `lavalamp/`

| File | Lines | Purpose | Key classes / functions |
|------|-------|---------|----------------------|
| `engine.py` | ~510 | Physics simulation: blobs, thermal model, buoyancy, inter-blob forces | `LavaLampEngine`, `Blob`, `PhysicsParams`, `WaxType`, `WAX_TYPES` |
| `renderer.py` | ~197 | Metaball 2D rendering (numpy-vectorised) | `render_frame()`, `lamp_radius()`, `upscale_image()` |
| `palettes.py` | ~354 | Colour schemes, contrast generation, blob colour modes | `ColorScheme`, `SCHEMES`, `assign_blob_colors()`, `create_custom_scheme()` |
| `controls.py` | ~827 | PyQt5 control panel (sliders, buttons, blob editor) | `ControlPanel`, `LSlider` |
| `canvas.py` | ~218 | Animated PyQt5 display widget | `LavaCanvas` |
| `main_window.py` | ~162 | Top-level QMainWindow with menus | `MainWindow` |
| `app.py` | ~234 | CLI args, dependency checks, Qt launch, dark theme | `main()` |
| `__init__.py` | ~27 | Package docstring and version | `__version__` |
| `__main__.py` | — | `python -m lavalamp` entry | — |

## Entry Points

| File | Purpose |
|------|---------|
| `run_lavalamp.py` (project root) | Quick launcher |
| `python -m lavalamp` | Package entry |
| CLI: `lavalamp --blobs 8 --scheme blue` | Via `app.py` argparse |

## Tests

| File | Coverage |
|------|----------|
| `tests/test_engine.py` | WaxType validation, Blob, PhysicsParams, LavaLampEngine step/reset/stir/heat, thermal model, buoyancy |
| `tests/test_renderer.py` | `lamp_radius()`, `render_frame()` output shape/dtype/content, `upscale_image()` |

## Data Flow

```
app.main()
  └── MainWindow
        ├── LavaCanvas  ─ timer tick ─▶ LavaLampEngine.step()
        │                              ▶ renderer.render_frame() ─▶ QPixmap
        └── ControlPanel ─ signals ──▶ LavaLampEngine (params, reset, stir)
                                     ▶ LavaCanvas (scheme, render_scale)
```

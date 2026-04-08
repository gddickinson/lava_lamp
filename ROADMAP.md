# Lava Lamp Simulator — Roadmap

## Current State
Well-structured PyQt5 application with clean modular architecture (8 files under `lavalamp/`). Physics engine, renderer, palettes, controls, and canvas are properly separated. Includes CLI args, 12 color schemes, extensive physics controls, and keyboard shortcuts. Code quality is high with type hints, dataclasses, and docstrings. No tests, no CI, no packaging metadata.

## Short-term Improvements
- [ ] Add unit tests for `engine.py` (blob physics, thermal model, buoyancy calculations)
- [ ] Add unit tests for `renderer.py` (metaball field evaluation, color interpolation)
- [ ] Add `pyproject.toml` with proper package metadata and entry point for `run_lavalamp.py`
- [ ] Add `requirements.txt` (currently only mentioned in README install section)
- [ ] Add input validation in `controls.py` for edge cases (e.g., 0 blobs, extreme drag values)
- [ ] Add error handling in `canvas.py` for display/rendering failures
- [ ] Add type hints to any remaining untyped public methods in `controls.py` and `main_window.py`

## Feature Enhancements
- [ ] Add preset system: save/load full parameter configurations (physics + colors) as JSON profiles
- [ ] Add recording mode: export animation as GIF or MP4 using `imageio` or `Pillow`
- [ ] Add multi-lamp view: side-by-side lamps with different color schemes
- [ ] Add sound: ambient bubbling sound effects synced to blob movement
- [ ] Performance: implement GPU-accelerated rendering via OpenGL or `pyqtgraph` for larger canvases
- [ ] Add screensaver mode: auto-cycling color schemes, fullscreen, no controls

## Long-term Vision
- [ ] Package and publish to PyPI as an installable app (`pip install lavalamp`)
- [ ] Add WebAssembly/browser version using `pyodide` or rewrite renderer in WebGL
- [ ] Plugin system for custom blob behaviors (e.g., magnetic blobs, splitting/merging)
- [ ] Add 3D rendering mode using actual OpenGL volume rendering instead of 2D metaball projection

## Technical Debt
- [ ] `WaxType` dataclass in `engine.py` could benefit from validation (no negative multipliers)
- [ ] Renderer resolution scaling (35% default) should be benchmarked — may be too conservative on modern hardware
- [ ] Extract repeated model-config code pattern from `controls.py` into a declarative slider factory
- [ ] Add CI pipeline (GitHub Actions) with linting (`ruff`) and test execution
- [ ] Pin dependency versions in a lockfile

"""
Application entry point — CLI parsing, dependency checks, Qt launch.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__


def _check_deps() -> list:
    missing = []
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        missing.append("PyQt5")
    return missing


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="lavalamp",
        description="Lava Lamp Simulator — physics-based metaball simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s                         # default 6 blobs, classic red\n"
            "  %(prog)s --blobs 8 --scheme blue  # 8 blobs, cosmic blue\n"
            "  %(prog)s --scheme gold --quality 50  # higher render quality\n"
            "  %(prog)s --list-schemes           # show available colour schemes\n"
            "  %(prog)s -v                       # verbose logging\n"
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--blobs", type=int, default=6, help="Number of wax blobs (3–12, default 6)")
    p.add_argument("--scheme", type=str, default="classic", help="Colour scheme")
    p.add_argument("--quality", type=int, default=35, help="Render quality %% (15–80, default 35)")
    p.add_argument("--warmup", type=float, default=18.0, help="Warmup duration in seconds")
    p.add_argument("--list-schemes", action="store_true", help="List colour schemes and exit")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("lavalamp")

    # List schemes
    if args.list_schemes:
        from .palettes import SCHEMES, list_schemes
        print("Available colour schemes:")
        for key in list_schemes():
            s = SCHEMES[key]
            contrast = f"  contrast=rgb{s.contrast}" if s.contrast else ""
            print(f"  {key:14s}  {s.name:18s}  base=rgb{s.base}  hot=rgb{s.hot}{contrast}")
        sys.exit(0)

    # Dependency check
    missing = _check_deps()
    if missing:
        print(f"ERROR: Missing packages: {', '.join(missing)}\n"
              f"Install: pip install {' '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Validate
    if not (3 <= args.blobs <= 12):
        print("ERROR: --blobs must be 3–12.", file=sys.stderr)
        sys.exit(1)

    if not (15 <= args.quality <= 80):
        print("ERROR: --quality must be 15–80.", file=sys.stderr)
        sys.exit(1)

    from .palettes import SCHEMES, get_scheme
    if args.scheme not in SCHEMES:
        from .palettes import list_schemes
        avail = ", ".join(list_schemes())
        print(f"ERROR: Unknown scheme '{args.scheme}'. Available: {avail}", file=sys.stderr)
        sys.exit(1)

    # Launch
    logger.info("Starting Lava Lamp Simulator v%s", __version__)
    logger.info("Blobs: %d, Scheme: %s, Quality: %d%%", args.blobs, args.scheme, args.quality)

    from PyQt5.QtWidgets import QApplication
    from .engine import LavaLampEngine, PhysicsParams
    from .main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Lava Lamp Simulator")
    app.setApplicationVersion(__version__)

    # Dark theme
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background: #1a1816;
            color: #c8b8a0;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            color: #c8a870;
            border: 1px solid #3a3025;
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 14px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 8px;
        }
        QPushButton {
            background: #2a2218;
            border: 1px solid #4a4035;
            border-radius: 5px;
            padding: 5px 12px;
            color: #c8b8a0;
            font-size: 12px;
        }
        QPushButton:hover {
            background: #3a3025;
            border-color: #6a5a48;
        }
        QPushButton:pressed {
            background: #5a4a35;
        }
        QPushButton:checked {
            background: #5a4a35;
            color: #f0d8b0;
        }
        QComboBox {
            background: #2a2218;
            border: 1px solid #4a4035;
            border-radius: 4px;
            padding: 4px 8px;
            color: #c8b8a0;
            font-size: 12px;
        }
        QComboBox QAbstractItemView {
            background: #2a2218;
            color: #c8b8a0;
            selection-background-color: #5a4a35;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #3a3025;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #c47830;
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:hover {
            background: #e09040;
        }
        QProgressBar {
            background: #2a2218;
            border: 1px solid #3a3025;
            border-radius: 4px;
            text-align: center;
            color: #c8a870;
            font-size: 10px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #6a3a10, stop:1 #c47830);
            border-radius: 3px;
        }
        QLabel {
            color: #b8a890;
            font-size: 12px;
        }
        QStatusBar {
            color: #8a7e6b;
            font-size: 11px;
        }
        QMenuBar {
            background: #1a1816;
            color: #c8b8a0;
        }
        QMenuBar::item:selected {
            background: #3a3025;
        }
        QMenu {
            background: #2a2218;
            color: #c8b8a0;
        }
        QMenu::item:selected {
            background: #5a4a35;
        }
        QScrollArea {
            background: #1a1816;
            border: none;
        }
        QScrollBar:vertical {
            background: #1a1816;
            width: 8px;
        }
        QScrollBar::handle:vertical {
            background: #4a4035;
            border-radius: 4px;
            min-height: 20px;
        }
    """)

    params = PhysicsParams(warmup_duration=args.warmup)
    engine = LavaLampEngine(blob_count=args.blobs, params=params)
    scheme = get_scheme(args.scheme)

    window = MainWindow(engine, scheme, render_scale=args.quality / 100)
    window.resize(680, 620)
    window.show()

    sys.exit(app.exec_())

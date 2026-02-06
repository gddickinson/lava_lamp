"""
Main window — assembles the lava lamp canvas, control panel, and menu bar.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QWidget,
)

from . import __version__
from .canvas import LavaCanvas
from .controls import ControlPanel
from .engine import LavaLampEngine, PhysicsParams
from .palettes import ColorScheme, get_scheme

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Top-level window for the Lava Lamp Simulator."""

    def __init__(
        self,
        engine: LavaLampEngine,
        scheme: ColorScheme,
        render_scale: float = 0.35,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"🫧  Lava Lamp Simulator  v{__version__}")
        self.setMinimumSize(620, 560)

        self.engine = engine
        self.canvas = LavaCanvas(engine, scheme, render_scale)
        self.controls = ControlPanel(self.canvas, engine)

        # Layout
        central = QWidget()
        self.setCentralWidget(central)
        h_layout = QHBoxLayout(central)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(12)

        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        h_layout.addWidget(self.canvas)
        h_layout.addWidget(self.controls, stretch=1)

        # Menu
        self._build_menu()

        # Status bar
        self.statusBar().showMessage("Lamp switched on — warming up…")

        # Signals
        self.controls.save_requested.connect(self._save)
        self.canvas.warmup_changed.connect(self._on_warmup)

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        save_act = QAction("&Save Image…", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self._save)
        file_menu.addAction(save_act)
        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = menu.addMenu("&Edit")
        pause_act = QAction("&Pause / Resume", self)
        pause_act.setShortcut(QKeySequence("Space"))
        pause_act.triggered.connect(self._toggle_pause)
        edit_menu.addAction(pause_act)
        reset_act = QAction("&Reset Lamp", self)
        reset_act.setShortcut(QKeySequence("Ctrl+R"))
        reset_act.triggered.connect(self._reset)
        edit_menu.addAction(reset_act)

        mix_menu = menu.addMenu("&Mix")
        stir_act = QAction("&Stir", self)
        stir_act.setShortcut(QKeySequence("S"))
        stir_act.triggered.connect(lambda: self.engine.stir(0.3))
        mix_menu.addAction(stir_act)
        shake_act = QAction("S&hake", self)
        shake_act.setShortcut(QKeySequence("H"))
        shake_act.triggered.connect(lambda: self.engine.stir(0.8))
        mix_menu.addAction(shake_act)
        heat_act = QAction("Heat &Burst", self)
        heat_act.setShortcut(QKeySequence("B"))
        heat_act.triggered.connect(lambda: self.engine.heat_burst(0.3))
        mix_menu.addAction(heat_act)

        help_menu = menu.addMenu("&Help")
        about_act = QAction("&About", self)
        about_act.triggered.connect(self._about)
        help_menu.addAction(about_act)

    def _save(self) -> None:
        img = self.canvas.get_image()
        if img is None:
            QMessageBox.warning(self, "Save Error", "No image to save yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Lava Lamp Image", "lavalamp.png",
            "PNG (*.png);;JPEG (*.jpg);;All (*)",
        )
        if path:
            if img.save(path):
                self.statusBar().showMessage(f"Saved to {path}")
            else:
                QMessageBox.critical(self, "Save Error", f"Failed to save:\n{path}")

    def _toggle_pause(self) -> None:
        self.canvas.paused = not self.canvas.paused
        self.controls._pause_btn.setChecked(self.canvas.paused)

    def _reset(self) -> None:
        self.controls._on_reset()

    def _on_warmup(self, pct: int) -> None:
        if pct < 100:
            self.statusBar().showMessage(f"Warming up… {pct}%")
        else:
            self.statusBar().showMessage("Lamp ready ✓")

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Lava Lamp Simulator",
            f"<h3>🫧 Lava Lamp Simulator v{__version__}</h3>"
            "<p>Physics-based lava lamp with metaball rendering.</p>"
            "<p>Wax blobs start cold and compact at the bottom. "
            "A heat source gradually warms them, causing thermal "
            "expansion and buoyancy-driven convection. At the top, "
            "wax cools, contracts, and sinks back down.</p>"
            "<p><b>Physics model:</b></p>"
            "<ul>"
            "<li>√-ramp buoyancy with melt threshold</li>"
            "<li>Separate horizontal / vertical drag</li>"
            "<li>Smoothstep thermal expansion</li>"
            "<li>Inter-blob repulsion and thermal separation</li>"
            "<li>Warmup phase simulating lamp switch-on</li>"
            "</ul>"
            "<p><b>Rendering:</b> metaball field Σ(rᵢ²/dᵢ²) with "
            "fake 3D lighting, specular highlights, and "
            "temperature-based colour interpolation.</p>",
        )

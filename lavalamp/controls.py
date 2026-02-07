"""
Control panel — all user-adjustable parameters for the lava lamp.

Organised into collapsible groups:
  - Colour scheme (with contrast colour options)
  - Physics (gravity, buoyancy, drag, heat/cool zones)
  - Blobs (count, radius, cold/warm ratio)
  - Mixing (stir, heat burst, shake)
  - Actions (pause, reset, save)
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .canvas import LavaCanvas
from .engine import LavaLampEngine, PhysicsParams, WAX_TYPES, WAX_TYPE_NAMES, WaxType
from .palettes import (
    SCHEMES,
    BLOB_COLOR_MODES,
    ColorScheme,
    assign_blob_colors,
    create_custom_scheme,
    get_scheme,
    list_schemes,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Labelled slider helper
# ---------------------------------------------------------------------------

class LSlider(QWidget):
    """Horizontal slider with label and readout."""

    valueChanged = pyqtSignal(int)

    def __init__(self, label, lo, hi, val, suffix="", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)

        self._lbl = QLabel(label)
        self._lbl.setFixedWidth(120)
        lay.addWidget(self._lbl)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(lo, hi)
        self._slider.setValue(val)
        lay.addWidget(self._slider, stretch=1)

        self._suffix = suffix
        self._ro = QLabel(f"{val}{suffix}")
        self._ro.setFixedWidth(48)
        self._ro.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._ro)

        self._slider.valueChanged.connect(self._changed)

    def _changed(self, v):
        self._ro.setText(f"{v}{self._suffix}")
        self.valueChanged.emit(v)

    def value(self):
        return self._slider.value()

    def setValue(self, v):
        self._slider.setValue(v)


# ---------------------------------------------------------------------------
# Control panel
# ---------------------------------------------------------------------------

class ControlPanel(QWidget):
    """Side panel with all lamp controls."""

    save_requested = pyqtSignal()

    def __init__(
        self,
        canvas: LavaCanvas,
        engine: LavaLampEngine,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self.engine = engine
        self.setFixedWidth(340)

        # ── Scroll wrapper ────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        # ══════════════════════════════════════════════════════════════════
        # COLOUR SCHEME
        # ══════════════════════════════════════════════════════════════════
        color_group = QGroupBox("Colour Scheme")
        cg = QVBoxLayout(color_group)

        self._scheme_combo = QComboBox()
        for key in list_schemes():
            self._scheme_combo.addItem(SCHEMES[key].name, key)
        self._scheme_combo.currentIndexChanged.connect(self._on_scheme_changed)
        cg.addWidget(self._scheme_combo)

        # Swatches
        self._swatch_layout = QHBoxLayout()
        cg.addLayout(self._swatch_layout)

        # ── Contrast colour ───────────────────────────────────────────────
        cg.addWidget(QLabel("Contrast Wax Colour:"))

        self._contrast_combo = QComboBox()
        self._contrast_combo.addItems([
            "None",
            "Complementary",
            "Triadic",
            "Split Complementary",
            "Analogous",
            "Custom…",
        ])
        self._contrast_combo.currentIndexChanged.connect(self._on_contrast_mode)
        cg.addWidget(self._contrast_combo)

        self._contrast_swatch = QWidget()
        self._contrast_swatch.setFixedSize(20, 20)
        self._contrast_swatch.setStyleSheet(
            "background: #333; border-radius: 10px; border: 1px solid #555;"
        )
        contrast_row = QHBoxLayout()
        contrast_row.addWidget(QLabel("Contrast:"))
        contrast_row.addWidget(self._contrast_swatch)
        self._pick_contrast_btn = QPushButton("Pick…")
        self._pick_contrast_btn.setFixedWidth(50)
        self._pick_contrast_btn.clicked.connect(self._pick_contrast_color)
        self._pick_contrast_btn.setEnabled(False)
        contrast_row.addWidget(self._pick_contrast_btn)
        contrast_row.addStretch()
        cg.addLayout(contrast_row)

        # ── Custom base colour ────────────────────────────────────────────
        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Custom Base:"))
        self._base_swatch = QWidget()
        self._base_swatch.setFixedSize(20, 20)
        self._base_swatch.setStyleSheet(
            "background: #b41e0a; border-radius: 10px; border: 1px solid #555;"
        )
        base_row.addWidget(self._base_swatch)
        self._pick_base_btn = QPushButton("Pick…")
        self._pick_base_btn.setFixedWidth(50)
        self._pick_base_btn.clicked.connect(self._pick_base_color)
        base_row.addWidget(self._pick_base_btn)
        base_row.addStretch()
        cg.addLayout(base_row)

        layout.addWidget(color_group)

        # ══════════════════════════════════════════════════════════════════
        # PHYSICS
        # ══════════════════════════════════════════════════════════════════
        phys_group = QGroupBox("Physics")
        pg = QVBoxLayout(phys_group)

        self._heat_slider = LSlider("Heat", 10, 250, 100, "%")
        self._heat_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "heat_strength", v / 100)
        )
        pg.addWidget(self._heat_slider)

        self._flow_slider = LSlider("Flow Speed", 10, 300, 100, "%")
        self._flow_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "flow_speed", v / 100)
        )
        pg.addWidget(self._flow_slider)

        self._gravity_slider = LSlider("Gravity", 5, 50, 18, "")
        self._gravity_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "gravity", v / 100)
        )
        pg.addWidget(self._gravity_slider)

        self._buoyancy_slider = LSlider("Buoyancy", 20, 150, 65, "")
        self._buoyancy_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "buoyancy_max", v / 100)
        )
        pg.addWidget(self._buoyancy_slider)

        self._vdrag_slider = LSlider("Vertical Drag", 5, 50, 16, "")
        self._vdrag_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "v_drag", v / 10)
        )
        pg.addWidget(self._vdrag_slider)

        self._hdrag_slider = LSlider("Horiz. Drag", 5, 50, 25, "")
        self._hdrag_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "h_drag", v / 10)
        )
        pg.addWidget(self._hdrag_slider)

        self._melt_slider = LSlider("Melt Temp", 10, 60, 28, "%")
        self._melt_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "melt_temp", v / 100)
        )
        pg.addWidget(self._melt_slider)

        self._warmup_slider = LSlider("Warmup Time", 3, 60, 18, "s")
        self._warmup_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "warmup_duration", float(v))
        )
        pg.addWidget(self._warmup_slider)

        # ── Displacement (medium-range interaction) ───────────────────────
        pg.addWidget(QLabel("─ Displacement ─"))

        self._displace_range_slider = LSlider("Displace Range", 10, 35, 18, "")
        self._displace_range_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "displacement_range", v / 10)
        )
        pg.addWidget(self._displace_range_slider)

        self._displace_str_slider = LSlider("Displace Force", 0, 20, 4, "")
        self._displace_str_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "displacement_strength", v / 10)
        )
        pg.addWidget(self._displace_str_slider)

        self._deflect_slider = LSlider("Approach Deflect", 0, 20, 6, "")
        self._deflect_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "approach_deflection", v / 10)
        )
        pg.addWidget(self._deflect_slider)

        layout.addWidget(phys_group)

        # ══════════════════════════════════════════════════════════════════
        # BLOBS
        # ══════════════════════════════════════════════════════════════════
        blob_group = QGroupBox("Wax Blobs")
        bg = QVBoxLayout(blob_group)

        self._count_slider = LSlider("Count", 3, 12, 6)
        self._count_slider.valueChanged.connect(self._on_blob_count)
        bg.addWidget(self._count_slider)

        self._coldrad_slider = LSlider("Cold Size", 15, 60, 35, "%")
        self._coldrad_slider.valueChanged.connect(self._on_cold_radius)
        bg.addWidget(self._coldrad_slider)

        self._repulsion_slider = LSlider("Repulsion", 5, 40, 15, "")
        self._repulsion_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "repulsion_strength", v / 10)
        )
        bg.addWidget(self._repulsion_slider)

        self._thermal_sep_slider = LSlider("Thermal Sep.", 0, 20, 6, "")
        self._thermal_sep_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "thermal_separation", v / 10)
        )
        bg.addWidget(self._thermal_sep_slider)

        # ── Blob colouring mode ───────────────────────────────────────────
        bg.addWidget(QLabel("Blob Colouring:"))
        self._blob_color_combo = QComboBox()
        mode_labels = {
            "uniform": "Uniform (all same)",
            "contrast": "Contrast (alternating)",
            "rainbow": "Rainbow",
            "warm_cool": "Warm & Cool",
            "random": "Random",
            "gradient": "Gradient",
        }
        for mode in BLOB_COLOR_MODES:
            self._blob_color_combo.addItem(mode_labels.get(mode, mode), mode)
        self._blob_color_combo.currentIndexChanged.connect(self._on_blob_color_mode)
        bg.addWidget(self._blob_color_combo)

        # Blob colour swatches
        self._blob_swatch_layout = QHBoxLayout()
        bg.addLayout(self._blob_swatch_layout)

        layout.addWidget(blob_group)

        # ══════════════════════════════════════════════════════════════════
        # INDIVIDUAL BLOB EDITOR
        # ══════════════════════════════════════════════════════════════════
        edit_group = QGroupBox("Edit Individual Blob")
        eg = QVBoxLayout(edit_group)

        # Blob selector
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Select:"))
        self._blob_select = QComboBox()
        self._blob_select.currentIndexChanged.connect(self._on_blob_selected)
        sel_row.addWidget(self._blob_select, stretch=1)
        eg.addLayout(sel_row)

        # Wax type preset
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Wax Type:"))
        self._wax_type_combo = QComboBox()
        wax_labels = {
            "standard": "Standard",
            "heavy": "Heavy (dense, slow to heat)",
            "light": "Light (buoyant, quick to heat)",
            "sluggish": "Sluggish (high viscosity)",
            "volatile": "Volatile (fast, expands a lot)",
            "giant": "Giant Globule (big & slow)",
        }
        for key in WAX_TYPE_NAMES:
            self._wax_type_combo.addItem(wax_labels.get(key, key), key)
        self._wax_type_combo.currentIndexChanged.connect(self._on_wax_type_changed)
        type_row.addWidget(self._wax_type_combo, stretch=1)
        eg.addLayout(type_row)

        # Custom property sliders
        eg.addWidget(QLabel("Fine-tune:"))

        self._density_slider = LSlider("Density", 3, 25, 10, "")
        self._density_slider.valueChanged.connect(self._on_blob_prop_changed)
        eg.addWidget(self._density_slider)

        self._heat_sens_slider = LSlider("Heat Sens.", 2, 30, 10, "")
        self._heat_sens_slider.valueChanged.connect(self._on_blob_prop_changed)
        eg.addWidget(self._heat_sens_slider)

        self._viscosity_slider = LSlider("Viscosity", 2, 30, 10, "")
        self._viscosity_slider.valueChanged.connect(self._on_blob_prop_changed)
        eg.addWidget(self._viscosity_slider)

        self._expansion_slider = LSlider("Expansion", 3, 25, 10, "")
        self._expansion_slider.valueChanged.connect(self._on_blob_prop_changed)
        eg.addWidget(self._expansion_slider)

        # Blob status readout
        self._blob_status = QLabel("—")
        self._blob_status.setWordWrap(True)
        self._blob_status.setStyleSheet("color: #888; font-size: 10px;")
        eg.addWidget(self._blob_status)

        # Apply to all button
        apply_all_btn = QPushButton("Apply Type to All Blobs")
        apply_all_btn.clicked.connect(self._apply_wax_to_all)
        eg.addWidget(apply_all_btn)

        layout.addWidget(edit_group)

        # ══════════════════════════════════════════════════════════════════
        # RENDERING
        # ══════════════════════════════════════════════════════════════════
        render_group = QGroupBox("Rendering")
        rg = QVBoxLayout(render_group)

        self._quality_slider = LSlider("Quality", 15, 80, 35, "%")
        self._quality_slider.valueChanged.connect(
            lambda v: self.canvas.set_render_scale(v / 100)
        )
        rg.addWidget(self._quality_slider)

        layout.addWidget(render_group)

        # ══════════════════════════════════════════════════════════════════
        # MIXING
        # ══════════════════════════════════════════════════════════════════
        mix_group = QGroupBox("Mixing")
        mix_vbox = QVBoxLayout(mix_group)

        mg = QGridLayout()

        stir_btn = QPushButton("🌀  Stir")
        stir_btn.clicked.connect(lambda: self.engine.stir(0.3))
        mg.addWidget(stir_btn, 0, 0)

        shake_btn = QPushButton("💥  Shake")
        shake_btn.clicked.connect(lambda: self.engine.stir(0.8))
        mg.addWidget(shake_btn, 0, 1)

        heat_btn = QPushButton("🔥  Heat Burst")
        heat_btn.clicked.connect(lambda: self.engine.heat_burst(0.3))
        mg.addWidget(heat_btn, 1, 0)

        cool_btn = QPushButton("❄  Cool Down")
        cool_btn.clicked.connect(self._cool_down)
        mg.addWidget(cool_btn, 1, 1)

        mix_vbox.addLayout(mg)

        # ── Continuous perturbation ───────────────────────────────────────
        mix_vbox.addWidget(QLabel("─ Continuous ─"))

        self._cont_stir_slider = LSlider("Stir Current", 0, 100, 0, "%")
        self._cont_stir_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "continuous_stir", v / 100)
        )
        mix_vbox.addWidget(self._cont_stir_slider)

        self._stir_speed_slider = LSlider("Stir Speed", 10, 300, 100, "%")
        self._stir_speed_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "stir_speed", v / 100)
        )
        mix_vbox.addWidget(self._stir_speed_slider)

        self._cont_shake_slider = LSlider("Turbulence", 0, 100, 0, "%")
        self._cont_shake_slider.valueChanged.connect(
            lambda v: setattr(self.engine.params, "continuous_shake", v / 100)
        )
        mix_vbox.addWidget(self._cont_shake_slider)

        layout.addWidget(mix_group)

        # ══════════════════════════════════════════════════════════════════
        # WARMUP STATUS
        # ══════════════════════════════════════════════════════════════════
        self._warmup_bar = QProgressBar()
        self._warmup_bar.setRange(0, 100)
        self._warmup_bar.setValue(0)
        self._warmup_bar.setFormat("Warming up… %p%")
        self._warmup_bar.setFixedHeight(18)
        layout.addWidget(self._warmup_bar)

        # ══════════════════════════════════════════════════════════════════
        # ACTIONS
        # ══════════════════════════════════════════════════════════════════
        action_group = QGroupBox("Actions")
        ag = QGridLayout(action_group)

        self._pause_btn = QPushButton("⏸  Pause")
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._on_pause)
        ag.addWidget(self._pause_btn, 0, 0)

        reset_btn = QPushButton("↻  Reset")
        reset_btn.clicked.connect(self._on_reset)
        ag.addWidget(reset_btn, 0, 1)

        save_btn = QPushButton("↓  Save PNG")
        save_btn.clicked.connect(self.save_requested.emit)
        ag.addWidget(save_btn, 1, 0, 1, 2)

        layout.addWidget(action_group)

        # ── Status ────────────────────────────────────────────────────────
        self._status = QLabel("Ready — drag on the lamp to stir")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        layout.addWidget(self._status)

        # ── Help ──────────────────────────────────────────────────────────
        help_lbl = QLabel(
            "<b>How it works:</b><br>"
            "Wax blobs start cold and compact at the bottom. The heat source "
            "gradually warms them, causing thermal expansion and buoyancy. "
            "Hot blobs rise, cool at the top, contract, and sink back down.<br><br>"
            "<b>Interactions:</b><br>"
            "• <b>Drag</b> on the lamp to stir the wax<br>"
            "• <b>Stir / Shake</b> buttons apply random forces<br>"
            "• <b>Heat Burst</b> instantly warms all blobs<br>"
            "• <b>Contrast colours</b> alternate between blobs<br><br>"
            "<i>Rendering: metaball field Σ(r²/d²) with fake 3D "
            "lighting and temperature-based colouring.</i>"
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet(
            "color: #777; font-size: 11px; padding: 8px; "
            "background: #1a1816; border-radius: 4px;"
        )
        layout.addWidget(help_lbl)

        layout.addStretch()

        # ── wire signals ──────────────────────────────────────────────────
        canvas.warmup_changed.connect(self._on_warmup)
        canvas.fps_changed.connect(self._on_fps)

        # ── initial state ─────────────────────────────────────────────────
        self._current_custom_base: Optional[tuple] = None
        self._current_contrast: Optional[tuple] = None
        self._contrast_mode = "none"
        self._blob_color_mode = "uniform"
        self._update_swatches()
        self._update_blob_swatches()
        self._refresh_blob_selector()

    # ── colour slots ──────────────────────────────────────────────────────

    def _on_scheme_changed(self, idx: int) -> None:
        key = self._scheme_combo.currentData()
        try:
            scheme = get_scheme(key)
            self.canvas.set_scheme(scheme)
            self._update_swatches()
            self._current_custom_base = None
            self._apply_blob_colors()
        except KeyError as e:
            logger.error("Scheme error: %s", e)

    def _update_swatches(self) -> None:
        while self._swatch_layout.count():
            item = self._swatch_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scheme = self.canvas.scheme
        for c in [scheme.base, scheme.hot]:
            sw = QWidget()
            sw.setFixedSize(20, 20)
            sw.setStyleSheet(
                f"background: rgb({c[0]},{c[1]},{c[2]}); "
                "border-radius: 10px; border: 1px solid #555;"
            )
            self._swatch_layout.addWidget(sw)

        if scheme.contrast:
            c = scheme.contrast
            sw = QWidget()
            sw.setFixedSize(20, 20)
            sw.setStyleSheet(
                f"background: rgb({c[0]},{c[1]},{c[2]}); "
                "border-radius: 10px; border: 2px solid #fff;"
            )
            self._swatch_layout.addWidget(sw)

        # Liquid swatch
        c = scheme.liquid
        sw = QWidget()
        sw.setFixedSize(20, 20)
        sw.setStyleSheet(
            f"background: rgb({c[0]},{c[1]},{c[2]}); "
            "border-radius: 10px; border: 1px solid #555;"
        )
        self._swatch_layout.addWidget(sw)
        self._swatch_layout.addStretch()

        # Update contrast swatch
        if scheme.contrast:
            cc = scheme.contrast
            self._contrast_swatch.setStyleSheet(
                f"background: rgb({cc[0]},{cc[1]},{cc[2]}); "
                "border-radius: 10px; border: 1px solid #fff;"
            )
        else:
            self._contrast_swatch.setStyleSheet(
                "background: #333; border-radius: 10px; border: 1px solid #555;"
            )

        # Update base swatch
        bb = scheme.base
        self._base_swatch.setStyleSheet(
            f"background: rgb({bb[0]},{bb[1]},{bb[2]}); "
            "border-radius: 10px; border: 1px solid #555;"
        )

    def _on_contrast_mode(self, idx: int) -> None:
        modes = ["none", "complementary", "triadic", "split", "analogous", "custom"]
        self._contrast_mode = modes[idx] if idx < len(modes) else "none"
        self._pick_contrast_btn.setEnabled(self._contrast_mode == "custom")
        self._rebuild_scheme()

    def _pick_contrast_color(self) -> None:
        color = QColorDialog.getColor(QColor(100, 200, 100), self, "Pick Contrast Colour")
        if color.isValid():
            self._current_contrast = (color.red(), color.green(), color.blue())
            self._rebuild_scheme()

    def _pick_base_color(self) -> None:
        current = self.canvas.scheme.base
        color = QColorDialog.getColor(
            QColor(*current), self, "Pick Base Wax Colour"
        )
        if color.isValid():
            self._current_custom_base = (color.red(), color.green(), color.blue())
            self._rebuild_scheme()

    def _rebuild_scheme(self) -> None:
        """Rebuild the colour scheme from current settings."""
        if self._current_custom_base:
            base = self._current_custom_base
        else:
            key = self._scheme_combo.currentData()
            base = SCHEMES.get(key, SCHEMES["classic"]).base

        contrast = self._current_contrast if self._contrast_mode == "custom" else None

        scheme = create_custom_scheme(
            name="Custom",
            base=base,
            contrast=contrast,
            contrast_mode=self._contrast_mode,
        )
        self.canvas.set_scheme(scheme)
        self._update_swatches()
        self._apply_blob_colors()

    # ── physics slots ─────────────────────────────────────────────────────

    def _on_blob_count(self, count: int) -> None:
        self.engine.reset(count)
        self._apply_blob_colors()
        self._refresh_blob_selector()

    def _on_blob_color_mode(self, idx: int) -> None:
        mode = self._blob_color_combo.currentData()
        self._blob_color_mode = mode
        self._apply_blob_colors()

    def _apply_blob_colors(self) -> None:
        """Assign per-blob colours based on current mode and scheme."""
        mode = getattr(self, "_blob_color_mode", "uniform")
        scheme = self.canvas.scheme
        blobs = self.engine.blobs
        colors = assign_blob_colors(len(blobs), scheme, mode)
        for b, (base_c, hot_c) in zip(blobs, colors):
            if mode == "uniform":
                b.color = None       # use scheme default
                b.hot_color = None
            else:
                b.color = base_c
                b.hot_color = hot_c
        self._update_blob_swatches()

    def _update_blob_swatches(self) -> None:
        """Show small colour dots for each blob's assigned colour."""
        while self._blob_swatch_layout.count():
            item = self._blob_swatch_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scheme = self.canvas.scheme
        for b in self.engine.blobs:
            c = b.color or scheme.base
            sw = QWidget()
            sw.setFixedSize(14, 14)
            sw.setStyleSheet(
                f"background: rgb({c[0]},{c[1]},{c[2]}); "
                "border-radius: 7px; border: 1px solid #555;"
            )
            self._blob_swatch_layout.addWidget(sw)
        self._blob_swatch_layout.addStretch()

    def _on_cold_radius(self, pct: int) -> None:
        frac = pct / 100
        self.engine.params.cold_radius_fraction = frac
        for b in self.engine.blobs:
            b.cold_radius = b.warm_radius * frac

    def _cool_down(self) -> None:
        for b in self.engine.blobs:
            b.temperature = max(0, b.temperature - 0.4)

    # ── blob editor slots ─────────────────────────────────────────────────

    def _refresh_blob_selector(self) -> None:
        """Rebuild the blob selector combo from current engine state."""
        self._blob_select.blockSignals(True)
        self._blob_select.clear()
        for i, b in enumerate(self.engine.blobs):
            wax_name = b.wax.name if b.wax else "Standard"
            self._blob_select.addItem(f"{b.label} ({wax_name})", i)
        self._blob_select.blockSignals(False)
        if self._blob_select.count() > 0:
            self._blob_select.setCurrentIndex(0)
            self._on_blob_selected(0)

    def _on_blob_selected(self, idx: int) -> None:
        """Load the selected blob's wax properties into the sliders."""
        if idx < 0 or idx >= len(self.engine.blobs):
            return
        b = self.engine.blobs[idx]
        w = b.wax

        # Block signals while updating sliders to avoid feedback
        for sl in (self._density_slider, self._heat_sens_slider,
                   self._viscosity_slider, self._expansion_slider):
            sl.blockSignals(True)

        self._density_slider.setValue(int(w.density * 10))
        self._heat_sens_slider.setValue(int(w.heat_sensitivity * 10))
        self._viscosity_slider.setValue(int(w.viscosity * 10))
        self._expansion_slider.setValue(int(w.expansion * 10))

        for sl in (self._density_slider, self._heat_sens_slider,
                   self._viscosity_slider, self._expansion_slider):
            sl.blockSignals(False)

        # Match wax type combo to current type (if preset)
        self._wax_type_combo.blockSignals(True)
        matched = False
        for ki, key in enumerate(WAX_TYPE_NAMES):
            wt = WAX_TYPES[key]
            if (abs(w.density - wt.density) < 0.01 and
                abs(w.heat_sensitivity - wt.heat_sensitivity) < 0.01 and
                abs(w.viscosity - wt.viscosity) < 0.01 and
                abs(w.expansion - wt.expansion) < 0.01):
                self._wax_type_combo.setCurrentIndex(ki)
                matched = True
                break
        if not matched:
            self._wax_type_combo.setCurrentIndex(0)
        self._wax_type_combo.blockSignals(False)

        self._update_blob_status(b)

    def _on_wax_type_changed(self, idx: int) -> None:
        """Apply a wax type preset to the selected blob."""
        blob_idx = self._blob_select.currentIndex()
        if blob_idx < 0 or blob_idx >= len(self.engine.blobs):
            return
        key = self._wax_type_combo.currentData()
        if key and key in WAX_TYPES:
            self.engine.set_blob_wax(blob_idx, key)
            # Refresh sliders
            self._on_blob_selected(blob_idx)
            self._refresh_blob_selector_label(blob_idx)

    def _on_blob_prop_changed(self, _val: int = 0) -> None:
        """Apply fine-tuned custom wax properties to the selected blob."""
        blob_idx = self._blob_select.currentIndex()
        if blob_idx < 0 or blob_idx >= len(self.engine.blobs):
            return
        self.engine.set_blob_wax_custom(
            blob_idx,
            density=self._density_slider.value() / 10,
            heat_sensitivity=self._heat_sens_slider.value() / 10,
            viscosity=self._viscosity_slider.value() / 10,
            expansion=self._expansion_slider.value() / 10,
        )
        self._refresh_blob_selector_label(blob_idx)
        self._update_blob_status(self.engine.blobs[blob_idx])

    def _refresh_blob_selector_label(self, idx: int) -> None:
        """Update just one entry in the blob selector combo."""
        if 0 <= idx < len(self.engine.blobs):
            b = self.engine.blobs[idx]
            wax_name = b.wax.name if b.wax else "Standard"
            self._blob_select.setItemText(idx, f"{b.label} ({wax_name})")

    def _update_blob_status(self, b) -> None:
        """Show blob's live state."""
        w = b.wax
        self._blob_status.setText(
            f"<b>{b.label}</b> — {w.name}<br>"
            f"density={w.density:.1f}  heat={w.heat_sensitivity:.1f}  "
            f"visc={w.viscosity:.1f}  expand={w.expansion:.1f}<br>"
            f"temp={b.temperature:.2f}  radius={b.radius:.3f}  "
            f"{'detached' if b.detached else 'grounded'}"
        )

    def _apply_wax_to_all(self) -> None:
        """Apply the current editor's wax type to every blob."""
        blob_idx = self._blob_select.currentIndex()
        if blob_idx < 0 or blob_idx >= len(self.engine.blobs):
            return
        source_wax = self.engine.blobs[blob_idx].wax
        for b in self.engine.blobs:
            b.wax = WaxType(
                name=source_wax.name,
                density=source_wax.density,
                heat_sensitivity=source_wax.heat_sensitivity,
                viscosity=source_wax.viscosity,
                expansion=source_wax.expansion,
            )
        self._refresh_blob_selector()

    # ── action slots ──────────────────────────────────────────────────────

    def _on_pause(self, checked: bool) -> None:
        self.canvas.paused = checked
        self._pause_btn.setText("▶  Play" if checked else "⏸  Pause")

    def _on_reset(self) -> None:
        count = self._count_slider.value()
        self.engine.reset(count)
        self._warmup_bar.setValue(0)
        self._apply_blob_colors()
        self._refresh_blob_selector()

    def _on_warmup(self, pct: int) -> None:
        self._warmup_bar.setValue(pct)
        if pct >= 100:
            self._warmup_bar.setFormat("Lamp Ready ✓")
        else:
            self._warmup_bar.setFormat("Warming up… %p%")

    def _on_fps(self, fps: float) -> None:
        n = len(self.engine.blobs)
        self._status.setText(
            f"{n} blobs  •  {fps:.0f} fps  •  "
            f"warmup {self.engine.warmup_fraction*100:.0f}%"
        )

    def current_scheme(self) -> ColorScheme:
        return self.canvas.scheme

"""
Lava lamp canvas widget — animated display with QTimer-driven rendering.

Rendering happens in the main thread (numpy is fast enough at 35% res)
and updates at ~30 fps.  Mouse dragging applies a stir force.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PyQt5.QtCore import QPointF, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QWidget

from .engine import LavaLampEngine
from .palettes import ColorScheme, get_scheme
from .renderer import render_frame

logger = logging.getLogger(__name__)


class LavaCanvas(QWidget):
    """Animated lava lamp display.

    Signals:
        warmup_changed(int):       warmup percentage 0–100
        fps_changed(float):        current rendering FPS
    """

    warmup_changed = pyqtSignal(int)
    fps_changed = pyqtSignal(float)

    LAMP_W = 220
    LAMP_H = 520

    def __init__(
        self,
        engine: LavaLampEngine,
        scheme: ColorScheme,
        render_scale: float = 0.35,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.scheme = scheme
        self.render_scale = render_scale
        self._pixmap: Optional[QPixmap] = None
        self._paused = False

        # Timing
        self._last_time = time.perf_counter()
        self._frame_count = 0
        self._fps_accum = 0.0
        self._last_warmup_pct = -1

        # Mouse interaction
        self._dragging = False
        self._last_mouse: Optional[QPointF] = None

        self.setMinimumSize(180, 400)
        self.setFixedWidth(self.LAMP_W + 20)

        # Animation timer (~30 fps)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ── properties ────────────────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, val: bool) -> None:
        self._paused = val
        if not val:
            self._last_time = time.perf_counter()

    def set_scheme(self, scheme: ColorScheme) -> None:
        self.scheme = scheme

    def set_render_scale(self, scale: float) -> None:
        self.render_scale = max(0.15, min(1.0, scale))

    # ── animation loop ────────────────────────────────────────────────────

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now

        # Physics
        if not self._paused:
            self.engine.step(dt)

        # Render
        img = render_frame(
            self.engine, self.scheme,
            self.LAMP_W, self.LAMP_H,
            self.render_scale,
        )

        # Convert to QPixmap
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGBA8888).copy()
        self._pixmap = QPixmap.fromImage(qimg).scaled(
            self.LAMP_W, self.LAMP_H,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        self.update()

        # FPS tracking
        self._frame_count += 1
        self._fps_accum += dt
        if self._fps_accum >= 1.0:
            fps = self._frame_count / self._fps_accum
            self.fps_changed.emit(fps)
            self._frame_count = 0
            self._fps_accum = 0.0

        # Warmup progress
        pct = int(self.engine.warmup_fraction * 100)
        if pct != self._last_warmup_pct:
            self._last_warmup_pct = pct
            self.warmup_changed.emit(pct)

    # ── painting ──────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Dark background
        painter.fillRect(self.rect(), QColor(10, 8, 6))

        if self._pixmap:
            # Centre the lamp
            x_off = (self.width() - self.LAMP_W) // 2
            y_off = (self.height() - self.LAMP_H) // 2
            painter.drawPixmap(x_off, y_off, self._pixmap)

        # Top cap
        cap_w = int(self.LAMP_W * 0.76)
        cap_h = max(6, int(self.LAMP_H * 0.025))
        x_off = (self.width() - self.LAMP_W) // 2
        y_off_base = (self.height() - self.LAMP_H) // 2
        cap_x = x_off + (self.LAMP_W - cap_w) // 2
        painter.setBrush(QColor(50, 45, 40))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(cap_x, y_off_base, cap_w, cap_h)

        # Bottom cap
        bot_w = int(self.LAMP_W * 0.84)
        bot_h = max(8, int(self.LAMP_H * 0.03))
        bot_x = x_off + (self.LAMP_W - bot_w) // 2
        bot_y = y_off_base + self.LAMP_H - bot_h
        painter.setBrush(QColor(35, 30, 25))
        painter.drawEllipse(bot_x, bot_y, bot_w, bot_h)

        # Heat glow
        warmup = self.engine.warmup_fraction
        if warmup > 0.05:
            glow_alpha = int(min(60, warmup * 60))
            base = self.scheme.base
            glow_color = QColor(base[0], base[1], base[2], glow_alpha)
            painter.setBrush(glow_color)
            glow_w = int(self.LAMP_W * 0.7)
            glow_h = int(self.LAMP_H * 0.06)
            glow_x = x_off + (self.LAMP_W - glow_w) // 2
            glow_y = bot_y - glow_h // 2
            painter.drawEllipse(glow_x, glow_y, glow_w, glow_h)

        if self._paused:
            painter.setPen(QColor(200, 180, 150, 180))
            painter.drawText(self.rect(), Qt.AlignCenter, "⏸ PAUSED")

        painter.end()

    # ── mouse interaction (stirring) ──────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse = QPointF(event.pos())

    def mouseMoveEvent(self, event):
        if not self._dragging or self._last_mouse is None:
            return
        pos = QPointF(event.pos())
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 3:
            # Apply lateral force to nearby blobs
            strength = min(0.5, dist * 0.005)
            self.engine.stir(strength)
        self._last_mouse = pos

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._last_mouse = None

    # ── save ──────────────────────────────────────────────────────────────

    def get_image(self) -> Optional[QImage]:
        if self._pixmap:
            return self._pixmap.toImage()
        return None

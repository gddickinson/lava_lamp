"""
Unit tests for the lava lamp renderer.
"""

import unittest

import numpy as np

from lavalamp.engine import LavaLampEngine, PhysicsParams
from lavalamp.palettes import get_scheme
from lavalamp.renderer import lamp_radius, render_frame, upscale_image


class TestLampRadius(unittest.TestCase):
    """Tests for the lamp silhouette function."""

    def test_returns_array(self):
        y = np.array([0.0, 0.5, 1.0])
        r = lamp_radius(y)
        self.assertEqual(r.shape, (3,))

    def test_positive_everywhere(self):
        y = np.linspace(0, 1, 50)
        r = lamp_radius(y)
        self.assertTrue(np.all(r > 0), "Lamp radius should be positive everywhere")

    def test_tapered_at_extremes(self):
        r_middle = lamp_radius(np.array([0.5]))[0]
        r_top = lamp_radius(np.array([0.99]))[0]
        r_bottom = lamp_radius(np.array([0.01]))[0]
        self.assertGreater(r_middle, r_top)
        self.assertGreater(r_middle, r_bottom)


class TestRenderFrame(unittest.TestCase):
    """Tests for the main render function."""

    def setUp(self):
        self.engine = LavaLampEngine(blob_count=3, seed=42)
        self.scheme = get_scheme("classic")

    def test_output_shape(self):
        img = render_frame(self.engine, self.scheme, width=40, height=80, render_scale=1.0)
        self.assertEqual(img.shape, (80, 40, 4))

    def test_output_dtype(self):
        img = render_frame(self.engine, self.scheme, width=40, height=80, render_scale=1.0)
        self.assertEqual(img.dtype, np.uint8)

    def test_rgba_range(self):
        img = render_frame(self.engine, self.scheme, width=40, height=80, render_scale=1.0)
        self.assertTrue(np.all(img >= 0))
        self.assertTrue(np.all(img <= 255))

    def test_has_non_transparent_pixels(self):
        """The lamp interior should have opaque pixels."""
        # Run a few steps so blobs move
        for _ in range(10):
            self.engine.step(0.016)
        img = render_frame(self.engine, self.scheme, width=60, height=120, render_scale=1.0)
        opaque_count = np.sum(img[:, :, 3] == 255)
        self.assertGreater(opaque_count, 0, "Image should have opaque pixels inside lamp")

    def test_low_render_scale(self):
        img = render_frame(self.engine, self.scheme, width=100, height=200, render_scale=0.2)
        # Output is at reduced resolution, but the shape is that of the reduced res
        h, w = img.shape[:2]
        self.assertLessEqual(h, 200)
        self.assertLessEqual(w, 100)

    def test_after_warmup(self):
        """After full warmup, rendering should still produce valid output."""
        self.engine.warmup_time = self.engine.params.warmup_duration + 1
        for _ in range(50):
            self.engine.step(0.016)
        img = render_frame(self.engine, self.scheme, width=40, height=80, render_scale=1.0)
        self.assertEqual(img.shape[2], 4)


class TestUpscaleImage(unittest.TestCase):
    """Tests for the upscale helper."""

    def test_identity(self):
        img = np.zeros((10, 5, 4), dtype=np.uint8)
        result = upscale_image(img, 5, 10)
        self.assertEqual(result.shape, (10, 5, 4))

    def test_upscale(self):
        img = np.ones((10, 5, 4), dtype=np.uint8) * 128
        result = upscale_image(img, 20, 40)
        self.assertEqual(result.shape[:2], (40, 20))


if __name__ == "__main__":
    unittest.main()

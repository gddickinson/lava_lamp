"""
Unit tests for the lava lamp physics engine.
"""

import math
import unittest

from lavalamp.engine import (
    Blob, LavaLampEngine, PhysicsParams, WaxType,
    WAX_TYPES, WAX_TYPE_NAMES,
)


class TestWaxType(unittest.TestCase):
    """Tests for WaxType dataclass."""

    def test_default_wax(self):
        w = WaxType()
        self.assertEqual(w.name, "Standard")
        self.assertAlmostEqual(w.density, 1.0)
        self.assertAlmostEqual(w.viscosity, 1.0)

    def test_builtin_types_exist(self):
        self.assertIn("standard", WAX_TYPES)
        self.assertIn("heavy", WAX_TYPES)
        self.assertIn("light", WAX_TYPES)
        self.assertIn("volatile", WAX_TYPES)

    def test_heavy_wax_properties(self):
        heavy = WAX_TYPES["heavy"]
        self.assertGreater(heavy.density, 1.0)
        self.assertLess(heavy.heat_sensitivity, 1.0)


class TestBlob(unittest.TestCase):
    """Tests for Blob dataclass."""

    def test_default_blob(self):
        b = Blob()
        self.assertAlmostEqual(b.x, 0.0)
        self.assertAlmostEqual(b.y, 0.0)
        self.assertFalse(b.detached)

    def test_post_init_sets_cold_radius(self):
        b = Blob(warm_radius=0.12)
        expected = 0.12 * 0.35
        self.assertAlmostEqual(b.cold_radius, expected, places=5)
        self.assertAlmostEqual(b.radius, expected, places=5)

    def test_mass_from_radius(self):
        b = Blob(warm_radius=0.2)
        self.assertAlmostEqual(b.mass, 0.2**3, places=8)


class TestPhysicsParams(unittest.TestCase):
    """Tests for PhysicsParams defaults."""

    def test_defaults(self):
        p = PhysicsParams()
        self.assertGreater(p.gravity, 0)
        self.assertGreater(p.buoyancy_max, 0)
        self.assertGreater(p.heat_zone, 0)
        self.assertLess(p.heat_zone, p.cool_zone)

    def test_warmup_duration_positive(self):
        p = PhysicsParams()
        self.assertGreater(p.warmup_duration, 0)


class TestLavaLampEngine(unittest.TestCase):
    """Tests for the LavaLampEngine simulation."""

    def setUp(self):
        self.engine = LavaLampEngine(blob_count=4, seed=42)

    def test_blob_count(self):
        # +1 for the pool blob
        self.assertEqual(len(self.engine.blobs), 5)
        self.assertEqual(self.engine.blob_count, 4)

    def test_reset(self):
        self.engine.step(0.01)
        self.engine.reset(6)
        self.assertEqual(len(self.engine.blobs), 7)
        self.assertAlmostEqual(self.engine.warmup_time, 0.0)

    def test_step_advances_time(self):
        self.engine.step(0.016)
        self.assertGreater(self.engine.warmup_time, 0)

    def test_blobs_stay_in_bounds(self):
        """After many steps, blobs should remain within the lamp."""
        for _ in range(200):
            self.engine.step(0.016)

        for b in self.engine.blobs:
            hr = math.sqrt(b.x**2 + b.z**2)
            self.assertLessEqual(hr, self.engine.params.wall_radius + 0.1,
                                 f"Blob {b.label} escaped horizontally")
            self.assertGreaterEqual(b.y, -0.1,
                                    f"Blob {b.label} fell below floor")
            self.assertLessEqual(b.y, 1.1,
                                 f"Blob {b.label} flew above ceiling")

    def test_warmup_fraction(self):
        self.assertAlmostEqual(self.engine.warmup_fraction, 0.0)
        # Simulate enough time to complete warmup
        for _ in range(2000):
            self.engine.step(0.016)
        self.assertAlmostEqual(self.engine.warmup_fraction, 1.0)

    def test_stir_changes_velocity(self):
        vx_before = [b.vx for b in self.engine.blobs]
        self.engine.stir(0.5)
        vx_after = [b.vx for b in self.engine.blobs]
        # At least some blobs should have changed velocity
        changed = sum(1 for a, b in zip(vx_before, vx_after) if abs(a - b) > 0.001)
        self.assertGreater(changed, 0)

    def test_heat_burst(self):
        temps_before = [b.temperature for b in self.engine.blobs]
        self.engine.heat_burst(0.5)
        temps_after = [b.temperature for b in self.engine.blobs]
        for before, after in zip(temps_before, temps_after):
            self.assertGreaterEqual(after, before)

    def test_set_blob_wax(self):
        self.engine.set_blob_wax(0, "heavy")
        self.assertEqual(self.engine.blobs[0].wax.name, "Heavy")
        self.assertGreater(self.engine.blobs[0].wax.density, 1.0)

    def test_set_blob_wax_custom(self):
        self.engine.set_blob_wax_custom(0, density=2.0, viscosity=0.5)
        self.assertAlmostEqual(self.engine.blobs[0].wax.density, 2.0)
        self.assertAlmostEqual(self.engine.blobs[0].wax.viscosity, 0.5)

    def test_deterministic_with_seed(self):
        e1 = LavaLampEngine(blob_count=4, seed=99)
        e2 = LavaLampEngine(blob_count=4, seed=99)
        for _ in range(50):
            e1.step(0.016)
            e2.step(0.016)
        for b1, b2 in zip(e1.blobs, e2.blobs):
            self.assertAlmostEqual(b1.x, b2.x, places=10)
            self.assertAlmostEqual(b1.y, b2.y, places=10)


class TestThermalModel(unittest.TestCase):
    """Tests for heating and cooling behaviour."""

    def test_blobs_heat_near_bottom(self):
        engine = LavaLampEngine(blob_count=3, seed=1)
        # Force a blob to the bottom heat zone
        engine.blobs[0].y = 0.05
        engine.blobs[0].temperature = 0.0

        # Run warmup to enable heating
        engine.warmup_time = engine.params.warmup_duration

        for _ in range(100):
            engine.step(0.016)

        self.assertGreater(engine.blobs[0].temperature, 0.0,
                           "Blob near bottom should heat up")

    def test_blobs_cool_near_top(self):
        engine = LavaLampEngine(blob_count=3, seed=1)
        engine.warmup_time = engine.params.warmup_duration
        engine.blobs[0].y = 0.9
        engine.blobs[0].temperature = 0.8

        for _ in range(100):
            engine.step(0.016)

        self.assertLess(engine.blobs[0].temperature, 0.8,
                        "Blob near top should cool down")


class TestBuoyancy(unittest.TestCase):
    """Tests for buoyancy / rising behaviour."""

    def test_hot_blob_rises(self):
        engine = LavaLampEngine(blob_count=1, seed=1)
        engine.warmup_time = engine.params.warmup_duration

        blob = engine.blobs[0]
        blob.y = 0.1
        blob.temperature = 0.9
        blob.detached = True

        initial_y = blob.y
        for _ in range(100):
            engine.step(0.016)

        self.assertGreater(blob.y, initial_y,
                           "Hot detached blob should rise")


if __name__ == "__main__":
    unittest.main()

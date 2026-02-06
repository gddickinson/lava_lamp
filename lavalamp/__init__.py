"""
Lava Lamp Simulator
====================

A physics-based lava lamp simulation using metaball rendering.

Wax blobs sit cold and compact at the bottom of a cylindrical vessel.
A heat source gradually warms them, causing thermal expansion and
buoyancy-driven convection:

  - Hot wax expands and rises (reduced density → buoyancy > gravity)
  - At the top, wax cools, contracts, and sinks back down
  - Metaball field Σ(rᵢ² / dᵢ²) creates organic merging/splitting

The simulation features:
  - 3D blob physics projected to 2D for rendering
  - Warmup phase simulating the lamp being switched on
  - Temperature-dependent expansion (compact→full size)
  - Melt threshold with √-ramp buoyancy for decisive detachment
  - Separate H/V drag for realistic lava lamp motion
  - Inter-blob repulsion and thermal separation forces
  - Customizable colour schemes with contrast wax colours
"""

__version__ = "1.0.0"
__author__ = "Lava Lamp Simulator"

Plan: Camera Pose Sampling for Rembrandt
Context — read these files first
Before writing any code, read:

.ai/AGENTS.md — project overview, MVP scope, conventions, and current state.
src/rembrandt/scene.py — the canonical style reference. Match its docstring format (Google-style with Args:, Returns:, Raises: sections), its use of from __future__ import annotations, its Literal types for enum-like params, and its keyword-only argument patterns where appropriate.
src/rembrandt/main.py — current usage pattern of the Scene class. Your integration example should look like a natural extension of this.
src/rembrandt/errors.py — error-handling pattern. Domain-specific failures get custom exception classes; generic validation failures use stdlib ValueError. For this module, all validation errors are ValueError.

Scope
Add a module that generates N camera positions on a sphere around a target point, restricted to user-specified angular bounds, with two sampling strategies. The output drives the camera-placement loop when rendering a dataset.
This module is pure Python math — no bpy, no mathutils dependency. Keeping it free of Blender makes tests fast, deterministic, and runnable without the 700MB bpy install. Use only math, random, dataclasses, and typing from the standard library.
Non-goals (do not do these)

Do not import bpy in this module or in its tests.
Do not import from mathutils. Use plain tuple[float, float, float] and stdlib math operations. The rest of the project uses Vector only inside scene.py because that file talks directly to Blender.
Do not re-export from src/rembrandt/__init__.py. The project keeps __init__.py minimal; users import from the submodule directly.
Do not modify scene.py, errors.py, main.py, or any other existing files. This is purely additive.
Do not support azimuth wraparound (e.g., (350, 10) to mean "the 20° wedge across +X"). Reject inverted ranges with a clear ValueError. Wraparound is a v0.2 problem.
Do not apply Fibonacci distribution to distance. Distance is always uniform random per pose regardless of strategy — Fibonacci is purely an angular-coverage concern.

Files to create

src/rembrandt/camera_poses.py
tests/test_camera_poses.py

Public API
pythonfrom dataclasses import dataclass
from typing import Literal

SamplingStrategy = Literal["random", "fibonacci"]


@dataclass(frozen=True)
class CameraPose:
    """A camera position and its look-at target in world coordinates."""
    location: tuple[float, float, float]
    look_at: tuple[float, float, float]


def sample_camera_poses(
    *,
    n: int,
    azimuth_range: tuple[float, float] = (0.0, 360.0),
    elevation_range: tuple[float, float] = (-10.0, 30.0),
    distance_range: tuple[float, float] = (3.0, 5.0),
    strategy: SamplingStrategy = "random",
    look_at: tuple[float, float, float] = (0.0, 0.0, 0.0),
    seed: int | None = None,
) -> list[CameraPose]:
    ...
Argument semantics

azimuth_range — degrees. Azimuth is rotation around +Z, measured CCW from +X when viewed from above. Defaults to a full circle.
elevation_range — degrees. Elevation is the angle above the XY plane. 0 = horizontal, +90 = straight up, -90 = straight down. Must be within [-90, 90]. The default (-10, 30) is a near-horizontal band suitable for ground-level subjects.
distance_range — world units. Per-pose distance is independently uniform-sampled from this range, regardless of strategy. Both endpoints must be > 0 and min <= max.
strategy — "random" for independent uniform samples (may cluster), "fibonacci" for evenly-distributed coverage.
look_at — the world-space point all cameras aim at. Camera positions are computed relative to it.
seed — if provided, use a local random.Random(seed) instance. Do not mutate the global RNG state.

Coordinate convention
Blender's right-handed, Z-up convention. Spherical → Cartesian, then offset by look_at:
x = look_at[0] + distance * cos(elevation) * cos(azimuth)
y = look_at[1] + distance * cos(elevation) * sin(azimuth)
z = look_at[2] + distance * sin(elevation)
All trig is in radians — convert from input degrees.
Algorithm — random sampling
Sampling elevation uniformly in degrees produces pole clustering on the sphere. For true area-uniform distribution on a spherical band, sample sin(elevation) uniformly instead:
sin_el_min = sin(radians(elevation_range[0]))
sin_el_max = sin(radians(elevation_range[1]))

for _ in range(n):
    sin_el = rng.uniform(sin_el_min, sin_el_max)
    el = asin(sin_el)
    az = rng.uniform(radians(azimuth_range[0]), radians(azimuth_range[1]))
    dist = rng.uniform(*distance_range)
    # compute Cartesian, append CameraPose
Algorithm — Fibonacci sampling
Distribute sin(elevation) linearly across the band (same area-uniformity reason as above — linear in sin(el) not el). Distribute azimuth via the golden angle, then map into the user's azimuth range:
golden_angle = pi * (3.0 - sqrt(5.0))  # ~2.39996

sin_el_min = sin(radians(elevation_range[0]))
sin_el_max = sin(radians(elevation_range[1]))
az_min = radians(azimuth_range[0])
az_max = radians(azimuth_range[1])
az_span = az_max - az_min

for i in range(n):
    t = (i + 0.5) / n          # half-step offset keeps samples off the boundaries
    sin_el = sin_el_min + t * (sin_el_max - sin_el_min)
    el = asin(sin_el)
    raw_az = (i * golden_angle) % (2 * pi)
    az = az_min + (raw_az / (2 * pi)) * az_span
    dist = rng.uniform(*distance_range)
    # compute Cartesian, append CameraPose
For full-sphere azimuth this reduces to the standard Fibonacci sphere. For narrow bands, the golden angle still gives pseudo-even coverage within the user's range.
Input validation
Validate before any sampling work. Raise ValueError with a clear, specific message for each:

n <= 0 → "n must be > 0, got {n}"
azimuth_range[0] > azimuth_range[1] → "azimuth_range min must be <= max, got {range}"
elevation_range[0] < -90 or elevation_range[1] > 90 → "elevation_range must be within [-90, 90], got {range}"
elevation_range[0] > elevation_range[1] → "elevation_range min must be <= max, got {range}"
distance_range[0] <= 0 or distance_range[1] <= 0 → "distance_range values must be > 0, got {range}"
distance_range[0] > distance_range[1] → "distance_range min must be <= max, got {range}"
strategy not in {"random", "fibonacci"} → handled implicitly by Literal, but runtime callers may bypass; still validate.

Tests
In tests/test_camera_poses.py, no bpy imports. Tests are pure unit tests, parametrize across both strategies where applicable:

Count — len(sample_camera_poses(n=50, ...)) == 50 for both strategies.
Within angular bounds — for each returned pose, recover azimuth and elevation from location relative to look_at via atan2 and asin, assert they fall within the requested ranges (pytest.approx with abs=1e-6). Test with both full-sphere and narrow-band ranges.
Within distance range — for each pose, Euclidean distance from location to look_at is in [distance_range[0] - 1e-9, distance_range[1] + 1e-9].
Reproducibility — same seed → identical output (full list equality on returned CameraPose objects).
Different seeds vary — sanity check that two different seeds produce different first poses.
No global RNG mutation — call random.seed(0), sample a value, call sample_camera_poses(..., seed=99), sample another value; the two values must match what would be produced without the intervening call. (Verifies the function uses a local RNG.)
Validation — pytest.raises(ValueError) for each invalid-input case, with a match= regex confirming the message contains the relevant field name.
Edge cases:

Full sphere: azimuth_range=(0, 360), elevation_range=(-90, 90) runs without error.
Great circle: elevation_range=(0, 0) returns poses with z ≈ look_at[2].
n=1 works for both strategies.
Non-origin look_at: passing look_at=(10, 20, 30) produces poses whose distances are measured from (10, 20, 30), not the origin.



Integration sanity check
This must run end-to-end after implementation. It extends the pattern in src/rembrandt/main.py:
python"""Sanity check: render N frames from sampled camera poses."""

import datetime
from rembrandt.camera_poses import sample_camera_poses
from rembrandt.scene import Scene

poses = sample_camera_poses(
    n=20,
    azimuth_range=(0.0, 360.0),
    elevation_range=(-10.0, 30.0),
    distance_range=(3.0, 5.0),
    strategy="fibonacci",
    seed=42,
)

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

for i, pose in enumerate(poses):
    scene = Scene()
    scene.load_object("./test-obj/mercedes.obj")
    scene.center_target()
    scene.add_camera(location=pose.location, look_at=pose.look_at, focal_length=50)
    scene.add_light(light_type="SUN", location=(2, -3, 5), energy=3.0)
    scene.add_light(light_type="POINT", location=(-2, 2, 3))
    out = scene.render(f"output/{stamp}/frame_{i:04d}.png", resolution=(640, 640))
    print(f"Rendered frame {i} to {out}")
Important interaction note
Scene.add_camera defaults to fit_target=True. If a sampled distance is too close to fit the object in frame, add_camera pushes the camera back to the fit distance. For large models with small distance_range, this means many or all sampled distances get overridden. This is intentional behavior — the safety net keeps the object visible — but document it in the module-level docstring so users aren't surprised. Users who want their distance samples honored exactly can pass fit_target=False.
Acceptance criteria

from rembrandt.camera_poses import sample_camera_poses, CameraPose imports cleanly.
All tests in tests/test_camera_poses.py pass: pytest tests/test_camera_poses.py -v
ruff check src/rembrandt/camera_poses.py tests/test_camera_poses.py is clean.
ruff format --check src/rembrandt/camera_poses.py tests/test_camera_poses.py is clean.
mypy src/rembrandt/camera_poses.py is clean under strict mode.
The integration script above renders 20 visually distinct images of the Mercedes from varied angles around the horizontal band when run against a real .obj.
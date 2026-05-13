"""Tests for pure camera pose sampling."""

from __future__ import annotations

from math import asin, atan2, degrees, sqrt
from random import random, seed
from typing import Literal

import pytest

from rembrandt.camera_poses import CameraPose, sample_camera_poses

Strategy = Literal["random", "fibonacci"]


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_count(strategy: Strategy) -> None:
    poses = sample_camera_poses(n=50, strategy=strategy, seed=1)

    assert len(poses) == 50


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
@pytest.mark.parametrize(
    ("azimuth_range", "elevation_range"),
    [
        ((0.0, 360.0), (-90.0, 90.0)),
        ((20.0, 120.0), (-15.0, 25.0)),
    ],
)
def test_sample_camera_poses_within_angular_bounds(
    strategy: Strategy,
    azimuth_range: tuple[float, float],
    elevation_range: tuple[float, float],
) -> None:
    poses = sample_camera_poses(
        n=100,
        azimuth_range=azimuth_range,
        elevation_range=elevation_range,
        strategy=strategy,
        seed=2,
    )

    for pose in poses:
        azimuth, elevation = _recover_angles(pose)
        assert azimuth_range[0] - 1e-6 <= azimuth <= azimuth_range[1] + 1e-6
        assert elevation == pytest.approx(
            min(max(elevation, elevation_range[0]), elevation_range[1]),
            abs=1e-6,
        )


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_within_distance_range(strategy: Strategy) -> None:
    distance_range = (7.0, 9.0)
    poses = sample_camera_poses(
        n=100,
        distance_range=distance_range,
        look_at=(10.0, 20.0, 30.0),
        strategy=strategy,
        seed=3,
    )

    for pose in poses:
        distance = _distance_from_look_at(pose)
        assert distance_range[0] - 1e-9 <= distance <= distance_range[1] + 1e-9


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_reproducible_with_same_seed(strategy: Strategy) -> None:
    first = sample_camera_poses(n=10, strategy=strategy, seed=4)
    second = sample_camera_poses(n=10, strategy=strategy, seed=4)

    assert first == second


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_different_seeds_vary(strategy: Strategy) -> None:
    first = sample_camera_poses(n=10, strategy=strategy, seed=5)
    second = sample_camera_poses(n=10, strategy=strategy, seed=6)

    assert first[0] != second[0]


def test_sample_camera_poses_does_not_mutate_global_rng() -> None:
    seed(0)
    before = random()
    sample_camera_poses(n=10, seed=99)
    after = random()

    seed(0)
    expected_before = random()
    expected_after = random()

    assert before == expected_before
    assert after == expected_after


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n": 0}, "n"),
        ({"n": 1, "azimuth_range": (350.0, 10.0)}, "azimuth_range"),
        ({"n": 1, "elevation_range": (-91.0, 10.0)}, "elevation_range"),
        ({"n": 1, "elevation_range": (10.0, 91.0)}, "elevation_range"),
        ({"n": 1, "elevation_range": (10.0, -10.0)}, "elevation_range"),
        ({"n": 1, "distance_range": (0.0, 1.0)}, "distance_range"),
        ({"n": 1, "distance_range": (1.0, 0.0)}, "distance_range"),
        ({"n": 1, "strategy": "grid"}, "strategy"),
    ],
)
def test_sample_camera_poses_validation(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        sample_camera_poses(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_full_sphere(strategy: Strategy) -> None:
    poses = sample_camera_poses(
        n=20,
        azimuth_range=(0.0, 360.0),
        elevation_range=(-90.0, 90.0),
        strategy=strategy,
        seed=7,
    )

    assert len(poses) == 20


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_great_circle(strategy: Strategy) -> None:
    look_at = (10.0, 20.0, 30.0)
    poses = sample_camera_poses(
        n=20,
        elevation_range=(0.0, 0.0),
        look_at=look_at,
        strategy=strategy,
        seed=8,
    )

    for pose in poses:
        assert pose.location[2] == pytest.approx(look_at[2], abs=1e-9)


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_n_one(strategy: Strategy) -> None:
    poses = sample_camera_poses(n=1, strategy=strategy, seed=9)

    assert len(poses) == 1


@pytest.mark.parametrize("strategy", ["random", "fibonacci"])
def test_sample_camera_poses_non_origin_look_at(strategy: Strategy) -> None:
    look_at = (10.0, 20.0, 30.0)
    poses = sample_camera_poses(
        n=20,
        distance_range=(4.0, 4.0),
        look_at=look_at,
        strategy=strategy,
        seed=10,
    )

    for pose in poses:
        assert pose.look_at == look_at
        assert _distance_from_look_at(pose) == pytest.approx(4.0, abs=1e-9)


def _recover_angles(pose: CameraPose) -> tuple[float, float]:
    dx = pose.location[0] - pose.look_at[0]
    dy = pose.location[1] - pose.look_at[1]
    dz = pose.location[2] - pose.look_at[2]
    distance = _distance_from_look_at(pose)

    azimuth = degrees(atan2(dy, dx))
    if azimuth < 0.0:
        azimuth += 360.0
    elevation = degrees(asin(dz / distance))
    return azimuth, elevation


def _distance_from_look_at(pose: CameraPose) -> float:
    dx = pose.location[0] - pose.look_at[0]
    dy = pose.location[1] - pose.look_at[1]
    dz = pose.location[2] - pose.look_at[2]
    return sqrt((dx * dx) + (dy * dy) + (dz * dz))

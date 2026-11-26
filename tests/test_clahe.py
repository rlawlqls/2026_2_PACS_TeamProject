"""B 담당 CLAHE 단위 테스트 (TEAM_CONTRACT §4 B·§8.2)."""

import cv2
import numpy as np
import pytest

from src.errors import ValidationError
from src.processing.clahe import ALGORITHM_NAME, ALGORITHM_VERSION, apply_clahe


def test_apply_clahe_keeps_shape_and_dtype(samples):
    gray = samples["normal"]

    result = apply_clahe(gray)

    assert isinstance(result, np.ndarray)
    assert result.shape == gray.shape
    assert result.dtype == np.uint8


def test_apply_clahe_does_not_modify_input(samples):
    gray = samples["low_contrast"].copy()
    original = gray.copy()

    result = apply_clahe(gray, clip_limit=4.0, tile_grid_size=(4, 4))

    np.testing.assert_array_equal(gray, original)
    assert result is not gray
    assert not np.shares_memory(result, gray)


def test_apply_clahe_increases_contrast_of_low_contrast_image(samples):
    gray = samples["low_contrast"]

    result = apply_clahe(gray)

    assert result.std() > gray.std()


def test_apply_clahe_default_params_match_contract(samples):
    gray = samples["normal"]

    np.testing.assert_array_equal(
        apply_clahe(gray), apply_clahe(gray, clip_limit=2.0, tile_grid_size=(8, 8))
    )


def test_apply_clahe_is_reproducible(samples):
    gray = samples["dark"]

    np.testing.assert_array_equal(apply_clahe(gray, 3.0, (4, 4)), apply_clahe(gray, 3.0, (4, 4)))


def test_apply_clahe_higher_clip_limit_gives_stronger_contrast(samples):
    gray = samples["low_contrast"]

    weak = apply_clahe(gray, clip_limit=1.0)
    strong = apply_clahe(gray, clip_limit=8.0)

    assert strong.std() > weak.std()


def test_apply_clahe_accepts_non_square_image_and_grid():
    rng = np.random.default_rng(0)
    gray = rng.integers(0, 256, size=(48, 96), dtype=np.uint8)

    result = apply_clahe(gray, clip_limit=2, tile_grid_size=[4, 2])  # int clip_limit, list 허용

    assert result.shape == (48, 96)
    assert result.dtype == np.uint8


def test_apply_clahe_tile_grid_order_is_columns_then_rows():
    # 열마다 밝기가 다른 가로 4 × 세로 64 영상: 가로로 나누면 칸마다 값이 하나뿐이라 결과가 달라진다.
    gray = np.tile(np.array([10, 80, 150, 220], dtype=np.uint8), (64, 1))

    by_columns = apply_clahe(gray, tile_grid_size=(2, 1))
    by_rows = apply_clahe(gray, tile_grid_size=(1, 2))

    assert not np.array_equal(by_columns, by_rows)
    np.testing.assert_array_equal(
        by_columns, cv2.createCLAHE(clipLimit=2.0, tileGridSize=(2, 1)).apply(gray))


def test_apply_clahe_accepts_grid_larger_than_image_as_finest_grid(samples):
    # 계약은 각 값이 1 이상이기만 하면 된다. 영상보다 잘게 나누라는 요청은 가장 잘게(칸당 2픽셀) 나눈다.
    small = np.random.default_rng(1).integers(0, 256, size=(4, 6), dtype=np.uint8)
    gray = samples["normal"]

    assert apply_clahe(small, tile_grid_size=(8, 8)).shape == (4, 6)
    np.testing.assert_array_equal(
        apply_clahe(gray, tile_grid_size=(2**40, 10**6)), apply_clahe(gray, tile_grid_size=(128, 128)))
    assert apply_clahe(np.full((1, 1), 7, dtype=np.uint8)).shape == (1, 1)


def test_apply_clahe_huge_clip_limit_means_no_clipping(samples):
    # 그대로 OpenCV에 넘기면 내부 정수가 넘쳐 가장 약한 대비가 나온다 → 256과 같은 결과여야 한다.
    gray = samples["low_contrast"]
    unclipped = apply_clahe(gray, clip_limit=256.0)

    for clip_limit in (1e3, 1e9, 1e300, 10**30):
        np.testing.assert_array_equal(apply_clahe(gray, clip_limit=clip_limit), unclipped)
    assert unclipped.std() > apply_clahe(gray, clip_limit=2.0).std()


def test_algorithm_name_and_version_for_processing_runs():
    assert ALGORITHM_NAME == "clahe"
    assert isinstance(ALGORITHM_VERSION, str) and ALGORITHM_VERSION


@pytest.mark.parametrize("clip_limit", [0, 0.0, -1.0, float("nan"), float("inf"), 10**400, "2.0", None, True])
def test_apply_clahe_rejects_invalid_clip_limit(samples, clip_limit):
    with pytest.raises(ValidationError):
        apply_clahe(samples["normal"], clip_limit=clip_limit)


@pytest.mark.parametrize(
    "tile_grid_size",
    [(0, 8), (8, 0), (-1, 8), (8,), (8, 8, 8), 8, "88", (8.0, 8), (True, 8), None],
)
def test_apply_clahe_rejects_invalid_tile_grid_size(samples, tile_grid_size):
    with pytest.raises(ValidationError):
        apply_clahe(samples["normal"], tile_grid_size=tile_grid_size)


@pytest.mark.parametrize(
    "gray",
    [
        [[0] * 64 for _ in range(64)],
        np.zeros((64, 64, 3), dtype=np.uint8),
        np.zeros((64, 64), dtype=np.float32),
        np.zeros((64, 64), dtype=np.uint16),
        np.zeros((0, 64), dtype=np.uint8),
        None,
    ],
    ids=["list", "rgb", "float32", "uint16", "empty", "none"],
)
def test_apply_clahe_rejects_invalid_image(gray):
    with pytest.raises(ValidationError):
        apply_clahe(gray)

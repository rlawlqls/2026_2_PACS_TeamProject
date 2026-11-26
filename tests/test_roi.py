"""B 담당 ROI 통계 단위 테스트 (TEAM_CONTRACT §4 B·§8.2)."""

import json

import numpy as np
import pytest

from src.errors import ValidationError
from src.processing.roi import get_roi_stats

RESULT_KEYS = {"roi", "mean", "variance", "std", "min", "max", "histogram", "pixel_count"}


def _roi(x, y, width, height):
    return {"x": x, "y": y, "width": width, "height": height}


def test_get_roi_stats_known_values():
    gray = np.zeros((40, 50), dtype=np.uint8)
    gray[10:12, 20:24] = [[10, 20, 30, 40], [50, 60, 70, 80]]

    stats = get_roi_stats(gray, _roi(20, 10, 4, 2))

    values = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=np.float64)
    assert set(stats) == RESULT_KEYS
    assert stats["roi"] == _roi(20, 10, 4, 2)
    assert stats["mean"] == pytest.approx(45.0)
    assert stats["variance"] == pytest.approx(values.var(ddof=0))  # 모집단 분산
    assert stats["std"] == pytest.approx(values.std(ddof=0))
    assert stats["min"] == 10
    assert stats["max"] == 80
    assert stats["pixel_count"] == 8


def test_get_roi_stats_histogram_has_256_bins_and_sums_to_pixel_count(samples):
    stats = get_roi_stats(samples["normal"], _roi(30, 40, 100, 80))

    assert len(stats["histogram"]) == 256
    assert sum(stats["histogram"]) == stats["pixel_count"] == 100 * 80


def test_get_roi_stats_histogram_counts_each_value():
    gray = np.full((32, 32), 7, dtype=np.uint8)
    gray[0, 0] = 255
    gray[0, 1] = 0

    stats = get_roi_stats(gray, _roi(0, 0, 32, 32))

    assert stats["histogram"][0] == 1
    assert stats["histogram"][7] == 32 * 32 - 2
    assert stats["histogram"][255] == 1


def test_get_roi_stats_uses_half_open_range_x_right_y_down():
    # x는 오른쪽, y는 아래쪽. 경계는 [x, x+width) × [y, y+height).
    gray = np.zeros((32, 64), dtype=np.uint8)
    gray[5, 40] = 200          # (x=40, y=5)

    inside = get_roi_stats(gray, _roi(40, 5, 1, 1))
    just_left = get_roi_stats(gray, _roi(39, 5, 1, 1))
    just_above = get_roi_stats(gray, _roi(40, 4, 1, 1))

    assert inside["max"] == 200 and inside["pixel_count"] == 1
    assert just_left["max"] == 0
    assert just_above["max"] == 0


def test_get_roi_stats_full_image_and_edges_are_allowed(samples):
    gray = samples["normal"]
    height, width = gray.shape

    full = get_roi_stats(gray, _roi(0, 0, width, height))
    corner = get_roi_stats(gray, _roi(width - 1, height - 1, 1, 1))

    assert full["pixel_count"] == gray.size
    assert full["mean"] == pytest.approx(float(gray.mean()))
    assert corner["min"] == corner["max"] == int(gray[-1, -1])


def test_get_roi_stats_returns_json_serializable_builtin_types(samples):
    roi = {"x": np.int64(3), "y": np.int32(4), "width": np.int64(10), "height": 12}

    stats = get_roi_stats(samples["normal"], roi)

    assert json.loads(json.dumps(stats)) == stats           # Firestore에 그대로 저장 가능
    assert type(stats["mean"]) is float
    assert type(stats["variance"]) is float
    assert type(stats["std"]) is float
    assert type(stats["min"]) is int and type(stats["max"]) is int
    assert type(stats["pixel_count"]) is int
    assert all(type(count) is int for count in stats["histogram"])
    assert all(type(value) is int for value in stats["roi"].values())


def test_get_roi_stats_does_not_modify_inputs(samples):
    gray = samples["normal"].copy()
    original = gray.copy()
    roi = _roi(10, 10, 20, 20)

    stats = get_roi_stats(gray, roi)

    np.testing.assert_array_equal(gray, original)
    assert roi == _roi(10, 10, 20, 20)
    assert stats["roi"] is not roi


@pytest.mark.parametrize(
    "roi",
    [
        _roi(-1, 0, 10, 10),
        _roi(0, -1, 10, 10),
        _roi(0, 0, 0, 10),
        _roi(0, 0, 10, 0),
        _roi(0, 0, -5, 10),
        _roi(60, 0, 10, 10),     # x + width = 70 > 64
        _roi(0, 30, 10, 10),     # y + height = 40 > 32
        _roi(64, 0, 1, 1),       # x가 영상 밖
        _roi(0, 0, 65, 32),
        _roi(0, 0, 64, 33),
    ],
)
def test_get_roi_stats_rejects_roi_outside_image(roi):
    gray = np.zeros((32, 64), dtype=np.uint8)

    with pytest.raises(ValidationError):
        get_roi_stats(gray, roi)


@pytest.mark.parametrize(
    "roi",
    [
        None,
        [0, 0, 10, 10],
        {"x": 0, "y": 0, "width": 10},                       # height 없음
        {"x": 0, "y": 0, "w": 10, "h": 10},
        {"x": 0.0, "y": 0, "width": 10, "height": 10},
        {"x": "0", "y": 0, "width": 10, "height": 10},
        {"x": True, "y": 0, "width": 10, "height": 10},
        {"x": 0, "y": 0, "width": None, "height": 10},
    ],
)
def test_get_roi_stats_rejects_malformed_roi(roi):
    gray = np.zeros((32, 64), dtype=np.uint8)

    with pytest.raises(ValidationError):
        get_roi_stats(gray, roi)


@pytest.mark.parametrize(
    "gray",
    [
        [[0] * 64 for _ in range(64)],
        np.zeros((64, 64, 3), dtype=np.uint8),
        np.zeros((64, 64), dtype=np.float32),
        np.zeros((0, 64), dtype=np.uint8),
        None,
    ],
    ids=["list", "rgb", "float32", "empty", "none"],
)
def test_get_roi_stats_rejects_invalid_image(gray):
    with pytest.raises(ValidationError):
        get_roi_stats(gray, _roi(0, 0, 1, 1))

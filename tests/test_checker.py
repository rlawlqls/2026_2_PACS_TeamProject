"""check_quality 테스트 (C 소유, #26).

테스트 영상은 이 파일 안에서 코드로 만든다 (PNG 파일을 읽지 않음, TEAM_CONTRACT §3.4).
지표를 손으로 계산할 수 있는 영상을 쓴다:

- 체커보드(1픽셀 단위로 a, b 번갈아): 평균 (a+b)/2, 표준편차 |a−b|/2, 경계가 많아 선명도 매우 큼
- 가로 그라데이션: 밝기는 고르게 퍼져 대비는 크지만, 경계가 없어 선명도 ≈ 0 (흐림)
- 한 가지 값으로 채운 영상: 대비 0, 선명도 0
"""

import copy
import math

import cv2
import numpy as np
import pytest

from src.errors import ValidationError
from src.quality.checker import (
    CHECKER_VERSION,
    REASON_LABELS,
    THRESHOLD_NUMBER_KEYS,
    check_quality,
    measure_metrics,
)
from src.quality.thresholds import DEFAULT_THRESHOLDS

# 테스트가 기준값 보정(demo-v2 등)에 흔들리지 않도록 고정 기준값을 따로 둔다.
FIXED = {
    "brightness_min": 50.0,
    "brightness_max": 205.0,
    "contrast_std_min": 35.0,
    "laplacian_var_min": 80.0,
    "version": "test-v1",
}


def checkerboard(a: int, b: int, size: int = 64) -> np.ndarray:
    y, x = np.indices((size, size))
    return np.where((x + y) % 2 == 0, a, b).astype(np.uint8)


def gradient(height: int = 64, width: int = 256) -> np.ndarray:
    return np.tile(np.arange(width), (height, 1)).astype(np.uint8)


def flat(value: int, size: int = 32) -> np.ndarray:
    return np.full((size, size), value, dtype=np.uint8)


# ---------------------------------------------------------------------------
# 반환 형식
# ---------------------------------------------------------------------------
def test_result_follows_contract_format():
    result = check_quality(checkerboard(40, 220), FIXED)
    assert set(result) == {"status", "metrics", "reasons", "thresholds", "checker_version"}
    assert set(result["metrics"]) == {"brightness_mean", "contrast_std", "laplacian_variance"}
    assert result["checker_version"] == CHECKER_VERSION
    assert result["thresholds"] == FIXED
    # Firestore에 바로 저장할 수 있게 numpy가 아닌 파이썬 float여야 한다.
    for value in result["metrics"].values():
        assert type(value) is float
    for key in THRESHOLD_NUMBER_KEYS:
        assert type(result["thresholds"][key]) is float


def test_metrics_use_contract_formula():
    rng = np.random.default_rng(0)
    gray = rng.integers(0, 256, (50, 70), dtype=np.uint8)
    metrics = measure_metrics(gray)
    assert math.isclose(metrics["brightness_mean"], np.mean(gray))
    assert math.isclose(metrics["contrast_std"], np.std(gray))
    assert math.isclose(metrics["laplacian_variance"], cv2.Laplacian(gray, cv2.CV_64F).var())
    assert check_quality(gray, FIXED)["metrics"] == metrics


def test_checkerboard_metrics_match_hand_calculation():
    metrics = measure_metrics(checkerboard(100, 140))
    assert metrics["brightness_mean"] == 120.0
    assert metrics["contrast_std"] == 20.0


# ---------------------------------------------------------------------------
# 판정
# ---------------------------------------------------------------------------
def test_good_image_passes():
    result = check_quality(checkerboard(40, 220), FIXED)
    assert result["status"] == "pass"
    assert result["reasons"] == []


@pytest.mark.parametrize(("gray", "expected"), [
    (checkerboard(0, 80), ["too_dark"]),          # 평균 40
    (checkerboard(180, 255), ["too_bright"]),     # 평균 217.5
    (checkerboard(100, 140), ["low_contrast"]),   # 표준편차 20
    (gradient(), ["possibly_blurry"]),            # 선명도 ≈ 0
], ids=["dark", "bright", "low_contrast", "blurry"])
def test_each_reason_alone(gray, expected):
    result = check_quality(gray, FIXED)
    assert result["status"] == "needs_check"
    assert result["reasons"] == expected


@pytest.mark.parametrize(("value", "first"), [(20, "too_dark"), (240, "too_bright")])
def test_multiple_reasons_keep_contract_order(value, first):
    result = check_quality(flat(value), FIXED)
    assert result["reasons"] == [first, "low_contrast", "possibly_blurry"]


def test_value_equal_to_threshold_passes():
    """지표가 기준값과 정확히 같으면 통과, 아주 조금이라도 넘어서면 경고."""
    gray = checkerboard(40, 220)
    m = measure_metrics(gray)
    exact = {
        "brightness_min": m["brightness_mean"],
        "brightness_max": m["brightness_mean"],
        "contrast_std_min": m["contrast_std"],
        "laplacian_var_min": m["laplacian_variance"],
        "version": "edge",
    }
    assert check_quality(gray, exact)["reasons"] == []

    eps = 1e-6
    assert check_quality(gray, {**exact, "brightness_min": m["brightness_mean"] + eps,
                                "brightness_max": 255.0})["reasons"] == ["too_dark"]
    assert check_quality(gray, {**exact, "brightness_min": 0.0,
                                "brightness_max": m["brightness_mean"] - eps})["reasons"] == ["too_bright"]
    assert check_quality(gray, {**exact, "contrast_std_min": m["contrast_std"] + eps})["reasons"] == ["low_contrast"]
    assert check_quality(gray, {**exact, "laplacian_var_min": m["laplacian_variance"] + eps})["reasons"] == ["possibly_blurry"]


def test_zero_thresholds_disable_checks():
    off = {**FIXED, "brightness_min": 0.0, "brightness_max": 255.0,
           "contrast_std_min": 0.0, "laplacian_var_min": 0.0}
    assert check_quality(flat(0), off)["status"] == "pass"


def test_works_with_default_thresholds():
    result = check_quality(checkerboard(40, 220), DEFAULT_THRESHOLDS)
    assert result["status"] == "pass"
    assert result["thresholds"]["version"] == DEFAULT_THRESHOLDS["version"]


def test_accepts_numpy_and_int_threshold_values():
    mixed = {**FIXED, "brightness_min": np.float32(50), "laplacian_var_min": 80}
    result = check_quality(checkerboard(0, 80), mixed)
    assert result["reasons"] == ["too_dark"]
    assert type(result["thresholds"]["brightness_min"]) is float


def test_extra_threshold_keys_are_not_copied():
    result = check_quality(checkerboard(40, 220), {**FIXED, "memo": "x"})
    assert "memo" not in result["thresholds"]


def test_every_reason_has_korean_label():
    assert REASON_LABELS == {
        "too_dark": "어두움",
        "too_bright": "너무 밝음",
        "low_contrast": "낮은 대비",
        "possibly_blurry": "흐림 의심",
    }


# ---------------------------------------------------------------------------
# 입력 불변·재현성
# ---------------------------------------------------------------------------
def test_does_not_modify_inputs_or_share_thresholds():
    gray = checkerboard(0, 80)
    gray_before = gray.copy()
    defaults_before = copy.deepcopy(DEFAULT_THRESHOLDS)

    result = check_quality(gray, DEFAULT_THRESHOLDS)
    result["thresholds"]["brightness_min"] = 999.0   # 결과를 고쳐도

    assert np.array_equal(gray, gray_before)
    assert DEFAULT_THRESHOLDS == defaults_before      # 원본 기준값은 그대로
    assert result["thresholds"] is not DEFAULT_THRESHOLDS


def test_same_input_gives_same_result():
    rng = np.random.default_rng(1)
    gray = rng.integers(0, 256, (80, 60), dtype=np.uint8)
    assert check_quality(gray, FIXED) == check_quality(gray.copy(), dict(FIXED))


def test_single_pixel_image():
    result = check_quality(np.array([[128]], dtype=np.uint8), FIXED)
    assert result["reasons"] == ["low_contrast", "possibly_blurry"]


# ---------------------------------------------------------------------------
# 오류 입력
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gray", [
    np.zeros((8, 8, 3), dtype=np.uint8),
    np.zeros((8, 8), dtype=np.float64),
    np.zeros((8, 8), dtype=np.uint16),
    np.zeros((0, 0), dtype=np.uint8),
    [[0, 1], [2, 3]],
    None,
], ids=["color", "float", "uint16", "empty", "list", "none"])
def test_rejects_invalid_image(gray):
    with pytest.raises(ValidationError):
        check_quality(gray, FIXED)
    with pytest.raises(ValidationError):
        measure_metrics(gray)


@pytest.mark.parametrize("key", [*THRESHOLD_NUMBER_KEYS, "version"])
def test_rejects_missing_threshold_key(key):
    broken = {k: v for k, v in FIXED.items() if k != key}
    with pytest.raises(ValidationError):
        check_quality(checkerboard(40, 220), broken)


@pytest.mark.parametrize("value", ["50", None, True, float("nan"), float("inf"), -1.0],
                         ids=["str", "none", "bool", "nan", "inf", "negative"])
@pytest.mark.parametrize("key", THRESHOLD_NUMBER_KEYS)
def test_rejects_invalid_threshold_value(key, value):
    with pytest.raises(ValidationError):
        check_quality(checkerboard(40, 220), {**FIXED, key: value})


@pytest.mark.parametrize("thresholds", [
    {**FIXED, "brightness_min": 210.0, "brightness_max": 200.0},
    {**FIXED, "version": ""},
    {**FIXED, "version": 2},
    None,
    [("brightness_min", 50.0)],
], ids=["min_gt_max", "empty_version", "int_version", "none", "list"])
def test_rejects_invalid_thresholds(thresholds):
    with pytest.raises(ValidationError):
        check_quality(checkerboard(40, 220), thresholds)

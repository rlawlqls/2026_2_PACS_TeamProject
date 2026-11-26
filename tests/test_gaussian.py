"""apply_gaussian 테스트 (C 소유, #24).

샘플 영상은 이 파일 안에서 코드로 만든다 (PNG 파일을 읽지 않음, TEAM_CONTRACT §3.4).
"""

import math

import cv2
import numpy as np
import pytest

from src.errors import ValidationError
from src.processing.gaussian import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    apply_gaussian,
    effective_sigma,
)


def smooth_image(height: int = 120, width: int = 160) -> np.ndarray:
    """잡음 없는 영상: 가로 그라데이션 + 가운데 밝은 사각형(경계 확인용)."""
    image = np.tile(np.linspace(40, 200, width), (height, 1))
    image[40:80, 60:100] = 230
    return image.astype(np.uint8)


def add_noise(gray: np.ndarray, sigma: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(gray + rng.normal(0, sigma, gray.shape), 0, 255).astype(np.uint8)


def laplacian_var(gray: np.ndarray) -> float:
    """선명도 지표 (TEAM_CONTRACT §4의 Laplacian 분산). 흐릴수록 작다."""
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# ---------------------------------------------------------------------------
# 정상 입력
# ---------------------------------------------------------------------------
def test_keeps_shape_dtype_and_does_not_modify_input():
    gray = add_noise(smooth_image(), 20)
    before = gray.copy()
    out = apply_gaussian(gray)
    assert out.shape == gray.shape and out.dtype == np.uint8
    assert out is not gray
    assert np.array_equal(gray, before)


def test_works_on_non_square_large_image():
    gray = add_noise(np.full((301, 203), 120, dtype=np.uint8), 10)
    assert apply_gaussian(gray, 7, 2.0).shape == (301, 203)


def test_kernel_size_one_returns_same_image():
    gray = add_noise(smooth_image(), 20)
    assert np.array_equal(apply_gaussian(gray, kernel_size=1), gray)


def test_matches_opencv_reference():
    gray = add_noise(smooth_image(), 20)
    expected = cv2.GaussianBlur(gray, (7, 7), 1.5)
    assert np.array_equal(apply_gaussian(gray, kernel_size=7, sigma=1.5), expected)


def test_larger_kernel_blurs_more():
    gray = add_noise(smooth_image(), 20)
    sharpness = [laplacian_var(apply_gaussian(gray, k)) for k in (3, 5, 9, 15)]
    assert sharpness == sorted(sharpness, reverse=True)
    assert len(set(sharpness)) == len(sharpness)      # 모두 다름 → 단계마다 더 흐려짐


def test_larger_sigma_blurs_more_with_same_kernel():
    gray = add_noise(smooth_image(), 20)
    assert laplacian_var(apply_gaussian(gray, 9, 3.0)) < laplacian_var(apply_gaussian(gray, 9, 1.0))


def test_reduces_gaussian_noise():
    """잡음을 넣은 영상이 Gaussian 처리 후 원래(잡음 없는) 영상에 더 가까워진다."""
    clean = smooth_image()
    noisy = add_noise(clean, 20)
    error_before = np.abs(noisy.astype(float) - clean).mean()
    error_after = np.abs(apply_gaussian(noisy, 5).astype(float) - clean).mean()
    assert error_after < error_before * 0.6


def test_accepts_numpy_integer_kernel_and_int_sigma():
    gray = smooth_image()
    assert np.array_equal(apply_gaussian(gray, np.int64(5), 2), apply_gaussian(gray, 5, 2.0))


@pytest.mark.parametrize(("kernel_size", "sigma", "expected"), [
    (3, 0.0, 0.8),
    (5, 0.0, 1.1),
    (9, 0.0, 1.7),
    (5, 2.5, 2.5),
])
def test_effective_sigma(kernel_size, sigma, expected):
    assert math.isclose(effective_sigma(kernel_size, sigma), expected, abs_tol=1e-9)


def test_algorithm_constants_for_processing_history():
    assert ALGORITHM_NAME == "gaussian"
    assert isinstance(ALGORITHM_VERSION, str) and ALGORITHM_VERSION


# ---------------------------------------------------------------------------
# 오류 입력
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kernel_size", [4, 0, -3, 5.0, True, "5", None],
                         ids=["even", "zero", "negative", "float", "bool", "str", "none"])
def test_rejects_invalid_kernel_size(kernel_size):
    with pytest.raises(ValidationError):
        apply_gaussian(smooth_image(), kernel_size=kernel_size)
    with pytest.raises(ValidationError):
        effective_sigma(kernel_size)


@pytest.mark.parametrize("sigma", [-0.1, float("nan"), float("inf"), "1.0", None, True],
                         ids=["negative", "nan", "inf", "str", "none", "bool"])
def test_rejects_invalid_sigma(sigma):
    with pytest.raises(ValidationError):
        apply_gaussian(smooth_image(), kernel_size=5, sigma=sigma)


@pytest.mark.parametrize("gray", [
    np.zeros((8, 8, 3), dtype=np.uint8),
    np.zeros((8, 8), dtype=np.float64),
    np.zeros((0, 0), dtype=np.uint8),
    [[0, 1], [2, 3]],
], ids=["color", "float", "empty", "list"])
def test_rejects_invalid_image(gray):
    with pytest.raises(ValidationError):
        apply_gaussian(gray)

"""D 담당 Median 필터 단위 테스트."""

import numpy as np
import pytest

from src.errors import ValidationError
from src.processing.median import apply_median


def test_apply_median_reduces_salt_and_pepper_noise():
    gray = np.full((64, 64), 128, dtype=np.uint8)
    gray[20, 20] = 0
    gray[30, 30] = 255

    result = apply_median(gray, kernel_size=3)

    assert result[20, 20] == 128
    assert result[30, 30] == 128
    assert result.shape == gray.shape
    assert result.dtype == np.uint8


def test_apply_median_does_not_modify_input():
    gray = np.arange(64 * 64, dtype=np.uint8).reshape(64, 64)
    original = gray.copy()

    apply_median(gray)

    np.testing.assert_array_equal(gray, original)


@pytest.mark.parametrize("kernel_size", [1, 2, 4, 0, -3, 3.0, True])
def test_apply_median_rejects_invalid_kernel_size(kernel_size):
    gray = np.zeros((64, 64), dtype=np.uint8)

    with pytest.raises(ValidationError):
        apply_median(gray, kernel_size=kernel_size)


@pytest.mark.parametrize(
    "gray",
    [
        [[0] * 64 for _ in range(64)],
        np.zeros((64, 64, 3), dtype=np.uint8),
        np.zeros((64, 64), dtype=np.float32),
        np.zeros((31, 64), dtype=np.uint8),
    ],
)
def test_apply_median_rejects_invalid_image(gray):
    with pytest.raises(ValidationError):
        apply_median(gray)


def test_apply_median_rejects_kernel_larger_than_image():
    gray = np.zeros((32, 32), dtype=np.uint8)

    with pytest.raises(ValidationError):
        apply_median(gray, kernel_size=33)

"""Gaussian 블러 (C 소유, TEAM_CONTRACT §4 C 계약, #24).

목적: 영상의 잡음(자글자글한 점)을 줄인다. 각 픽셀을 주변 픽셀의 **가중 평균**으로 바꾸는데,
가중치가 Gaussian(종 모양) 분포라서 가까운 픽셀일수록 크게 반영된다.

- `kernel_size`: 평균을 내는 창의 크기 (k×k). 중심 픽셀이 있어야 하므로 **양의 홀수**.
- `sigma`: 종 모양의 폭. 클수록 먼 픽셀까지 많이 섞여 더 흐려진다.
  0이면 OpenCV가 kernel_size로 정한다 (`effective_sigma` 참고).

한계: 잡음과 함께 **경계(뼈 가장자리, 미세 구조)도 흐려진다.** 점 형태의 소금·후추 잡음에는
Median(D)이 더 효과적이다. 비교 실험은 TEAM_CONTRACT §8.5 기록에 남긴다.
"""

import math
from numbers import Real

import cv2
import numpy as np

from src.errors import ValidationError

#: 처리 이력(processing_runs)의 algorithm 값
ALGORITHM_NAME = "gaussian"
#: 처리 이력의 algorithm_version. 동작이 바뀌면 올린다.
ALGORITHM_VERSION = "1.0.0"


def _check_gray(gray: np.ndarray) -> None:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상은 (H, W) 모양의 uint8 grayscale 배열이어야 합니다.")
    if gray.size == 0:
        raise ValidationError("빈 영상은 처리할 수 없습니다.")


def _check_kernel_size(kernel_size: int) -> None:
    # bool은 int의 하위 타입이라 True가 1로 통과하지 않도록 먼저 막는다.
    if isinstance(kernel_size, bool) or not isinstance(kernel_size, (int, np.integer)):
        raise ValidationError("kernel_size는 정수여야 합니다.")
    if kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValidationError("kernel_size는 양의 홀수여야 합니다 (예: 3, 5, 7).")


def _check_sigma(sigma: float) -> None:
    if isinstance(sigma, bool) or not isinstance(sigma, Real):
        raise ValidationError("sigma는 숫자여야 합니다.")
    if not math.isfinite(sigma) or sigma < 0:
        raise ValidationError("sigma는 0 이상의 유한한 수여야 합니다.")


def effective_sigma(kernel_size: int, sigma: float = 0.0) -> float:
    """실제로 적용되는 sigma를 돌려준다 (처리 이력·보고서 기록용).

    sigma > 0이면 그대로. sigma == 0이면 OpenCV 규칙
    `0.3 × ((kernel_size − 1) × 0.5 − 1) + 0.8`로 계산한 값이다.
    단 kernel_size가 7 이하이고 sigma가 0이면 OpenCV는 이 값에 가까운 **고정 커널**
    (예: 5 → [1, 4, 6, 4, 1] / 16)을 쓴다. 그래서 이 값은 "근사 sigma"로 기록한다.
    """
    _check_kernel_size(kernel_size)
    _check_sigma(sigma)
    if sigma > 0:
        return float(sigma)
    return 0.3 * ((kernel_size - 1) * 0.5 - 1) + 0.8


def apply_gaussian(gray: np.ndarray, kernel_size: int = 5,
                   sigma: float = 0.0) -> np.ndarray:
    """kernel_size는 양의 홀수, sigma >= 0, uint8 grayscale 반환.

    입력과 같은 크기의 새 배열을 돌려주고 입력은 수정하지 않는다.
    가장자리는 OpenCV 기본값(BORDER_REFLECT_101, 경계에서 거울처럼 반사)으로 채운다.
    kernel_size=1이면 아무것도 섞지 않으므로 원본과 같은 영상이 나온다.
    잘못된 영상·파라미터는 ValidationError.
    """
    _check_gray(gray)
    _check_kernel_size(kernel_size)
    _check_sigma(sigma)

    size = int(kernel_size)
    return cv2.GaussianBlur(gray, (size, size), sigmaX=float(sigma), sigmaY=float(sigma))

"""Median 필터 (D 소유, TEAM_CONTRACT §4 D 계약)."""

import cv2
import numpy as np

from src.errors import ValidationError


def apply_median(gray: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Median 필터가 적용된 ``uint8`` 흑백 영상을 반환한다.

    입력 배열은 변경하지 않는다. 영상 규격이나 커널 크기가 계약과 다르면
    OpenCV 내부 오류 대신 ``ValidationError``를 발생시킨다.
    """
    if not isinstance(gray, np.ndarray):
        raise ValidationError("영상은 numpy.ndarray 형식이어야 합니다.")
    if gray.ndim != 2:
        raise ValidationError("영상은 2차원 흑백 배열이어야 합니다.")
    if gray.dtype != np.uint8:
        raise ValidationError("영상 자료형은 uint8이어야 합니다.")
    if min(gray.shape) < 32:
        raise ValidationError("영상의 가로와 세로는 각각 32픽셀 이상이어야 합니다.")

    if isinstance(kernel_size, bool) or not isinstance(kernel_size, int):
        raise ValidationError("커널 크기는 정수여야 합니다.")
    if kernel_size < 3 or kernel_size % 2 == 0:
        raise ValidationError("커널 크기는 3 이상의 홀수여야 합니다.")
    if kernel_size > min(gray.shape):
        raise ValidationError("커널 크기는 영상의 짧은 변보다 클 수 없습니다.")

    return cv2.medianBlur(gray, kernel_size)

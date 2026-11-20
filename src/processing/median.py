"""Median 필터 (D 소유, TEAM_CONTRACT §4 D 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""

import numpy as np


def apply_median(gray: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """kernel_size는 3 이상의 홀수. uint8 grayscale 반환."""
    raise NotImplementedError

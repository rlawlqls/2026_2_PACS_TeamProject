"""Gaussian 블러 (C 소유, TEAM_CONTRACT §4 C 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 C가 한다.
"""

import numpy as np


def apply_gaussian(gray: np.ndarray, kernel_size: int = 5,
                   sigma: float = 0.0) -> np.ndarray:
    """kernel_size는 양의 홀수, sigma >= 0, uint8 grayscale 반환."""
    raise NotImplementedError

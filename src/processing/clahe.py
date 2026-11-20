"""CLAHE 대비 개선 (B 소유, TEAM_CONTRACT §4 B 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 B가 한다.
"""

import numpy as np


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0,
                tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """uint8 grayscale 반환. clip_limit > 0, tile_grid_size 각 정수 >= 1."""
    raise NotImplementedError

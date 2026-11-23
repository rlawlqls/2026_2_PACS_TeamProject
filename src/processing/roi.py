"""ROI 통계 (B 소유, TEAM_CONTRACT §4 B 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 B가 한다.
"""

import numpy as np


def get_roi_stats(gray: np.ndarray, roi: dict) -> dict:
    """roi={'x':int,'y':int,'width':int,'height':int};
    반환 {'roi': roi, 'mean':float, 'variance':float,
          'std':float, 'min':int, 'max':int,
          'histogram':list[int], 'pixel_count':int}.
    유효하지 않거나 영역 밖이면 ValidationError.
    """
    raise NotImplementedError

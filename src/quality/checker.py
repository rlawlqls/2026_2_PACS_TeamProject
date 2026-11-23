"""화질 자동 점검 (C 소유, TEAM_CONTRACT §4 C 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 C가 한다.
"""

import numpy as np


def check_quality(gray: np.ndarray, thresholds: dict) -> dict:
    """밝기/대비/흐림 기초 지표 측정 후 팀 규칙에 따라 판정.
    결과는 아래 표준 결과 dict 형식을 정확히 따름.
    외부 DB/API 쓰기 없음. 재현 가능해야 함.
    """
    raise NotImplementedError

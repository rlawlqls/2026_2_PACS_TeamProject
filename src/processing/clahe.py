"""CLAHE 대비 개선 (B 소유, TEAM_CONTRACT §4 B 계약).

목적: 어둡거나 명암 차이가 작은 영상에서 구조가 더 잘 보이도록 **국소 대비**를 높인다.
영상을 격자(tile)로 나누고 칸마다 히스토그램 평활화를 한 뒤, 칸 경계가 보이지 않도록
이웃 칸의 결과를 보간해 잇는다 (CLAHE: Contrast Limited Adaptive Histogram Equalization).

- `clip_limit`: 히스토그램 한 칸(bin)에 몰릴 수 있는 픽셀 수의 상한(배수). 클수록 대비가
  강해지지만 잡음도 같이 커진다.
- `tile_grid_size`: 영상을 나누는 격자 수 `(가로 칸 수, 세로 칸 수)`. 클수록 더 좁은 영역
  기준으로 대비를 맞춘다.

한계: 밝기 값을 바꾸는 처리이므로 결과 영상의 픽셀값은 원본의 물리적 의미(감쇠량)와 다르다.
균일한 영역의 잡음이 강조될 수 있다. 비교 실험은 `docs/experiments/clahe.md`에 기록한다.
"""

import math
from numbers import Real

import cv2
import numpy as np

from src.errors import ValidationError

#: 처리 이력(processing_runs)의 algorithm 값
ALGORITHM_NAME = "clahe"
#: 처리 이력의 algorithm_version. 동작이 바뀌면 올린다.
ALGORITHM_VERSION = "1.0.0"
#: 이 값 이상의 clip_limit은 모두 "자르지 않음"으로 같다 (히스토그램 bin이 256개라서)
MAX_CLIP_LIMIT = 256.0


def _check_gray(gray: np.ndarray) -> None:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상은 (H, W) 모양의 uint8 grayscale 배열이어야 합니다.")
    if gray.size == 0:
        raise ValidationError("빈 영상은 처리할 수 없습니다.")


def _check_clip_limit(clip_limit: float) -> None:
    # bool은 int의 하위 타입이라 True가 1.0으로 통과하지 않도록 먼저 막는다.
    if isinstance(clip_limit, bool) or not isinstance(clip_limit, Real):
        raise ValidationError("clip_limit은 숫자여야 합니다.")
    try:
        finite = math.isfinite(clip_limit)
    except OverflowError:  # float으로 바꿀 수 없을 만큼 큰 정수 (예: 10**400)
        finite = False
    if not finite or clip_limit <= 0:
        raise ValidationError("clip_limit은 0보다 큰 유한한 수여야 합니다.")


def _check_tile_grid_size(tile_grid_size: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(tile_grid_size, (tuple, list)) or len(tile_grid_size) != 2:
        raise ValidationError("tile_grid_size는 (가로 칸 수, 세로 칸 수) 두 정수여야 합니다.")
    for value in tile_grid_size:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValidationError("tile_grid_size의 각 값은 정수여야 합니다.")
        if value < 1:
            raise ValidationError("tile_grid_size의 각 값은 1 이상이어야 합니다.")
    return int(tile_grid_size[0]), int(tile_grid_size[1])


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0,
                tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """uint8 grayscale 반환. clip_limit > 0, tile_grid_size 각 정수 >= 1.

    입력과 같은 크기의 새 배열을 돌려주고 입력은 수정하지 않는다.
    tile_grid_size는 OpenCV와 같은 `(가로 칸 수, 세로 칸 수)` 순서다.
    잘못된 영상·파라미터는 ValidationError.

    극단값은 거절하지 않고 뜻이 같은 안전한 값으로 바꿔 OpenCV에 넘긴다:
    - clip_limit이 256을 넘으면 256으로 계산한다. 한 bin에는 칸의 픽셀 수보다 많이 몰릴 수
      없어서 256 이상은 모두 "자르지 않음"으로 같다. (그대로 넘기면 OpenCV 내부 정수가
      넘쳐 오히려 가장 약한 대비가 나온다.)
    - 칸 수는 칸 하나가 최소 2픽셀이 되도록 변마다 `변 길이 // 2`(최소 1)까지만 쓴다.
      그보다 잘게 나누면 칸마다 통계를 낼 픽셀이 없어 결과가 무의미하고 메모리만 쓴다.
    """
    _check_gray(gray)
    _check_clip_limit(clip_limit)
    tiles_x, tiles_y = _check_tile_grid_size(tile_grid_size)

    height, width = gray.shape
    tiles = (min(tiles_x, max(1, width // 2)), min(tiles_y, max(1, height // 2)))
    clahe = cv2.createCLAHE(clipLimit=min(float(clip_limit), MAX_CLIP_LIMIT), tileGridSize=tiles)
    return clahe.apply(gray)

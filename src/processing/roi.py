"""ROI 통계 (B 소유, TEAM_CONTRACT §4 B 계약).

사각형 관심 영역(ROI) 안의 픽셀값 통계를 계산한다.

- 좌표 원점은 영상의 왼쪽 위 `(x=0, y=0)`, x는 오른쪽, y는 아래쪽 (§3.1).
- 영역은 반열림 구간 `gray[y:y+height, x:x+width]`이다.
- 분산·표준편차는 모집단 기준(`ddof=0`)이고, 픽셀값(0~255) 그대로 계산한다.
- 히스토그램은 256개 bin 고정이며 합계는 `pixel_count`와 같다.
"""

import numpy as np

from src.errors import ValidationError

ROI_KEYS = ("x", "y", "width", "height")
HISTOGRAM_BINS = 256


def _check_gray(gray: np.ndarray) -> None:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상은 (H, W) 모양의 uint8 grayscale 배열이어야 합니다.")
    if gray.size == 0:
        raise ValidationError("빈 영상은 처리할 수 없습니다.")


def _check_roi(roi: dict, shape: tuple[int, int]) -> dict:
    """roi를 검사하고 파이썬 int 네 개만 담은 새 dict를 돌려준다 (입력 dict는 수정하지 않음)."""
    if not isinstance(roi, dict):
        raise ValidationError("ROI는 x, y, width, height를 담은 dict여야 합니다.")
    missing = [key for key in ROI_KEYS if key not in roi]
    if missing:
        raise ValidationError(f"ROI에 {', '.join(missing)} 값이 없습니다.")
    for key in ROI_KEYS:
        value = roi[key]
        # bool은 int의 하위 타입이라 True가 1로 통과하지 않도록 먼저 막는다.
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValidationError(f"ROI의 {key}는 정수여야 합니다.")
    clean = {key: int(roi[key]) for key in ROI_KEYS}

    height, width = shape
    if clean["x"] < 0 or clean["y"] < 0:
        raise ValidationError("ROI의 x, y는 0 이상이어야 합니다.")
    if clean["width"] <= 0 or clean["height"] <= 0:
        raise ValidationError("ROI의 width, height는 1 이상이어야 합니다.")
    if clean["x"] + clean["width"] > width or clean["y"] + clean["height"] > height:
        raise ValidationError(
            f"ROI가 영상 범위를 벗어났습니다 (영상 크기: 가로 {width}, 세로 {height})."
        )
    return clean


def get_roi_stats(gray: np.ndarray, roi: dict) -> dict:
    """roi={'x':int,'y':int,'width':int,'height':int};
    반환 {'roi': roi, 'mean':float, 'variance':float,
          'std':float, 'min':int, 'max':int,
          'histogram':list[int], 'pixel_count':int}.
    유효하지 않거나 영역 밖이면 ValidationError.

    반환값은 모두 파이썬 기본 자료형이라 JSON/Firestore에 그대로 저장할 수 있다 (§3.1).
    입력 영상과 roi dict는 수정하지 않는다.
    """
    _check_gray(gray)
    clean = _check_roi(roi, gray.shape)

    x, y, width, height = (clean[key] for key in ROI_KEYS)
    region = gray[y:y + height, x:x + width]
    histogram = np.bincount(region.ravel(), minlength=HISTOGRAM_BINS)

    return {
        "roi": clean,
        "mean": float(np.mean(region)),
        "variance": float(np.var(region)),  # ddof=0 (모집단 분산)
        "std": float(np.std(region)),
        "min": int(region.min()),
        "max": int(region.max()),
        "histogram": [int(count) for count in histogram],
        "pixel_count": int(region.size),
    }

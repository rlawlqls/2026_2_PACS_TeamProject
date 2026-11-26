"""화질 자동 점검 (C 소유, TEAM_CONTRACT §4 C 계약, #26).

목적: 등록된 영상이 **너무 어둡거나 밝은지, 대비가 낮은지, 흐린지**를 숫자로 재서
"사람이 한 번 더 확인해야 하는 영상"을 표시한다. 진단이 아니라 확인 단계를 돕는 교육용 기능이다.

지표 3개 (계약 §4 구현 식 그대로, 8-bit grayscale 기준):

- 밝기 평균 `brightness_mean = np.mean(gray)` — 낮으면 어둡고, 높으면 밝다.
- 대비 `contrast_std = np.std(gray)` — 밝기가 얼마나 넓게 퍼져 있는지. 작으면 밋밋하다.
- 선명도 `laplacian_variance = cv2.Laplacian(gray, cv2.CV_64F).var()` — Laplacian은 밝기가
  급하게 바뀌는 곳(경계)에서 크게 반응한다. 그 분산이 작으면 경계가 적다 = 흐리다.

판정: 지표가 기준값(thresholds)을 벗어나면 사유를 붙이고 `needs_check`, 하나도 없으면 `pass`.
기준값과 **같으면 통과**로 본다 (`<`, `>`로 비교).

한계: `pass`여도 진단 가능·재촬영 불필요를 보장하지 않는다. Laplacian 분산은 영상 크기와
잡음에 크게 좌우되므로 기준값은 실제 영상으로 보정해야 한다 (§8.5 기록).
"""

import math
from numbers import Real

import cv2
import numpy as np

from src.errors import ValidationError

#: 점검 로직의 버전 (quality_checks.checker_version). 판정 방식이 바뀌면 올린다.
CHECKER_VERSION = "1.0.0"

# 경고 사유 코드 (계약 §4). 결과 reasons에는 이 순서대로 들어간다.
TOO_DARK = "too_dark"
TOO_BRIGHT = "too_bright"
LOW_CONTRAST = "low_contrast"
POSSIBLY_BLURRY = "possibly_blurry"

#: 화면 표시용 한글 이름 (계약 §4 매핑). 자동 점검 탭에서 쓴다.
REASON_LABELS = {
    TOO_DARK: "어두움",
    TOO_BRIGHT: "너무 밝음",
    LOW_CONTRAST: "낮은 대비",
    POSSIBLY_BLURRY: "흐림 의심",
}

#: thresholds에 반드시 있어야 하는 숫자 키 (계약 §4 thresholds 표준)
THRESHOLD_NUMBER_KEYS = (
    "brightness_min",
    "brightness_max",
    "contrast_std_min",
    "laplacian_var_min",
)


def _check_gray(gray: np.ndarray) -> None:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상은 (H, W) 모양의 uint8 grayscale 배열이어야 합니다.")
    if gray.size == 0:
        raise ValidationError("빈 영상은 점검할 수 없습니다.")


def _clean_thresholds(thresholds: dict) -> dict:
    """thresholds를 검사하고, 판정에 쓸 **새 dict**(표준 키 5개, 숫자는 float)를 돌려준다.

    새 dict를 만드는 이유: 결과에 담긴 thresholds를 나중에 누가 고쳐도 호출자가 넘긴 dict나
    DEFAULT_THRESHOLDS가 같이 바뀌지 않게 하고, numpy 숫자를 Firestore에 저장할 수 있는
    파이썬 float로 바꾸기 위해서다. 표준에 없는 키는 결과에 넣지 않는다.
    """
    if not isinstance(thresholds, dict):
        raise ValidationError("thresholds는 dict여야 합니다.")

    cleaned = {}
    for key in THRESHOLD_NUMBER_KEYS:
        if key not in thresholds:
            raise ValidationError(f"thresholds에 '{key}' 값이 없습니다.")
        value = thresholds[key]
        # bool은 int의 하위 타입이라 True가 1로 통과하지 않도록 먼저 막는다.
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValidationError(f"thresholds['{key}']는 숫자여야 합니다.")
        if not math.isfinite(value) or value < 0:
            raise ValidationError(f"thresholds['{key}']는 0 이상의 유한한 수여야 합니다.")
        cleaned[key] = float(value)

    if cleaned["brightness_min"] > cleaned["brightness_max"]:
        raise ValidationError("brightness_min이 brightness_max보다 클 수 없습니다.")

    version = thresholds.get("version")
    if not isinstance(version, str) or not version:
        raise ValidationError("thresholds['version']은 비어 있지 않은 문자열이어야 합니다.")
    cleaned["version"] = version
    return cleaned


def measure_metrics(gray: np.ndarray) -> dict:
    """지표 3개만 잰다 (판정 없음). 기준값 보정 실험에서도 같은 식을 쓰기 위해 분리했다.

    값은 파이썬 float (numpy float는 Firestore 저장 시 문제가 될 수 있어 변환).
    잘못된 영상은 ValidationError.
    """
    _check_gray(gray)
    return {
        "brightness_mean": float(np.mean(gray)),
        "contrast_std": float(np.std(gray)),
        "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
    }


def check_quality(gray: np.ndarray, thresholds: dict) -> dict:
    """밝기/대비/흐림 기초 지표 측정 후 팀 규칙에 따라 판정.
    결과는 아래 표준 결과 dict 형식을 정확히 따름.
    외부 DB/API 쓰기 없음. 재현 가능해야 함.

    반환::

        {
            "status": "pass" | "needs_check",
            "metrics": {"brightness_mean", "contrast_std", "laplacian_variance"},
            "reasons": [...],        # too_dark/too_bright → low_contrast → possibly_blurry
            "thresholds": {...},     # 실제 적용한 기준값의 복사본
            "checker_version": CHECKER_VERSION,
        }

    입력 영상과 thresholds는 수정하지 않는다. 잘못된 영상·thresholds는 ValidationError.
    """
    # thresholds를 먼저 검사한다: 기준값이 틀렸으면 영상을 재 볼 필요가 없다.
    applied = _clean_thresholds(thresholds)
    metrics = measure_metrics(gray)

    reasons = []
    # 밝기: 평균 하나로 판정하므로 too_dark와 too_bright는 동시에 나올 수 없다.
    if metrics["brightness_mean"] < applied["brightness_min"]:
        reasons.append(TOO_DARK)
    elif metrics["brightness_mean"] > applied["brightness_max"]:
        reasons.append(TOO_BRIGHT)
    if metrics["contrast_std"] < applied["contrast_std_min"]:
        reasons.append(LOW_CONTRAST)
    if metrics["laplacian_variance"] < applied["laplacian_var_min"]:
        reasons.append(POSSIBLY_BLURRY)

    return {
        "status": "needs_check" if reasons else "pass",
        "metrics": metrics,
        "reasons": reasons,
        "thresholds": applied,
        "checker_version": CHECKER_VERSION,
    }

"""앱 설정 (A 소유).

DEFAULT_THRESHOLDS는 C 소유인 src/quality/thresholds.py에서 가져와 노출만 한다.
환경변수(APP_ENV 등) 설정은 app-skeleton 작업에서 추가한다.
"""

from src.quality.thresholds import DEFAULT_THRESHOLDS

__all__ = ["DEFAULT_THRESHOLDS"]

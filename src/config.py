"""앱 설정 (A 소유).

- DEFAULT_THRESHOLDS는 C 소유인 src/quality/thresholds.py에서 가져와 노출만 한다.
- 환경변수는 저장소 루트의 .env에서 읽는다 (.env는 커밋 금지, 예시는 .env.example).
- 환경변수 값(키·경로 등)은 로그나 화면에 출력하지 않는다.
"""

import os

from dotenv import load_dotenv

from src.quality.thresholds import DEFAULT_THRESHOLDS

# .env를 읽어 os.environ에 넣는다. 이미 설정된 환경변수는 덮어쓰지 않는다.
load_dotenv()

# 개발 모드(§7.1)에서 로그인 대신 세션에 넣는 가상 사용자. 실제 Firebase 계정이 아니다.
DEV_USER = {
    "uid": "dev-admin",
    "role": "admin",
    "display_name": "개발용 관리자",
    "id_token": "",
}


def get_app_env() -> str:
    """APP_ENV 값. 설정이 없으면 안전하게 'production'으로 본다."""
    return os.getenv("APP_ENV", "production").strip().lower()


def is_dev_mode() -> bool:
    """APP_ENV가 정확히 'development'일 때만 True (§7.1).

    값이 없거나 오타가 나도 개발 모드(로그인 우회)는 꺼진 쪽으로 동작한다.
    """
    return get_app_env() == "development"


__all__ = ["DEFAULT_THRESHOLDS", "DEV_USER", "get_app_env", "is_dev_mode"]

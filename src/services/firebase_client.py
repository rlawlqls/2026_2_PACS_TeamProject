"""Firebase 초기화와 Firestore 공용 클라이언트 (A 소유, TEAM_CONTRACT §4·§11.3).

서비스 계정은 두 방법 중 하나로 받는다 (§11.3):
- FIREBASE_SERVICE_ACCOUNT_JSON: JSON 내용 자체 (JCloud 배포용)
- FIREBASE_SERVICE_ACCOUNT_PATH: 키 파일 경로 (로컬 개발용, 파일은 커밋 금지)

자격증명·키 내용·환경변수 값은 로그나 오류 메시지에 절대 넣지 않는다 (§4).
테스트에서는 conftest.py의 fake_db fixture가 get_db를 가짜 Firestore로 바꿔 끼운다.
"""

import json
import os

from src.errors import StorageError

_db = None


def _init_firebase() -> None:
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return

    json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    try:
        if json_str:
            cred = credentials.Certificate(json.loads(json_str))
        elif path and os.path.isfile(path):
            cred = credentials.Certificate(path)
        else:
            raise StorageError(
                "Firebase 서비스 계정이 설정되지 않았습니다. "
                ".env의 FIREBASE_SERVICE_ACCOUNT_PATH를 확인하세요 (개발 중에는 APP_ENV=development)."
            )
        options = {}
        if os.environ.get("FIREBASE_STORAGE_BUCKET"):  # firebase 저장소 모드일 때만
            options["storageBucket"] = os.environ["FIREBASE_STORAGE_BUCKET"]
        firebase_admin.initialize_app(cred, options)
    except StorageError:
        raise
    except Exception:  # 잘못된 JSON·키 형식 등. 원인에 키 내용이 섞일 수 있어 연결(from)하지 않는다.
        raise StorageError("Firebase 초기화에 실패했습니다. 서비스 계정 설정을 확인하세요.") from None


def get_db():
    """Firestore 클라이언트. Firebase 초기화는 한 번만 수행 (§11.3)."""
    global _db
    if _db is None:
        _init_firebase()
        from firebase_admin import firestore

        _db = firestore.client()
    return _db

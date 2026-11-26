"""로그인·역할 확인 (A 소유, TEAM_CONTRACT §4·§10.5).

로그인 순서 (§10.5):
1. Firebase Auth REST API에 이메일·비밀번호를 보낸다 (FIREBASE_WEB_API_KEY 사용).
2. 돌려받은 idToken을 Admin SDK로 검증해 uid를 얻는다 (응답을 그대로 믿지 않는다).
3. Firestore users/{uid}에서 role·active·display_name을 읽는다.

보안 규칙
- 실패 메시지는 원인(없는 계정/틀린 비밀번호 등)을 구분하지 않는다.
- 비밀번호·토큰·API 키는 로그와 오류 메시지에 절대 넣지 않는다.
- 로그인한 uid·role은 화면이 st.session_state["auth_user"]에 보관하고,
  서비스 함수에는 actor_uid(또는 registered_by)로 넘긴다 (§6.1 검사 위치).
"""

import logging
import os

import requests

from src.errors import PermissionDeniedError, StorageError
from src.services import firebase_client

logger = logging.getLogger(__name__)

ROLES = ("registrar", "reviewer", "admin")
SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
REQUEST_TIMEOUT = 10  # 초

LOGIN_FAILED = "이메일 또는 비밀번호가 올바르지 않습니다."
LOGIN_UNAVAILABLE = "지금은 로그인할 수 없습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요."


def _load_user(uid: str) -> dict:
    """users/{uid} 문서를 읽고 검증한다. 없거나 비활성·잘못된 역할이면 PermissionDeniedError."""
    if not isinstance(uid, str) or not uid.strip():
        raise PermissionDeniedError("로그인이 필요합니다.")
    try:
        snap = firebase_client.get_db().collection("users").document(uid).get()
    except Exception as err:
        logger.error("사용자 정보 조회 실패: %s", type(err).__name__)
        raise PermissionDeniedError(LOGIN_UNAVAILABLE) from None
    user = snap.to_dict() if snap.exists else None
    if not user or user.get("active") is not True:
        raise PermissionDeniedError("사용할 수 없는 계정입니다. 관리자에게 문의하세요.")
    if user.get("role") not in ROLES:
        raise PermissionDeniedError("계정에 역할이 지정되지 않았습니다. 관리자에게 문의하세요.")
    return user


def _verify_id_token(id_token: str) -> str:
    """idToken을 Admin SDK로 검증하고 uid를 반환한다."""
    from firebase_admin import auth as firebase_auth

    firebase_client.get_db()  # Firebase 앱 초기화를 보장한다 (한 번만 수행)
    return firebase_auth.verify_id_token(id_token)["uid"]


def login(email: str, password: str) -> dict:
    """Firebase Auth REST 로그인(§10.5). 반환 {'uid','role','display_name','id_token'};
    실패하면 PermissionDeniedError (원인은 구분하지 않는 일반 메시지)."""
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
        raise PermissionDeniedError(LOGIN_FAILED)

    api_key = os.environ.get("FIREBASE_WEB_API_KEY", "").strip()
    if not api_key:
        logger.error("FIREBASE_WEB_API_KEY가 설정되지 않음")
        raise PermissionDeniedError(LOGIN_UNAVAILABLE)

    try:
        response = requests.post(
            SIGN_IN_URL,
            params={"key": api_key},
            json={"email": email.strip(), "password": password, "returnSecureToken": True},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as err:
        # 예외 문자열에는 URL(API 키 포함)이 들어갈 수 있어 종류만 남긴다.
        logger.error("로그인 서버 연결 실패: %s", type(err).__name__)
        raise PermissionDeniedError(LOGIN_UNAVAILABLE) from None

    if response.status_code != 200:
        raise PermissionDeniedError(LOGIN_FAILED)
    try:
        id_token = (response.json() or {}).get("idToken")
    except ValueError:
        id_token = None
    if not id_token:
        raise PermissionDeniedError(LOGIN_FAILED)

    try:
        uid = _verify_id_token(id_token)
    except StorageError:
        # 서비스 계정 미설정 등 서버 쪽 문제 → 비밀번호 탓으로 안내하지 않는다.
        logger.error("Firebase 초기화 실패로 토큰을 검증하지 못함")
        raise PermissionDeniedError(LOGIN_UNAVAILABLE) from None
    except Exception as err:
        logger.error("ID 토큰 검증 실패: %s", type(err).__name__)
        raise PermissionDeniedError(LOGIN_FAILED) from None

    user = _load_user(uid)
    return {
        "uid": uid,
        "role": user["role"],
        "display_name": str(user.get("display_name") or ""),
        "id_token": id_token,
    }


def get_user_role(uid: str) -> str:
    """users/{uid}.role ('registrar'/'reviewer'/'admin'); 문서가 없거나 active가 false면 PermissionDeniedError."""
    return _load_user(uid)["role"]

"""로그인·역할 확인 테스트 (A 소유) — 비로그인·권한 없음 거절 (TEAM_CONTRACT §2·§10.5).

Firebase에 실제로 접속하지 않는다: 가짜 Firestore(fake_db) + 로그인 서버 응답·토큰 검증을 가짜로 바꿔 끼운다.
"""

import logging

import pytest
import requests

from src.errors import PermissionDeniedError, StorageError
from src.services import auth

API_KEY = "test-api-key-not-real"
PASSWORD = "pw-should-never-be-logged"
TOKEN = "token-should-never-be-logged"
USERS = {
    "uid_reg": {"display_name": "박접수", "role": "registrar", "active": True},
    "uid_rev": {"display_name": "김검토", "role": "reviewer", "active": True},
    "uid_off": {"display_name": "퇴사자", "role": "reviewer", "active": False},
    "uid_norole": {"display_name": "역할없음", "role": "", "active": True},
}
ACCOUNTS = {"reg@pacs.test": "uid_reg", "rev@pacs.test": "uid_rev", "off@pacs.test": "uid_off"}


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload

    def json(self):
        return self._payload


@pytest.fixture
def firebase(fake_db, monkeypatch):
    """가짜 users 문서 + 가짜 로그인 서버 + 가짜 토큰 검증."""
    fake_db.data["users"] = {uid: dict(doc) for uid, doc in USERS.items()}
    monkeypatch.setenv("FIREBASE_WEB_API_KEY", API_KEY)
    calls = []

    def fake_post(url, params=None, json=None, timeout=None):
        calls.append({"url": url, "params": params, "json": json, "timeout": timeout})
        uid = ACCOUNTS.get(json["email"])
        if uid is None or json["password"] != PASSWORD:
            return FakeResponse(400, {"error": {"message": "INVALID_LOGIN_CREDENTIALS"}})
        return FakeResponse(200, {"idToken": f"{TOKEN}:{uid}", "localId": uid})

    monkeypatch.setattr(auth.requests, "post", fake_post)
    monkeypatch.setattr(auth, "_verify_id_token", lambda token: token.split(":", 1)[1])
    return calls


# --- 정상 ---------------------------------------------------------------------

def test_login_returns_contract_fields(firebase):
    user = auth.login("rev@pacs.test", PASSWORD)
    assert set(user) == {"uid", "role", "display_name", "id_token"}
    assert user["uid"] == "uid_rev" and user["role"] == "reviewer" and user["display_name"] == "김검토"
    assert firebase[0]["params"] == {"key": API_KEY} and firebase[0]["timeout"]


@pytest.mark.parametrize("uid, role", [("uid_reg", "registrar"), ("uid_rev", "reviewer")])
def test_get_user_role_reads_users_document(firebase, uid, role):
    assert auth.get_user_role(uid) == role


# --- 오류 ---------------------------------------------------------------------

@pytest.mark.parametrize("email, password", [
    ("rev@pacs.test", "wrong"),       # 틀린 비밀번호
    ("nobody@pacs.test", PASSWORD),   # 없는 계정
    ("", PASSWORD), ("rev@pacs.test", ""),
])
def test_login_failures_share_one_message(firebase, email, password):
    with pytest.raises(PermissionDeniedError) as exc:
        auth.login(email, password)
    assert str(exc.value) == auth.LOGIN_FAILED  # 원인을 구분하지 않는다 (§10.5)


def test_inactive_account_cannot_login(firebase):
    with pytest.raises(PermissionDeniedError):
        auth.login("off@pacs.test", PASSWORD)


@pytest.mark.parametrize("uid", ["uid_off", "uid_norole", "uid_missing", "", None])
def test_get_user_role_rejects_bad_accounts(firebase, uid):
    with pytest.raises(PermissionDeniedError):
        auth.get_user_role(uid)


def test_network_error_does_not_leak_api_key(firebase, monkeypatch, caplog):
    def broken_post(*args, **kwargs):
        raise requests.ConnectionError(f"failed to reach url?key={API_KEY}")

    monkeypatch.setattr(auth.requests, "post", broken_post)
    with caplog.at_level(logging.DEBUG), pytest.raises(PermissionDeniedError) as exc:
        auth.login("rev@pacs.test", PASSWORD)
    assert str(exc.value) == auth.LOGIN_UNAVAILABLE
    assert API_KEY not in caplog.text and exc.value.__cause__ is None


def test_missing_api_key_is_reported_as_unavailable(firebase, monkeypatch):
    monkeypatch.delenv("FIREBASE_WEB_API_KEY")
    with pytest.raises(PermissionDeniedError) as exc:
        auth.login("rev@pacs.test", PASSWORD)
    assert str(exc.value) == auth.LOGIN_UNAVAILABLE


def test_firebase_not_configured_is_not_blamed_on_password(firebase, monkeypatch):
    def not_configured(token):
        raise StorageError("서비스 계정 미설정")

    monkeypatch.setattr(auth, "_verify_id_token", not_configured)
    with pytest.raises(PermissionDeniedError) as exc:
        auth.login("rev@pacs.test", PASSWORD)
    assert str(exc.value) == auth.LOGIN_UNAVAILABLE


def test_forged_token_is_rejected(firebase, monkeypatch):
    def bad_token(token):
        raise ValueError("invalid signature")

    monkeypatch.setattr(auth, "_verify_id_token", bad_token)
    with pytest.raises(PermissionDeniedError) as exc:
        auth.login("rev@pacs.test", PASSWORD)
    assert str(exc.value) == auth.LOGIN_FAILED


def test_password_and_token_never_logged(firebase, caplog):
    with caplog.at_level(logging.DEBUG):
        auth.login("rev@pacs.test", PASSWORD)
        with pytest.raises(PermissionDeniedError):
            auth.login("rev@pacs.test", "wrong")
    assert PASSWORD not in caplog.text and TOKEN not in caplog.text

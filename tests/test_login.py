"""로그인 화면·로그아웃 테스트 (A 소유, #41).

실제 Firebase에 접속하지 않도록 auth.login을 가짜 함수로 바꾼다.
배포 모드(APP_ENV=production)에서 실행해 개발 모드 우회가 끼어들지 않게 한다.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.errors import PermissionDeniedError
from src.services import auth

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")
REVIEWER = {"uid": "uid_rev", "role": "reviewer", "display_name": "테스트 검토자", "id_token": "tok"}


@pytest.fixture
def prod(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    calls = []

    def fake_login(email, password):
        calls.append(email)
        if email == "reviewer@pacs.test" and password == "right-pw":
            return dict(REVIEWER)
        raise PermissionDeniedError(auth.LOGIN_FAILED)

    monkeypatch.setattr(auth, "login", fake_login)
    return calls


def _submit(at, email, password):
    at.text_input[0].input(email)
    at.text_input[1].input(password)
    next(b for b in at.button if b.label == "로그인").click()
    return at.run()


# --- 정상 ---------------------------------------------------------------------

def test_login_success_opens_app_with_role(prod):
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception and len(at.tabs) == 0  # 로그인 전에는 탭이 없다

    _submit(at, "reviewer@pacs.test", "right-pw")
    assert not at.exception
    assert at.session_state["auth_user"] == REVIEWER
    assert len(at.tabs) == 5
    assert any("테스트 검토자" in m.value for m in at.markdown)  # 헤더에 이름


def test_logout_clears_session_and_returns_to_login(prod):
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["auth_user"] = dict(REVIEWER)
    at.session_state["selected_case_id"] = "case_old"
    at.run()
    assert len(at.tabs) == 5

    next(b for b in at.button if b.label == "로그아웃").click()
    at.run()
    assert not at.exception
    assert "auth_user" not in at.session_state
    assert "selected_case_id" not in at.session_state  # 이전 사용자의 선택이 남지 않는다
    assert len(at.tabs) == 0 and any(b.label == "로그인" for b in at.button)


def test_dev_mode_skips_login_and_hides_logout(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception and len(at.tabs) == 5
    assert not any(b.label == "로그아웃" for b in at.button)


# --- 오류 ---------------------------------------------------------------------

def test_wrong_password_shows_generic_message_and_keeps_no_password(prod):
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _submit(at, "reviewer@pacs.test", "wrong-pw")
    assert not at.exception
    assert "auth_user" not in at.session_state
    assert [e.value for e in at.error] == [auth.LOGIN_FAILED]
    assert len(at.tabs) == 0
    # 코드가 읽을 수 있는 세션 값 어디에도 비밀번호가 남지 않는다
    assert all("wrong-pw" not in str(v) for v in at.session_state.filtered_state.values())


def test_unexpected_error_does_not_leak_details(prod, monkeypatch):
    def broken(email, password):
        raise RuntimeError("secret-detail-from-server")

    monkeypatch.setattr(auth, "login", broken)
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    _submit(at, "reviewer@pacs.test", "right-pw")
    assert "auth_user" not in at.session_state
    assert at.error and all("secret-detail" not in e.value for e in at.error)

"""앱 전체 실행 테스트 (A 총괄, 전원 참여).

Streamlit 내장 테스트 도구(AppTest)로 브라우저 없이 app.py를 한 번 실행해 본다.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")
TAB_LABELS = ["케이스 목록", "영상 등록", "뷰어·ROI", "자동 점검", "검토·이력"]


def test_app_runs_in_dev_mode_with_all_tabs(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert not at.exception
    assert [tab.label for tab in at.tabs] == TAB_LABELS
    assert at.session_state["auth_user"]["role"] == "admin"
    assert at.session_state["selected_image_id"].startswith("img_")


def test_app_requires_login_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert not at.exception
    assert len(at.tabs) == 0                      # 로그인 전에는 탭이 보이지 않는다
    assert "auth_user" not in at.session_state     # 개발용 가상 사용자가 들어가지 않는다

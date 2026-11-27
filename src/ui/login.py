"""로그인 화면 (A 소유, TEAM_CONTRACT §7·§10.5). 외부에는 render()만 내보낸다.

- 이메일·비밀번호 → auth.login() → st.session_state["auth_user"]에 {uid, role, display_name, id_token} 저장
- 실패 안내는 auth가 만든 메시지를 그대로 보여 준다 (없는 계정·틀린 비밀번호를 구분하지 않음).
- 비밀번호는 session_state에 키로 남기지 않고, 제출하면 입력칸을 비운다 (clear_on_submit).
- 로그아웃은 app.py 헤더 옆 버튼이 session_state를 비우는 방식으로 처리한다.
"""

import streamlit as st

from src.services import auth
from src.ui import style


def _try_login(email: str, password: str) -> bool:
    """로그인에 성공하면 세션에 사용자 정보를 넣고 True. 실패하면 안내를 보여 주고 False."""
    try:
        user = auth.login(email, password)
    except Exception as err:  # AppError는 메시지 그대로, 예상 못 한 오류는 일반 안내만 (상세는 로그)
        style.show_app_error(err)
        return False
    st.session_state["auth_user"] = user
    return True


def render() -> None:
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        st.markdown(
            f'<div class="pacs-header"><div class="pacs-logo">P</div>'
            f'<span class="pacs-title">{style.APP_NAME}</span>'
            f'<span class="pacs-pill">교육용 시연 · 실제 진료용 아님</span></div>',
            unsafe_allow_html=True,
        )
        style.page_header("로그인", "관리자가 발급한 계정으로 로그인합니다. 역할에 따라 보이는 기능이 다릅니다.")

        with st.form("auth_login_form", clear_on_submit=True):
            email = st.text_input("이메일", placeholder="name@pacs.test")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

        if submitted and _try_login(email, password):
            st.rerun()

        st.caption("계정이 없거나 역할을 바꿔야 하면 관리자에게 문의하세요.")

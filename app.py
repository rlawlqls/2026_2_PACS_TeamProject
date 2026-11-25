"""앱 진입점: 로그인 확인 → 탭 구조 (A 소유, TEAM_CONTRACT §2·§7).

실행: streamlit run app.py
각 탭의 내용은 src/ui/*.py의 render()가 그린다. 탭 담당자는 이 파일을 고치지 않는다.
"""

import streamlit as st

from src.config import DEV_USER, is_dev_mode
from src.ui import case_list, login, quality_panel, register, style, viewer, workflow_panel

st.set_page_config(page_title="영상 품질 자동 점검", page_icon="🩻", layout="wide")
style.apply_global_style()

dev_mode = is_dev_mode()

# 개발 모드(§7.1): 로그인을 건너뛰고 가상 관리자를 세션에 넣는다. production에서는 실행되지 않는다.
if dev_mode and "auth_user" not in st.session_state:
    st.session_state["auth_user"] = dict(DEV_USER)

user = st.session_state.get("auth_user")
if user is None:
    login.render()
    st.stop()

st.title("🩻 영상 품질 자동 점검")
if dev_mode:
    style.dev_mode_banner()
style.render_sidebar_user(user, dev_mode=dev_mode)

TABS = [
    ("케이스 목록", case_list.render),       # A
    ("영상 등록", register.render),          # A
    ("뷰어·ROI", viewer.render),             # B
    ("자동 점검", quality_panel.render),     # C
    ("검토·이력", workflow_panel.render),    # D
]

for tab, (_, render_tab) in zip(st.tabs([name for name, _ in TABS]), TABS):
    with tab:
        render_tab()

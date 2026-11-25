"""공통 테마·공용 UI 헬퍼 (A만 수정, TEAM_CONTRACT §2·§7).

모든 탭은 이 파일의 헬퍼를 써서 같은 디자인을 유지한다.
필요한 헬퍼가 없으면 직접 만들지 말고 A에게 요청한다.
"""

import logging

import streamlit as st

from src.errors import (
    AppError,
    NotFoundError,
    PermissionDeniedError,
    StateConflictError,
    StorageError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# 예외 메시지가 비어 있을 때 보여 줄 기본 한국어 안내
_DEFAULT_ERROR_MESSAGES = {
    ValidationError: "입력값을 확인해 주세요.",
    NotFoundError: "요청한 케이스나 영상을 찾을 수 없습니다.",
    PermissionDeniedError: "권한이 없거나 로그인이 필요합니다.",
    StateConflictError: "현재 상태에서는 이 작업을 할 수 없습니다.",
    StorageError: "저장소 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}

_ROLE_LABELS = {"registrar": "등록 담당", "reviewer": "검토 담당", "admin": "관리자"}

_GLOBAL_CSS = """
<style>
.block-container { padding-top: 2rem; }
.pacs-caption { color: #64748B; font-size: 0.9rem; margin-top: -0.5rem; }
</style>
"""


def apply_global_style() -> None:
    """app.py에서 한 번 호출한다. 탭 파일에서는 호출하지 않는다."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def page_header(title: str, caption: str = "") -> None:
    """탭 맨 위 제목과 한 줄 설명."""
    st.subheader(title)
    if caption:
        st.markdown(f'<p class="pacs-caption">{caption}</p>', unsafe_allow_html=True)


def todo_placeholder(owner: str, description: str) -> None:
    """아직 구현되지 않은 탭에 표시하는 안내 (담당자가 구현하면서 지운다)."""
    st.info(f"🚧 구현 예정 ({owner} 담당): {description}")


def show_app_error(err: Exception) -> None:
    """예외를 사용자용 한국어 안내로 보여 준다.

    AppError 계열은 메시지를 그대로 보여 주고, 예상 못 한 오류는
    로그에만 상세히 남기고 화면에는 민감정보 없는 일반 메시지를 보여 준다 (§4).
    """
    if isinstance(err, AppError):
        message = str(err) or _DEFAULT_ERROR_MESSAGES.get(type(err), "요청을 처리할 수 없습니다.")
        st.error(message)
        return
    logger.exception("예상하지 못한 오류", exc_info=err)
    st.error("예상하지 못한 오류가 발생했습니다. 문제가 계속되면 관리자에게 알려 주세요.")


def dev_mode_banner() -> None:
    """개발 모드가 켜져 있음을 눈에 띄게 알린다 (배포 환경에서 보이면 안 됨)."""
    st.warning("개발 모드입니다: 로그인 없이 가상 관리자와 샘플 영상으로 동작합니다. 배포 환경에서는 꺼져야 합니다.")


def render_sidebar_user(user: dict, dev_mode: bool = False) -> None:
    """사이드바에 로그인 사용자 이름과 역할을 보여 준다."""
    with st.sidebar:
        st.markdown("### 👤 사용자")
        st.write(user.get("display_name", ""))
        role = user.get("role", "")
        st.caption(f"역할: {_ROLE_LABELS.get(role, role)}")
        if dev_mode:
            st.caption("🛠 개발 모드")

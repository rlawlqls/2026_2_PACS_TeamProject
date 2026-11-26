"""공통 테마·공용 UI 헬퍼 (A만 수정, TEAM_CONTRACT §2·§7).

디자인 방향: "쓰기 쉬운 업무 시스템" — Pretendard 글꼴, 숫자는 고정폭, 알약형 버튼,
연회색 배경 위 흰 패널. 탭 담당자는 Streamlit 기본 위젯(st.button, st.image 등)을
그대로 쓰면 아래 CSS가 자동으로 적용된다. 필요한 헬퍼가 없으면 A에게 요청한다.

- 주 버튼: st.button("검토 완료", type="primary")  → 진한 파랑 알약
- 일반 버튼: st.button("취소")                     → 연한 파랑 알약
- 상태 배지: st.markdown(style.status_badge(case["status"]), unsafe_allow_html=True)
"""

import html
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

APP_NAME = "영상 품질 자동 점검"

# 예외 메시지가 비어 있을 때 보여 줄 기본 한국어 안내
_DEFAULT_ERROR_MESSAGES = {
    ValidationError: "입력값을 확인해 주세요.",
    NotFoundError: "요청한 케이스나 영상을 찾을 수 없습니다.",
    PermissionDeniedError: "권한이 없거나 로그인이 필요합니다.",
    StateConflictError: "현재 상태에서는 이 작업을 할 수 없습니다.",
    StorageError: "저장소 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
}

_ROLE_LABELS = {"registrar": "접수 담당", "reviewer": "검토 담당", "admin": "관리자"}

# 업무 상태(§6.2) → (화면 표시, 배지 색). 자동 점검 결과(needs_check)와는 다른 값이다.
STATUS_LABELS = {
    "registered": ("접수", "gray"),
    "assigned": ("배정", "blue"),
    "reviewing": ("검토 중", "blue"),
    "needs_review": ("재검토 요청", "orange"),
    "completed": ("완료", "green"),
}

_PRETENDARD_CSS = (
    "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
    "dist/web/variable/pretendardvariable-dynamic-subset.min.css"
)

_GLOBAL_CSS = f"""
<style>
@import url("{_PRETENDARD_CSS}");

:root {{
  --pacs-blue: #1264A3;
  --pacs-blue-dark: #075287;
  --pacs-blue-bg: #E9F3FC;
  --pacs-text: #192B3B;
  --pacs-muted: #657789;
  --pacs-border: #DCE4EB;
  --pacs-orange: #A85D10;
  --pacs-orange-bg: #FFF3DF;
  --pacs-green: #19744C;
  --pacs-green-bg: #E5F6ED;
  --pacs-image-bg: #131B24;
}}

/* 글꼴: Pretendard (연결 안 되면 시스템 글꼴), 숫자는 고정폭으로 자리 맞춤 */
html, body, .stApp, .stApp *:not(code):not(pre):not(svg):not(path) {{
  font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont,
               "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
}}
.stApp {{ font-variant-numeric: tabular-nums; }}

/* 화면 폭을 꽉 채운다 (영상을 크게 보기 위해 최대 폭 제한 없음) */
/* 위·양옆 여백을 같은 2rem으로 맞춘다. Streamlit 기본 상단 바(메뉴가 빠져 비어 있음)는 숨긴다. */
.block-container {{ padding: 2rem 2rem 3rem; max-width: 100%; }}
[data-testid="stHeader"], [data-testid="stDecoration"] {{ display: none; }}
/* 이 CSS를 넣는 빈 칸이 맨 위 자리를 차지하지 않게 한다 */
.element-container:has(> .stMarkdown style) {{ display: none; }}

/* 상단 헤더 바 */
.pacs-header {{
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: #FFFFFF; border: 1px solid var(--pacs-border); border-radius: 12px;
  padding: 12px 18px; margin-bottom: 14px;
}}
.pacs-logo {{
  width: 34px; height: 34px; border-radius: 9px; background: var(--pacs-blue);
  color: #FFFFFF; display: grid; place-items: center; font-weight: 700; font-size: 18px;
}}
.pacs-title {{ font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }}
.pacs-pill {{
  font-size: 11px; background: #EEF1F4; color: #536271; border-radius: 999px; padding: 3px 10px;
}}
.pacs-pill.dev {{ background: var(--pacs-orange-bg); color: var(--pacs-orange); font-weight: 600; }}
.pacs-grow {{ flex: 1; }}
.pacs-user {{ font-weight: 650; }}
.pacs-role {{ color: var(--pacs-muted); font-size: 13px; margin-left: 4px; }}
.pacs-who {{ white-space: nowrap; }}
/* 헤더 옆 로그아웃 버튼: 헤더와 세로 가운데를 맞추고 글자가 꺾이지 않게 한다 */
/* (헤더 높이 60px, 버튼 40px → 버튼을 10px 내린다) */
[data-testid="stHorizontalBlock"]:has(.pacs-header) > [data-testid="column"]:last-child button {{
  margin-top: 10px;
}}
[data-testid="stHorizontalBlock"]:has(.pacs-header) > [data-testid="column"]:last-child button p {{
  white-space: nowrap;
}}

/* 좁은 화면(노트북 창을 줄였을 때·태블릿): 여백을 줄여 내용 영역을 넓힌다 */
@media (max-width: 900px) {{
  .block-container {{ padding: 1rem 1rem 2rem; }}
  .stTabs [data-baseweb="tab-panel"] {{ padding: 16px; }}
  .pacs-pill {{ display: none; }}
}}

/* 탭: 선택된 탭은 연한 파랑 알약 */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{
  height: 40px; padding: 0 16px; border-radius: 999px; color: #526779;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
  background: var(--pacs-blue-bg); color: var(--pacs-blue-dark); font-weight: 700;
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* 탭 내용 영역 = 흰 패널 */
.stTabs [data-baseweb="tab-panel"] {{
  background: #FFFFFF; border: 1px solid var(--pacs-border); border-radius: 12px;
  padding: 22px 24px; margin-top: 8px;
}}

/* 버튼: 알약형. 주 버튼은 진한 파랑, 일반 버튼은 연한 파랑 배경 */
.stApp button[data-testid^="baseButton-primary"],
.stApp button[data-testid^="baseButton-secondary"] {{
  border-radius: 999px; min-height: 40px; padding: 6px 20px; font-weight: 600;
  transition: background-color .15s ease;
}}
.stApp button[data-testid^="baseButton-primary"] {{
  background: var(--pacs-blue); border: 1px solid var(--pacs-blue); color: #FFFFFF;
}}
.stApp button[data-testid^="baseButton-primary"]:hover {{
  background: var(--pacs-blue-dark); border-color: var(--pacs-blue-dark); color: #FFFFFF;
}}
.stApp button[data-testid^="baseButton-secondary"] {{
  background: var(--pacs-blue-bg); border: 1px solid transparent; color: var(--pacs-blue-dark);
}}
.stApp button[data-testid^="baseButton-secondary"]:hover {{
  background: #D6E9F8; border-color: transparent; color: var(--pacs-blue-dark);
}}
.stApp button:disabled {{ opacity: .5; }}

/* 입력칸: 흰 바탕 + 얇은 테두리, 안내 박스 모서리 */
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div,
.stApp [data-baseweb="textarea"] {{
  border-radius: 8px; background: #FFFFFF; border: 1px solid #BECBD7;
}}
.stApp [data-baseweb="input"] input, .stApp [data-baseweb="textarea"] textarea {{ background: #FFFFFF; }}
.stApp [data-testid="stAlert"] > div {{ border-radius: 10px; }}

/* markdown 표: 헤더 연회색, 가로줄만 */
.stApp [data-testid="stMarkdownContainer"] table {{ width: 100%; border-collapse: collapse; }}
.stApp [data-testid="stMarkdownContainer"] th {{
  text-align: left; font-size: 12px; color: #697B8D; background: #F8FAFC;
  border: none; border-bottom: 1px solid var(--pacs-border); padding: 10px 12px;
}}
.stApp [data-testid="stMarkdownContainer"] td {{
  border: none; border-bottom: 1px solid #EDF1F4; padding: 12px;
}}
.stApp [data-testid="stMarkdownContainer"] tr:last-child td {{ border-bottom: none; }}

/* 영상: 짙은 남색 배경 위에 표시 */
[data-testid="stImage"] {{
  background: var(--pacs-image-bg); border-radius: 10px; padding: 8px;
}}
[data-testid="stImageCaption"] {{ color: #C9D3DC; }}

/* 제목 아래 설명 */
.pacs-caption {{ color: var(--pacs-muted); font-size: 0.9rem; margin-top: -0.5rem; }}

/* 상태 배지 */
.pacs-badge {{
  display: inline-block; font-weight: 650; font-size: 12px; border-radius: 999px; padding: 4px 10px;
}}
.pacs-badge.gray {{ background: #EEF2F5; color: #536573; }}
.pacs-badge.blue {{ background: var(--pacs-blue-bg); color: #135E95; }}
.pacs-badge.green {{ background: var(--pacs-green-bg); color: var(--pacs-green); }}
.pacs-badge.orange {{ background: var(--pacs-orange-bg); color: var(--pacs-orange); }}
</style>
"""


def apply_global_style() -> None:
    """app.py에서 한 번 호출한다. 탭 파일에서는 호출하지 않는다."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def app_header(user: dict, dev_mode: bool = False) -> None:
    """상단 헤더 바: 로고·앱 이름·교육용 표시·사용자와 역할. app.py에서만 호출한다."""
    name = html.escape(str(user.get("display_name", "")))
    role = str(user.get("role", ""))
    role_label = html.escape(_ROLE_LABELS.get(role, role))
    dev_pill = '<span class="pacs-pill dev">개발 모드</span>' if dev_mode else ""
    st.markdown(
        f"""
<div class="pacs-header">
  <div class="pacs-logo">P</div>
  <span class="pacs-title">{APP_NAME}</span>
  <span class="pacs-pill">교육용 시연 · 실제 진료용 아님</span>
  {dev_pill}
  <div class="pacs-grow"></div>
  <span class="pacs-who"><span class="pacs-user">{name}</span> <span class="pacs-role">{role_label}</span></span>
</div>
""",
        unsafe_allow_html=True,
    )


def page_header(title: str, caption: str = "") -> None:
    """탭 맨 위 제목과 한 줄 설명."""
    st.subheader(title)
    if caption:
        st.markdown(f'<p class="pacs-caption">{html.escape(caption)}</p>', unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """업무 상태 코드(§6.2)를 색 배지 HTML로 바꾼다.

    사용: st.markdown(style.status_badge("reviewing"), unsafe_allow_html=True)
    모르는 상태 코드면 ValidationError.
    """
    if status not in STATUS_LABELS:
        raise ValidationError(f"알 수 없는 업무 상태입니다: {status}")
    label, color = STATUS_LABELS[status]
    return f'<span class="pacs-badge {color}">{label}</span>'


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

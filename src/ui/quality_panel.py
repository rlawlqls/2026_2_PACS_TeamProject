"""자동 점검 결과 탭 (C 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

A가 app-skeleton 작업에서 만든 stub이다. 실제 화면은 C가 구현한다.
선택된 영상: st.session_state.get("selected_image_id") → src.services.cases.load_image()
"""

from src.ui import style


def render() -> None:
    style.page_header("자동 화질 점검", "밝기·대비·흐림 지표와 경고 사유")
    style.todo_placeholder("C", "점수 3종, 적용 임계값, 경고 사유, 교육용 문구")

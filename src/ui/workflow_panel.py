"""검토·이력 탭 (D 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

A가 app-skeleton 작업에서 만든 stub이다. 실제 화면은 D가 구현한다.
선택된 케이스: st.session_state.get("selected_case_id") → src.services.cases.load_case()
"""

from src.ui import style


def render() -> None:
    style.page_header("검토·이력", "업무 상태 변경, 메모, 처리·검토 이력")
    style.todo_placeholder("D", "상태 변경 버튼, 사유, 담당자·이력, 리포트")

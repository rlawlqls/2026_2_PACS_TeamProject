"""영상 뷰어·ROI 탭 (B 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

A가 app-skeleton 작업에서 만든 stub이다. 실제 화면은 B가 구현한다.
선택된 영상: st.session_state.get("selected_image_id") → src.services.cases.load_image()
"""

from src.ui import style


def render() -> None:
    style.page_header("영상 뷰어·ROI", "원본/처리 결과 비교와 ROI 통계")
    style.todo_placeholder("B", "CLAHE·Gaussian·Median 처리, 원본/결과 비교, ROI 통계")

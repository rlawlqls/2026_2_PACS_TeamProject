"""케이스 목록 화면 (A 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

여기서 고른 케이스가 st.session_state["selected_case_id"], ["selected_image_id"]에 저장되고,
다른 탭은 이 두 키로 선택된 케이스·영상을 알 수 있다.
"""

import streamlit as st

from src.errors import AppError
from src.services.cases import search_cases
from src.ui import style


def render() -> None:
    style.page_header("케이스 목록", "선택한 케이스는 뷰어·자동 점검·검토 탭에서 함께 사용됩니다.")

    try:
        cases = search_cases()
    except NotImplementedError:
        style.todo_placeholder("A", "실제 케이스 조회(search_cases)는 Firebase 연결 후 구현합니다.")
        return
    except AppError as err:
        style.show_app_error(err)
        return

    if not cases:
        st.info("표시할 케이스가 없습니다.")
        return

    labels = {case["case_id"]: f'{case["case_label"]} · {case["description"]}' for case in cases}
    selected_case_id = st.selectbox(
        "케이스 선택",
        options=list(labels),
        format_func=labels.get,
    )
    selected = next(case for case in cases if case["case_id"] == selected_case_id)
    st.session_state["selected_case_id"] = selected["case_id"]
    st.session_state["selected_image_id"] = selected["image_id"]

    # TODO(A): 담당자·자동 점검 상태 표시, 처리할 업무/완료된 업무 필터 (§7)
    # st.dataframe은 현재 requirements 조합(pyarrow 미고정 + numpy 1.26.4)에서 오류가 나므로
    # pyarrow 버전 고정이 합의될 때까지 markdown 표로 그린다.
    rows = ["| 케이스 | 검사 종류 | 업무 상태 |", "|---|---|---|"]
    rows += [f'| {c["case_label"]} | {c["exam_type"]} | {c["status"]} |' for c in cases]
    st.markdown("\n".join(rows))

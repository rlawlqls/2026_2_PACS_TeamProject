"""영상 등록 화면 (A 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다."""

from src.ui import style


def render() -> None:
    style.page_header("영상 등록", "PNG/JPEG, 10MB 이하 grayscale 영상을 등록하면 자동 화질 점검이 실행됩니다.")
    # TODO(A): 업로드 → save_case → load_image → check_quality → save_quality_check (§7)
    style.todo_placeholder("A", "영상 업로드와 자동 점검 호출 흐름")

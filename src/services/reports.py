"""메모·리포트·이력 (D 소유, TEAM_CONTRACT §4 D 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""


def add_review_note(case_id: str, image_id: str,
                    actor_uid: str, content: str,
                    run_id: str | None = None) -> str:
    """메모 저장; 반환 note_id. 빈 메모 금지, 대상 케이스와 이미지 관계 확인."""
    raise NotImplementedError


def get_case_history(case_id: str) -> list[dict]:
    """업무 이벤트/메모/처리 기록을 조회 가능한 형태로 반환."""
    raise NotImplementedError

"""배정·업무 상태 전환 (D 소유, TEAM_CONTRACT §4 D 계약·§6).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""


def check_transition(current_status: str, action: str, actor_role: str,
                     is_assigned_reviewer: bool, note: str = "",
                     has_note_or_report: bool = False) -> str:
    """§6.2 표를 그대로 구현한다. 허용이면 다음 status를 반환한다.
    역할·담당 위반 → PermissionDeniedError,
    표에 없는 전이 또는 complete_review 조건(메모·리포트 1개 이상) 미충족 → StateConflictError,
    request_recheck의 사유(note)가 비어 있음 → ValidationError.
    """
    raise NotImplementedError


def transition_case(case_id: str, action: str,
                    actor_uid: str, note: str = "") -> dict:
    """로그인 사용자 역할·담당자·현재 상태/허용 전이 검사 후
    Firestore 트랜잭션으로 상태 및 event 이력 저장.
    반환: 변경 후 케이스 dict; 실패 시 PermissionDeniedError 또는 StateConflictError.
    """
    raise NotImplementedError


def assign_case(case_id: str, reviewer_uid: str, actor_uid: str) -> dict:
    """admin만 배정 가능; registered → assigned 처리 및 이벤트 저장."""
    raise NotImplementedError

"""배정·업무 상태 전환 (D 소유, TEAM_CONTRACT §4 D 계약·§6).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""

from src.errors import PermissionDeniedError, StateConflictError, ValidationError


_TRANSITIONS = {
    ("registered", "assign_case"): "assigned",
    ("assigned", "start_review"): "reviewing",
    ("reviewing", "request_recheck"): "needs_review",
    ("needs_review", "resume_review"): "reviewing",
    ("reviewing", "complete_review"): "completed",
}


def check_transition(current_status: str, action: str, actor_role: str,
                     is_assigned_reviewer: bool, note: str = "",
                     has_note_or_report: bool = False) -> str:
    """§6.2 표를 그대로 구현한다. 허용이면 다음 status를 반환한다.
    역할·담당 위반 → PermissionDeniedError,
    표에 없는 전이 또는 complete_review 조건(메모·리포트 1개 이상) 미충족 → StateConflictError,
    request_recheck의 사유(note)가 비어 있음 → ValidationError.
    """
    transition = (current_status, action)
    if transition not in _TRANSITIONS:
        raise StateConflictError(
            f"현재 상태 '{current_status}'에서는 '{action}' 작업을 수행할 수 없습니다."
        )

    if actor_role == "admin":
        pass
    elif actor_role == "reviewer":
        if action == "assign_case" or not is_assigned_reviewer:
            raise PermissionDeniedError("이 케이스를 처리할 권한이 없습니다.")
    else:
        raise PermissionDeniedError("업무 상태를 변경할 권한이 없습니다.")

    if action == "request_recheck":
        if not isinstance(note, str) or not note.strip():
            raise ValidationError("재검토 요청 사유를 입력해야 합니다.")

    if action == "complete_review" and not has_note_or_report:
        raise StateConflictError("검토 완료 전에 메모 또는 리포트가 필요합니다.")

    return _TRANSITIONS[transition]


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

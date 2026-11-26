"""배정·업무 상태 전환 (D 소유, TEAM_CONTRACT §4 D 계약·§6).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""

import uuid

from src.errors import (
    AppError,
    NotFoundError,
    PermissionDeniedError,
    StateConflictError,
    StorageError,
    ValidationError,
)
from src.services import firebase_client


_TRANSITIONS = {
    ("registered", "assign_case"): "assigned",
    ("assigned", "start_review"): "reviewing",
    ("reviewing", "request_recheck"): "needs_review",
    ("needs_review", "resume_review"): "reviewing",
    ("reviewing", "complete_review"): "completed",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _server_timestamp():
    from google.cloud.firestore import SERVER_TIMESTAMP

    return SERVER_TIMESTAMP


def _get_active_user(db, uid: str, *, target: bool = False) -> dict:
    if not isinstance(uid, str) or not uid.strip():
        raise PermissionDeniedError("로그인이 필요합니다.")

    snapshot = db.collection("users").document(uid).get()
    if not snapshot.exists:
        if target:
            raise NotFoundError("검토자 계정을 찾을 수 없습니다.")
        raise PermissionDeniedError("사용자 권한을 확인할 수 없습니다.")

    user = snapshot.to_dict() or {}
    if not user.get("active"):
        raise PermissionDeniedError("비활성 계정은 업무를 수행할 수 없습니다.")
    return user


def _has_note_or_report(db, case_id: str) -> bool:
    for collection_name in ("review_notes", "reports"):
        records = db.collection(collection_name).where(
            "case_id", "==", case_id
        ).stream()
        if next(iter(records), None) is not None:
            return True
    return False


def _run_transaction(db, operation):
    """실제 Firestore 트랜잭션 안에서 ``operation``을 실행한다."""
    from google.cloud import firestore

    transaction = db.transaction()

    @firestore.transactional
    def execute(transaction):
        return operation(transaction)

    return execute(transaction)


def _transaction_snapshot(transaction, document_ref):
    """실제 SDK의 snapshot generator와 테스트 fake snapshot을 모두 처리한다."""
    result = transaction.get(document_ref)
    if hasattr(result, "exists"):
        return result
    return next(iter(result), None)


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
    if not isinstance(case_id, str) or not case_id.strip():
        raise NotFoundError("케이스를 찾을 수 없습니다.")

    try:
        db = firebase_client.get_db()
        actor = _get_active_user(db, actor_uid)
        actor_role = actor.get("role", "")
        has_content = _has_note_or_report(db, case_id)
        case_ref = db.collection("cases").document(case_id)
        event_ref = db.collection("case_events").document(_new_id("evt_"))
        clean_note = note.strip() if isinstance(note, str) else ""

        def operation(transaction):
            snapshot = _transaction_snapshot(transaction, case_ref)
            if snapshot is None or not snapshot.exists:
                raise NotFoundError("케이스를 찾을 수 없습니다.")

            case = snapshot.to_dict() or {}
            current_status = case.get("status", "")
            assigned_uid = case.get("assigned_reviewer_uid")
            next_status = check_transition(
                current_status,
                action,
                actor_role,
                assigned_uid == actor_uid,
                note=note,
                has_note_or_report=has_content,
            )
            now = _server_timestamp()
            transaction.update(case_ref, {
                "status": next_status,
                "updated_at": now,
            })
            transaction.set(event_ref, {
                "case_id": case_id,
                "action": action,
                "from_status": current_status,
                "to_status": next_status,
                "actor_uid": actor_uid,
                "note": clean_note,
                "created_at": now,
            })
            return {
                "case_id": case_id,
                **case,
                "status": next_status,
                "updated_at": now,
            }

        return _run_transaction(db, operation)
    except AppError:
        raise
    except Exception as err:
        raise StorageError("업무 상태를 저장하지 못했습니다.") from err


def assign_case(case_id: str, reviewer_uid: str, actor_uid: str) -> dict:
    """admin만 배정 가능; registered → assigned 처리 및 이벤트 저장."""
    if not isinstance(case_id, str) or not case_id.strip():
        raise NotFoundError("케이스를 찾을 수 없습니다.")

    try:
        db = firebase_client.get_db()
        actor = _get_active_user(db, actor_uid)
        if actor.get("role") != "admin":
            raise PermissionDeniedError("관리자만 검토자를 배정할 수 있습니다.")

        reviewer = _get_active_user(db, reviewer_uid, target=True)
        if reviewer.get("role") != "reviewer":
            raise PermissionDeniedError("활성 검토자 계정만 배정할 수 있습니다.")

        case_ref = db.collection("cases").document(case_id)
        event_ref = db.collection("case_events").document(_new_id("evt_"))

        def operation(transaction):
            snapshot = _transaction_snapshot(transaction, case_ref)
            if snapshot is None or not snapshot.exists:
                raise NotFoundError("케이스를 찾을 수 없습니다.")

            case = snapshot.to_dict() or {}
            current_status = case.get("status", "")
            next_status = check_transition(
                current_status,
                "assign_case",
                actor_role="admin",
                is_assigned_reviewer=False,
            )
            now = _server_timestamp()
            transaction.update(case_ref, {
                "status": next_status,
                "assigned_reviewer_uid": reviewer_uid,
                "updated_at": now,
            })
            transaction.set(event_ref, {
                "case_id": case_id,
                "action": "assign_case",
                "from_status": current_status,
                "to_status": next_status,
                "actor_uid": actor_uid,
                "note": "",
                "created_at": now,
            })
            return {
                "case_id": case_id,
                **case,
                "status": next_status,
                "assigned_reviewer_uid": reviewer_uid,
                "updated_at": now,
            }

        return _run_transaction(db, operation)
    except AppError:
        raise
    except Exception as err:
        raise StorageError("검토자 배정을 저장하지 못했습니다.") from err

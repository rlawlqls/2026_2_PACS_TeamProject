"""배정·업무 상태 전환 (D 소유, TEAM_CONTRACT §4 D 계약·§6).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""

import uuid

from src.config import is_dev_mode
from src.errors import (
    AppError,
    NotFoundError,
    PermissionDeniedError,
    StateConflictError,
    StorageError,
    ValidationError,
)
from src.services import auth, firebase_client


_TRANSITIONS = {
    ("registered", "assign_case"): "assigned",
    ("assigned", "start_review"): "reviewing",
    ("reviewing", "request_recheck"): "needs_review",
    ("needs_review", "resume_review"): "reviewing",
    ("reviewing", "complete_review"): "completed",
}


#: 개발 모드에서 배정·상태 변경을 부르면 내는 안내 (TEAM_CONTRACT §7.1)
DEV_MODE_MESSAGE = (
    "개발 모드에서는 배정·업무 상태 변경을 저장하지 않습니다. "
    "상태 전이는 실제 Firebase에 연결해 확인합니다 (TEAM_CONTRACT §7.1)."
)


def _reject_dev_mode() -> None:
    """개발 모드는 화면 확인용이라 Firestore가 없다. Firebase 설정 오류처럼 보이지 않게 먼저 막는다."""
    if is_dev_mode():
        raise StorageError(DEV_MODE_MESSAGE)


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _server_timestamp():
    from google.cloud.firestore import SERVER_TIMESTAMP

    return SERVER_TIMESTAMP


def _check_assignable_reviewer(db, reviewer_uid: str) -> None:
    """배정 대상이 활성 reviewer인지 확인한다.

    계정이 없으면 NotFoundError(배정 화면에서 잘못 고른 경우), 있으면 실행자와 같은 기준
    (auth.get_user_role: active가 정확히 True, 역할 유효)으로 검사한다.
    """
    if not isinstance(reviewer_uid, str) or not reviewer_uid.strip():
        raise NotFoundError("검토자 계정을 찾을 수 없습니다.")
    if not db.collection("users").document(reviewer_uid).get().exists:
        raise NotFoundError("검토자 계정을 찾을 수 없습니다.")
    try:
        role = auth.get_user_role(reviewer_uid)
    except PermissionDeniedError:
        raise PermissionDeniedError("활성 검토자 계정만 배정할 수 있습니다.") from None
    if role != "reviewer":
        raise PermissionDeniedError("활성 검토자 계정만 배정할 수 있습니다.")


def _has_note_or_report(db, case_id: str) -> bool:
    # 위치 인자 where("case_id", "==", …)는 SDK가 UserWarning을 낸다 → cases.py와 같이 filter= 사용
    from google.cloud.firestore_v1.base_query import FieldFilter

    for collection_name in ("review_notes", "reports"):
        records = db.collection(collection_name).where(
            filter=FieldFilter("case_id", "==", case_id)
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
    개발 모드에서는 저장하지 않고 StorageError(DEV_MODE_MESSAGE)를 낸다.
    """
    _reject_dev_mode()
    if not isinstance(case_id, str) or not case_id.strip():
        raise NotFoundError("케이스를 찾을 수 없습니다.")

    try:
        db = firebase_client.get_db()
        actor_role = auth.get_user_role(actor_uid)  # §6.1: 역할은 auth에서 다시 읽는다
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
    """admin만 배정 가능; registered → assigned 처리 및 이벤트 저장.
    개발 모드에서는 저장하지 않고 StorageError(DEV_MODE_MESSAGE)를 낸다.
    """
    _reject_dev_mode()
    if not isinstance(case_id, str) or not case_id.strip():
        raise NotFoundError("케이스를 찾을 수 없습니다.")

    try:
        db = firebase_client.get_db()
        if auth.get_user_role(actor_uid) != "admin":  # §6.1: 역할은 auth에서 다시 읽는다
            raise PermissionDeniedError("관리자만 검토자를 배정할 수 있습니다.")
        _check_assignable_reviewer(db, reviewer_uid)

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

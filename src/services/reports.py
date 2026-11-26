"""메모·리포트·이력 (D 소유, TEAM_CONTRACT §4 D 계약).

A가 Day 0 선행 작업으로 만든 stub이다. 실제 구현은 D가 한다.
"""

import uuid

from src.errors import (
    AppError,
    NotFoundError,
    PermissionDeniedError,
    StorageError,
    ValidationError,
)
from src.services import firebase_client


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _server_timestamp():
    from google.cloud.firestore import SERVER_TIMESTAMP

    return SERVER_TIMESTAMP


def _get_active_actor(db, actor_uid: str) -> dict:
    if not isinstance(actor_uid, str) or not actor_uid.strip():
        raise PermissionDeniedError("로그인이 필요합니다.")

    snapshot = db.collection("users").document(actor_uid).get()
    if not snapshot.exists:
        raise PermissionDeniedError("사용자 권한을 확인할 수 없습니다.")

    actor = snapshot.to_dict() or {}
    if not actor.get("active"):
        raise PermissionDeniedError("비활성 계정은 메모를 작성할 수 없습니다.")
    if actor.get("role") not in {"reviewer", "admin"}:
        raise PermissionDeniedError("검토자 또는 관리자만 메모를 작성할 수 있습니다.")
    return actor


def add_review_note(case_id: str, image_id: str,
                    actor_uid: str, content: str,
                    run_id: str | None = None) -> str:
    """메모 저장; 반환 note_id. 빈 메모 금지, 대상 케이스와 이미지 관계 확인."""
    if not isinstance(content, str) or not content.strip():
        raise ValidationError("검토 메모 내용을 입력해야 합니다.")
    if not isinstance(case_id, str) or not case_id.strip():
        raise NotFoundError("케이스를 찾을 수 없습니다.")
    if not isinstance(image_id, str) or not image_id.strip():
        raise NotFoundError("영상을 찾을 수 없습니다.")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
        raise NotFoundError("처리 기록을 찾을 수 없습니다.")

    try:
        db = firebase_client.get_db()
        actor = _get_active_actor(db, actor_uid)

        case_snapshot = db.collection("cases").document(case_id).get()
        if not case_snapshot.exists:
            raise NotFoundError("케이스를 찾을 수 없습니다.")
        case = case_snapshot.to_dict() or {}
        if (
            actor.get("role") == "reviewer"
            and case.get("assigned_reviewer_uid") != actor_uid
        ):
            raise PermissionDeniedError("배정된 케이스에만 메모를 작성할 수 있습니다.")

        image_snapshot = db.collection("images").document(image_id).get()
        if not image_snapshot.exists:
            raise NotFoundError("영상을 찾을 수 없습니다.")
        image = image_snapshot.to_dict() or {}
        if image.get("case_id") != case_id:
            raise ValidationError("선택한 영상이 해당 케이스에 속하지 않습니다.")

        if run_id is not None:
            run_snapshot = db.collection("processing_runs").document(run_id).get()
            if not run_snapshot.exists:
                raise NotFoundError("처리 기록을 찾을 수 없습니다.")
            run = run_snapshot.to_dict() or {}
            if (
                run.get("case_id") != case_id
                or run.get("source_image_id") != image_id
            ):
                raise ValidationError("처리 기록이 선택한 케이스·영상과 연결되지 않습니다.")

        note_id = _new_id("note_")
        db.collection("review_notes").document(note_id).set({
            "case_id": case_id,
            "image_id": image_id,
            "run_id": run_id,
            "content": content.strip(),
            "author_uid": actor_uid,
            "created_at": _server_timestamp(),
        })
        return note_id
    except AppError:
        raise
    except Exception as err:
        raise StorageError("검토 메모를 저장하지 못했습니다.") from err


def get_case_history(case_id: str) -> list[dict]:
    """업무 이벤트/메모/처리 기록을 조회 가능한 형태로 반환."""
    raise NotImplementedError

"""D 담당 업무 상태 전환 규칙 단위 테스트."""

import pytest

from src.errors import (
    NotFoundError,
    PermissionDeniedError,
    StateConflictError,
    ValidationError,
)
from src.services import workflow
from src.services.workflow import assign_case, check_transition, transition_case


@pytest.mark.parametrize(
    ("current_status", "action", "expected"),
    [
        ("registered", "assign_case", "assigned"),
        ("assigned", "start_review", "reviewing"),
        ("reviewing", "request_recheck", "needs_review"),
        ("needs_review", "resume_review", "reviewing"),
        ("reviewing", "complete_review", "completed"),
    ],
)
def test_admin_can_perform_every_allowed_transition(current_status, action, expected):
    result = check_transition(
        current_status,
        action,
        actor_role="admin",
        is_assigned_reviewer=False,
        note="영상 품질 재확인 필요",
        has_note_or_report=True,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("current_status", "action", "expected"),
    [
        ("assigned", "start_review", "reviewing"),
        ("reviewing", "request_recheck", "needs_review"),
        ("needs_review", "resume_review", "reviewing"),
        ("reviewing", "complete_review", "completed"),
    ],
)
def test_assigned_reviewer_can_perform_review_transitions(
    current_status, action, expected
):
    result = check_transition(
        current_status,
        action,
        actor_role="reviewer",
        is_assigned_reviewer=True,
        note="영상 품질 재확인 필요",
        has_note_or_report=True,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("current_status", "action"),
    [
        ("assigned", "start_review"),
        ("reviewing", "request_recheck"),
        ("needs_review", "resume_review"),
        ("reviewing", "complete_review"),
    ],
)
def test_unassigned_reviewer_is_rejected(current_status, action):
    with pytest.raises(PermissionDeniedError):
        check_transition(
            current_status,
            action,
            actor_role="reviewer",
            is_assigned_reviewer=False,
            note="재검토 필요",
            has_note_or_report=True,
        )


def test_reviewer_cannot_assign_case():
    with pytest.raises(PermissionDeniedError):
        check_transition(
            "registered",
            "assign_case",
            actor_role="reviewer",
            is_assigned_reviewer=True,
        )


@pytest.mark.parametrize("actor_role", ["registrar", "", "unknown"])
def test_role_without_review_permission_is_rejected(actor_role):
    with pytest.raises(PermissionDeniedError):
        check_transition(
            "assigned",
            "start_review",
            actor_role=actor_role,
            is_assigned_reviewer=True,
        )


@pytest.mark.parametrize("note", ["", "   ", None])
def test_request_recheck_requires_note(note):
    with pytest.raises(ValidationError):
        check_transition(
            "reviewing",
            "request_recheck",
            actor_role="reviewer",
            is_assigned_reviewer=True,
            note=note,
        )


def test_complete_review_requires_note_or_report():
    with pytest.raises(StateConflictError):
        check_transition(
            "reviewing",
            "complete_review",
            actor_role="reviewer",
            is_assigned_reviewer=True,
            has_note_or_report=False,
        )


@pytest.mark.parametrize(
    ("current_status", "action"),
    [
        ("registered", "start_review"),
        ("assigned", "complete_review"),
        ("completed", "start_review"),
        ("reviewing", "unknown_action"),
        ("unknown_status", "start_review"),
    ],
)
def test_undefined_transition_is_rejected(current_status, action):
    with pytest.raises(StateConflictError):
        check_transition(
            current_status,
            action,
            actor_role="admin",
            is_assigned_reviewer=False,
            note="사유",
            has_note_or_report=True,
        )


class ImmediateTransaction:
    """Firestore 트랜잭션 API를 단위 테스트에서 즉시 실행한다."""

    def get(self, ref):
        return ref.get()

    def update(self, ref, data):
        ref.update(data)

    def set(self, ref, data):
        ref.set(data)


class IteratorTransaction(ImmediateTransaction):
    """실제 Firestore처럼 get 결과를 반복자로 반환한다."""

    def get(self, ref):
        return iter([ref.get()])


@pytest.fixture
def workflow_db(fake_db, monkeypatch):
    monkeypatch.setattr(
        workflow,
        "_run_transaction",
        lambda db, operation: operation(ImmediateTransaction()),
    )
    fake_db.data["users"] = {
        "uid_admin": {"role": "admin", "active": True},
        "uid_reviewer": {"role": "reviewer", "active": True},
        "uid_other_reviewer": {"role": "reviewer", "active": True},
        "uid_registrar": {"role": "registrar", "active": True},
        "uid_inactive": {"role": "reviewer", "active": False},
        # active가 bool True가 아닌 값: auth.get_user_role과 같은 기준으로 모두 비활성 처리
        "uid_active_str_false": {"role": "admin", "active": "false"},
        "uid_active_one": {"role": "reviewer", "active": 1},
        "uid_active_missing": {"role": "reviewer"},
        "uid_no_role": {"active": True},
    }
    fake_db.data["cases"] = {
        "case_demo": {
            "status": "registered",
            "assigned_reviewer_uid": None,
            "registered_by": "uid_registrar",
        }
    }
    return fake_db


def test_transaction_snapshot_accepts_firestore_iterator(workflow_db):
    ref = workflow_db.collection("cases").document("case_demo")

    snapshot = workflow._transaction_snapshot(IteratorTransaction(), ref)

    assert snapshot.exists
    assert snapshot.to_dict()["status"] == "registered"


def test_assign_case_updates_case_and_creates_event(workflow_db):
    result = assign_case("case_demo", "uid_reviewer", "uid_admin")

    stored = workflow_db.data["cases"]["case_demo"]
    assert result["case_id"] == "case_demo"
    assert result["status"] == "assigned"
    assert result["assigned_reviewer_uid"] == "uid_reviewer"
    assert stored["status"] == "assigned"
    assert stored["assigned_reviewer_uid"] == "uid_reviewer"

    events = list(workflow_db.data["case_events"].values())
    assert len(events) == 1
    assert events[0]["action"] == "assign_case"
    assert events[0]["from_status"] == "registered"
    assert events[0]["to_status"] == "assigned"
    assert events[0]["actor_uid"] == "uid_admin"


@pytest.mark.parametrize("actor_uid", ["uid_registrar", "uid_reviewer"])
def test_assign_case_requires_admin(workflow_db, actor_uid):
    with pytest.raises(PermissionDeniedError):
        assign_case("case_demo", "uid_reviewer", actor_uid)


@pytest.mark.parametrize("reviewer_uid", ["uid_registrar", "uid_inactive"])
def test_assign_case_requires_active_reviewer(workflow_db, reviewer_uid):
    with pytest.raises(PermissionDeniedError):
        assign_case("case_demo", reviewer_uid, "uid_admin")


def test_assign_case_rejects_unknown_reviewer(workflow_db):
    with pytest.raises(NotFoundError):
        assign_case("case_demo", "uid_missing", "uid_admin")


def test_assign_case_rejects_missing_case(workflow_db):
    with pytest.raises(NotFoundError):
        assign_case("case_missing", "uid_reviewer", "uid_admin")


def test_assign_case_rejects_duplicate_assignment(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")

    with pytest.raises(StateConflictError):
        assign_case("case_demo", "uid_reviewer", "uid_admin")


def test_transition_case_starts_review_and_creates_event(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")

    result = transition_case("case_demo", "start_review", "uid_reviewer")

    assert result["status"] == "reviewing"
    assert workflow_db.data["cases"]["case_demo"]["status"] == "reviewing"
    events = list(workflow_db.data["case_events"].values())
    assert [event["action"] for event in events] == ["assign_case", "start_review"]


def test_transition_case_rejects_unassigned_reviewer(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")

    with pytest.raises(PermissionDeniedError):
        transition_case("case_demo", "start_review", "uid_other_reviewer")


def test_transition_case_records_recheck_note(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")
    transition_case("case_demo", "start_review", "uid_reviewer")

    result = transition_case(
        "case_demo",
        "request_recheck",
        "uid_reviewer",
        note="  밝기 확인 필요  ",
    )

    assert result["status"] == "needs_review"
    events = list(workflow_db.data["case_events"].values())
    assert events[-1]["note"] == "밝기 확인 필요"


def test_transition_case_requires_content_before_completion(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")
    transition_case("case_demo", "start_review", "uid_reviewer")

    with pytest.raises(StateConflictError):
        transition_case("case_demo", "complete_review", "uid_reviewer")


def test_transition_case_completes_when_note_exists(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")
    transition_case("case_demo", "start_review", "uid_reviewer")
    workflow_db.data["review_notes"] = {
        "note_demo": {"case_id": "case_demo", "content": "검토 완료"}
    }

    result = transition_case("case_demo", "complete_review", "uid_reviewer")

    assert result["status"] == "completed"


def test_transition_case_rejects_duplicate_action(workflow_db):
    assign_case("case_demo", "uid_reviewer", "uid_admin")
    transition_case("case_demo", "start_review", "uid_reviewer")

    with pytest.raises(StateConflictError):
        transition_case("case_demo", "start_review", "uid_reviewer")


# --- 역할 확인은 auth.get_user_role 기준 (§6.1) -------------------------------

def test_workflow_uses_auth_get_user_role(workflow_db, monkeypatch):
    calls = []

    def fake_role(uid):
        calls.append(uid)
        return {"uid_admin": "admin", "uid_reviewer": "reviewer"}[uid]

    monkeypatch.setattr(workflow.auth, "get_user_role", fake_role)
    assign_case("case_demo", "uid_reviewer", "uid_admin")
    transition_case("case_demo", "start_review", "uid_reviewer")
    assert calls == ["uid_admin", "uid_reviewer", "uid_reviewer"]  # 실행자, 배정 대상, 실행자


@pytest.mark.parametrize("actor_uid", ["uid_active_str_false", "uid_missing", "", None])
def test_assign_case_rejects_actor_not_active_true(workflow_db, actor_uid):
    with pytest.raises(PermissionDeniedError):
        assign_case("case_demo", "uid_reviewer", actor_uid)


@pytest.mark.parametrize("reviewer_uid", ["uid_active_one", "uid_active_missing", "uid_no_role"])
def test_assign_case_rejects_reviewer_not_active_true(workflow_db, reviewer_uid):
    with pytest.raises(PermissionDeniedError):
        assign_case("case_demo", reviewer_uid, "uid_admin")
    assert workflow_db.data["cases"]["case_demo"]["status"] == "registered"


@pytest.mark.parametrize("reviewer_uid", ["", None])
def test_assign_case_rejects_empty_reviewer_uid(workflow_db, reviewer_uid):
    with pytest.raises(NotFoundError):
        assign_case("case_demo", reviewer_uid, "uid_admin")


def test_transition_case_rejects_actor_not_active_true(workflow_db):
    workflow_db.data["cases"]["case_demo"].update(status="assigned", assigned_reviewer_uid="uid_active_one")
    with pytest.raises(PermissionDeniedError):
        transition_case("case_demo", "start_review", "uid_active_one")
    assert workflow_db.data["cases"]["case_demo"]["status"] == "assigned"

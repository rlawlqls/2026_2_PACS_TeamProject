"""D 담당 업무 상태 전환 규칙 단위 테스트."""

import pytest

from src.errors import PermissionDeniedError, StateConflictError, ValidationError
from src.services.workflow import check_transition


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

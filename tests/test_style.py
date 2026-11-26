"""공통 테마 헬퍼 테스트 (A 소유)."""

import pytest

from src.errors import ValidationError
from src.ui import style

# TEAM_CONTRACT §6.2의 업무 상태 전체
CONTRACT_STATUSES = ["registered", "assigned", "reviewing", "needs_review", "completed"]


@pytest.mark.parametrize("status", CONTRACT_STATUSES)
def test_status_badge_covers_every_contract_status(status):
    label, color = style.STATUS_LABELS[status]
    badge = style.status_badge(status)
    assert label in badge
    assert f"pacs-badge {color}" in badge


def test_status_badge_labels_in_korean():
    assert ">검토 중<" in style.status_badge("reviewing")
    assert ">재검토 요청<" in style.status_badge("needs_review")


@pytest.mark.parametrize("bad", ["needs_check", "", "Reviewing", "unknown"])
def test_status_badge_rejects_unknown_status(bad):
    # needs_check는 자동 점검 결과 값이라 업무 상태 배지로 쓰면 안 된다 (§6.2)
    with pytest.raises(ValidationError):
        style.status_badge(bad)

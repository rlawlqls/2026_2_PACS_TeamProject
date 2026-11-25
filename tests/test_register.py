"""영상 등록 흐름 테스트 (A 소유) — 개발 모드에서 등록 → 목록·영상 조회 → 자동 점검.

C의 check_quality·dicom_io가 아직 stub이어도 등록이 유지되는지, 완성되면 점검 결과가 저장되는지 확인한다.
"""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from src.config import DEV_USER
from src.errors import PermissionDeniedError, ValidationError
from src.services import cases
from src.ui import register

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")

PASS_RESULT = {
    "status": "pass",
    "metrics": {"brightness_mean": 128.0, "contrast_std": 55.0, "laplacian_variance": 900.0},
    "reasons": [],
    "thresholds": {"brightness_min": 50.0, "brightness_max": 205.0, "contrast_std_min": 35.0,
                   "laplacian_var_min": 80.0, "version": "demo-v1"},
    "checker_version": "1.0.0",
}


@pytest.fixture
def dev(monkeypatch):
    """개발 모드 + 테스트마다 비어 있는 메모리 저장소."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(cases, "_DEV_REGISTERED_CASES", [])
    monkeypatch.setattr(cases, "_DEV_REGISTERED_IMAGES", {})
    monkeypatch.setattr(cases, "_DEV_QUALITY", {})


def _png(gray):
    buf = io.BytesIO()
    Image.fromarray(gray, mode="L").save(buf, format="PNG")
    return buf.getvalue()


def _meta(uid=DEV_USER["uid"]):
    return {"case_label": "LIDC-IDRI-0001", "exam_type": "X-ray", "description": "CHEST", "registered_by": uid}


# --- 정상 ---------------------------------------------------------------------

def test_dev_registration_appears_in_list_and_viewer(dev, samples, monkeypatch):
    monkeypatch.setattr(register, "check_quality", lambda gray, thresholds: PASS_RESULT)
    outcome = register._register_and_check(_meta(), _png(samples["normal"]))

    newest = cases.search_cases()[0]
    assert newest["case_id"] == outcome["case_id"] and newest["case_label"] == "LIDC-IDRI-0001"
    assert newest["latest_quality_status"] == "pass"  # 자동 점검 결과가 목록에 반영
    assert np.array_equal(cases.load_image(outcome["image_id"]), samples["normal"])  # 뷰어가 받을 영상
    assert outcome["quality"] == PASS_RESULT and outcome["quality_error"] is None


def test_registration_kept_when_quality_check_not_ready(dev, samples):
    # C의 check_quality가 아직 stub(NotImplementedError)이어도 등록은 유지된다 (§4)
    outcome = register._register_and_check(_meta(), _png(samples["normal"]))
    assert outcome["quality"] is None and "준비되지 않아" in outcome["quality_error"]
    assert cases.load_case(outcome["case_id"])["latest_quality_status"] is None


def test_dicom_tags_fill_form(monkeypatch):
    tags = {"case_label": "LIDC-IDRI-0001", "exam_type": "X-ray", "description": "CHEST", "dicom": {}}
    monkeypatch.setattr(register.dicom_io, "read_tags", lambda data: tags)
    filled, notice = register._read_dicom_tags("scan.DCM", b"...")
    assert filled == {"case_label": "LIDC-IDRI-0001", "exam_type": "X-ray", "description": "CHEST"}
    assert "자동으로 채웠습니다" in notice
    assert register._read_dicom_tags("photo.png", b"...") == ({}, None)  # 일반 영상은 직접 입력


def test_register_tab_shows_form_for_admin_in_dev_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    assert any("실제 환자정보" in w.value for w in at.warning)  # 등록 안내가 보인다


# --- 오류 ---------------------------------------------------------------------

def test_dicom_reader_not_ready_shows_notice(monkeypatch):
    filled, notice = register._read_dicom_tags("scan.dcm", b"...")  # dicom_io stub
    assert filled == {} and "준비되지 않았습니다" in notice


def test_only_session_dev_user_can_register_in_dev_mode(dev, samples):
    with pytest.raises(PermissionDeniedError):
        register._register_and_check(_meta(uid="someone_else"), _png(samples["normal"]))
    assert cases._DEV_REGISTERED_CASES == []


def test_broken_file_is_rejected_in_dev_mode(dev, monkeypatch):
    monkeypatch.setattr(cases.dicom_io, "is_dicom", lambda data: False)
    with pytest.raises(ValidationError):
        register._register_and_check(_meta(), b"not an image")


def test_reviewer_sees_no_register_form(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.session_state["auth_user"] = {"uid": "uid_rev", "role": "reviewer", "display_name": "김검토", "id_token": ""}
    at.run()
    assert not at.exception
    assert any("접수 담당자 또는 관리자만" in i.value for i in at.info)
    assert not any("실제 환자정보" in w.value for w in at.warning)

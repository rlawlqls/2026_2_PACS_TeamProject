"""영상 등록 흐름 테스트 (A 소유) — 개발 모드에서 등록 → 목록·영상 조회 → 자동 점검.

C의 실제 check_quality·dicom_io와 함께 동작하는지, 그리고 점검·태그 읽기가 실패했을 때
(가짜 함수로 흉내)도 등록이 유지되는지 확인한다.
"""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from src.config import DEV_USER
from src.errors import PermissionDeniedError, StorageError, ValidationError
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


def _dicom(**tags) -> bytes:
    """태그만 있는 작은 테스트용 DICOM (태그 자동 입력 확인용, 픽셀 없음)."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    for keyword, value in {"PatientID": "LIDC-IDRI-0001", "Modality": "DX", "BodyPartExamined": "CHEST",
                           **tags}.items():
        setattr(ds, keyword, value)
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    return buf.getvalue()


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

    newest = cases.search_cases(actor_uid=DEV_USER["uid"])[0]
    assert newest["case_id"] == outcome["case_id"] and newest["case_label"] == "LIDC-IDRI-0001"
    assert newest["latest_quality_status"] == "pass"  # 자동 점검 결과가 목록에 반영
    assert np.array_equal(cases.load_image(outcome["image_id"]), samples["normal"])  # 뷰어가 받을 영상
    assert outcome["quality"] == PASS_RESULT and outcome["quality_error"] is None


def test_registration_runs_real_quality_check(dev, samples):
    # C의 실제 check_quality와 연결: 결과가 계약 형식으로 저장되고 목록에 반영된다
    outcome = register._register_and_check(_meta(), _png(samples["blur"]))
    assert outcome["quality_error"] is None
    assert outcome["quality"]["status"] == "needs_check"
    assert "possibly_blurry" in outcome["quality"]["reasons"]
    case = cases.load_case(outcome["case_id"], actor_uid=DEV_USER["uid"])
    assert case["latest_quality_status"] == "needs_check"


def test_dicom_tags_fill_form_by_content_not_file_name(samples):
    # 실제 dicom_io: 파일 이름과 상관없이 내용이 DICOM이면 태그로 채운다 (C 리뷰 #49)
    filled, notice = register._read_dicom_tags(_dicom())
    assert filled == {"case_label": "LIDC-IDRI-0001", "exam_type": "X-ray", "description": "CHEST"}
    assert "자동으로 채웠습니다" in notice
    assert register._read_dicom_tags(_png(samples["normal"])) == ({}, None)  # 일반 영상은 직접 입력


def test_reason_labels_come_from_checker():
    from src.quality import checker

    assert register.REASON_LABELS is checker.REASON_LABELS  # 한글 표시 표는 한 곳(C)에만 둔다


def test_register_tab_shows_form_for_admin_in_dev_mode(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not at.exception
    assert any("실제 환자정보" in w.value for w in at.warning)  # 등록 안내가 보인다


# --- 오류 ---------------------------------------------------------------------

def test_registration_kept_when_quality_check_fails(dev, samples, monkeypatch):
    # 자동 점검이 실패해도 등록은 유지되고, 다시 점검할 수 있다는 안내가 나온다 (§4, C 리뷰 #49)
    def broken(gray, thresholds):
        raise StorageError("점검 결과를 저장하지 못했습니다.")

    monkeypatch.setattr(register, "check_quality", broken)
    outcome = register._register_and_check(_meta(), _png(samples["normal"]))
    assert outcome["quality"] is None and "완료하지 못했습니다" in outcome["quality_error"]
    case = cases.load_case(outcome["case_id"], actor_uid=DEV_USER["uid"])
    assert case["latest_quality_status"] is None
    assert "자동 점검 탭" in register.RECHECK_HINT


def test_unreadable_dicom_tags_show_manual_input_notice(monkeypatch):
    # DICOM이지만 태그를 읽지 못하면 예외로 멈추지 않고 직접 입력 안내
    def broken(data):
        raise ValidationError("DICOM 파일을 읽을 수 없습니다.")

    monkeypatch.setattr(register.dicom_io, "read_tags", broken)
    filled, notice = register._read_dicom_tags(_dicom())
    assert filled == {} and "읽지 못했습니다" in notice and "직접 입력" in notice


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

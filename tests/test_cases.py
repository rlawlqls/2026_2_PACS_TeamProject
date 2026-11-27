"""케이스·영상 조회 테스트 (A 소유).

지금은 개발 모드(§7.1) 동작만 검사한다. Firebase 연결 후 실제 저장·조회 테스트를 추가한다.
"""

import numpy as np
import pytest

from src.config import DEV_USER, is_dev_mode
from src.errors import NotFoundError
from src.services.cases import load_case, load_image, search_cases

DEV_UID = DEV_USER["uid"]


@pytest.fixture
def dev_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")


# --- 개발 모드 켜기/끄기 ---------------------------------------------------

def test_dev_mode_on_only_for_development(dev_env):
    assert is_dev_mode() is True


@pytest.mark.parametrize("value", ["production", "", "dev", "Production "])
def test_dev_mode_off_for_other_values(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert is_dev_mode() is False


def test_dev_mode_off_when_app_env_missing(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert is_dev_mode() is False


# --- 개발 모드 정상 동작 -----------------------------------------------------

def test_dev_search_cases_returns_sample_cases(dev_env):
    cases = search_cases(actor_uid=DEV_UID)
    assert len(cases) >= 1
    assert all(case["case_id"].startswith("case_") for case in cases)
    assert all(case["image_id"].startswith("img_") for case in cases)


def test_dev_load_image_follows_image_spec(dev_env):
    case = search_cases(actor_uid=DEV_UID)[0]
    gray = load_image(case["image_id"])
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert min(gray.shape) >= 32


def test_dev_load_image_returns_copy(dev_env):
    image_id = search_cases(actor_uid=DEV_UID)[0]["image_id"]
    first = load_image(image_id)
    first[:] = 0
    assert load_image(image_id).any()


def test_dev_load_case_matches_search(dev_env):
    case = search_cases(actor_uid=DEV_UID)[0]
    assert load_case(case["case_id"], actor_uid=DEV_UID) == case


# --- 오류 입력 -----------------------------------------------------------------

def test_dev_load_case_unknown_raises_not_found(dev_env):
    with pytest.raises(NotFoundError):
        load_case("case_does_not_exist", actor_uid=DEV_UID)


def test_dev_load_image_unknown_raises_not_found(dev_env):
    with pytest.raises(NotFoundError):
        load_image("img_does_not_exist")


def test_production_does_not_return_dev_cases(env):
    # 실제 조회는 아직 미구현이므로, 개발용 가짜 데이터가 새어 나오지 않는지만 확인한다.
    with pytest.raises(NotImplementedError):
        search_cases(actor_uid="uid_admin")


# --- 조회 범위 (§6.1, 계약 v2.3 actor_uid) --------------------------------------

@pytest.mark.parametrize("actor_uid", ["", "   ", None])
def test_dev_mode_still_requires_actor_uid(dev_env, actor_uid):
    with pytest.raises(PermissionDeniedError):
        search_cases(actor_uid=actor_uid)
    with pytest.raises(PermissionDeniedError):
        load_case("case_dev_normal", actor_uid=actor_uid)


def test_actor_uid_is_keyword_only_and_required(dev_env):
    with pytest.raises(TypeError):
        search_cases()
    with pytest.raises(TypeError):
        load_case("case_dev_normal")
    with pytest.raises(TypeError):
        load_case("case_dev_normal", DEV_UID)


# =============================================================================
# 실제 모드: save_case / load_case / load_image (가짜 Firestore + 임시 폴더)
# =============================================================================

import io

from PIL import Image

from src import dicom_io
from src.errors import PermissionDeniedError, StorageError, ValidationError
from src.services import auth, cases, storage
from src.services.cases import save_case

REGISTRAR = "uid_registrar"
REVIEWER = "uid_reviewer"
ROLES = {REGISTRAR: "registrar", REVIEWER: "reviewer", "uid_admin": "admin",
         "uid_other_registrar": "registrar", "uid_other_reviewer": "reviewer"}


def _png_bytes(gray):
    buf = io.BytesIO()
    Image.fromarray(gray, mode="L").save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_rgb_bytes(gray):
    buf = io.BytesIO()
    Image.fromarray(gray, mode="L").convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _meta(uid=REGISTRAR, **extra):
    return {"case_label": "DEMO-001", "exam_type": "X-ray", "description": "모의 흉부", "registered_by": uid, **extra}


@pytest.fixture
def env(fake_db, local_storage, monkeypatch):
    """실제 모드 준비: 가짜 Firestore + 임시 저장소 + 역할 조회 대체 (auth는 Day 2 작업)."""
    def fake_role(uid):
        if uid not in ROLES:
            raise PermissionDeniedError("권한 없음")
        return ROLES[uid]

    monkeypatch.setattr(auth, "get_user_role", fake_role)
    return fake_db, local_storage


@pytest.fixture
def fake_dicom(monkeypatch, samples):
    """C의 dicom_io가 아직 stub이므로 계약(§4 docstring) 형식대로 대체한다."""
    marker = b"\0" * 128 + b"DICM"
    gray = samples["normal"]
    monkeypatch.setattr(dicom_io, "is_dicom", lambda data: data.startswith(marker))
    monkeypatch.setattr(dicom_io, "read_tags", lambda data: {
        "case_label": "LIDC-IDRI-0001", "exam_type": "X-ray", "description": "CHEST",
        "dicom": {"modality": "DX", "body_part": "CHEST", "manufacturer": "GE MEDICAL SYSTEMS",
                  "rows": gray.shape[0], "cols": gray.shape[1], "bits_stored": 14},
    })
    monkeypatch.setattr(dicom_io, "to_gray", lambda data: gray.copy())
    return marker + b"fake-dicom-body"


# --- 정상 ---------------------------------------------------------------------

def test_save_png_creates_files_and_documents(env, samples):
    db, root = env
    gray = samples["normal"]
    case_id, image_id = save_case(_meta(), _png_bytes(gray))

    assert case_id.startswith("case_") and image_id.startswith("img_")
    case = db.data["cases"][case_id]
    assert case["status"] == "registered" and case["registered_by"] == REGISTRAR
    assert case["case_label"] == "DEMO-001" and case["latest_quality_status"] is None
    image = db.data["images"][image_id]
    assert image["source_format"] == "png" and image["kind"] == "original"
    assert (image["width"], image["height"]) == (gray.shape[1], gray.shape[0])
    assert (root / f"originals/{case_id}/{image_id}.png").is_file()
    assert (root / f"display/{case_id}/{image_id}.png").is_file()


def test_load_image_returns_same_gray_after_save(env, samples):
    gray = samples["normal"]
    _, image_id = save_case(_meta(), _png_bytes(gray))
    loaded = cases.load_image(image_id)
    assert loaded.dtype == np.uint8 and loaded.ndim == 2
    assert np.array_equal(loaded, gray)


def test_load_case_includes_original_image_id(env, samples):
    case_id, image_id = save_case(_meta(uid="uid_admin"), _png_bytes(samples["normal"]))
    case = cases.load_case(case_id, actor_uid="uid_admin")
    assert case["case_id"] == case_id and case["image_id"] == image_id
    assert case["registered_by"] == "uid_admin"


def test_save_rgb_jpeg_is_stored_as_gray(env, samples):
    db, root = env
    _, image_id = save_case(_meta(), _jpeg_rgb_bytes(samples["normal"]))
    image = db.data["images"][image_id]
    assert image["mime_type"] == "image/jpeg" and image["storage_path"].endswith(".jpg")
    assert cases.load_image(image_id).ndim == 2


def test_save_dicom_keeps_original_and_tags(env, fake_dicom, samples):
    db, root = env
    case_id, image_id = save_case(_meta(), fake_dicom)
    image = db.data["images"][image_id]
    assert image["source_format"] == "dicom" and image["mime_type"] == "application/dicom"
    assert image["dicom"]["bits_stored"] == 14
    assert (root / f"originals/{case_id}/{image_id}.dcm").read_bytes() == fake_dicom  # 원본 그대로 보관
    assert np.array_equal(cases.load_image(image_id), samples["normal"])  # B·C·D는 uint8만 받는다


def test_save_case_does_not_modify_metadata(env, samples):
    meta = _meta(description="  공백  ")
    before = dict(meta)
    save_case(meta, _png_bytes(samples["normal"]))
    assert meta == before


# --- 오류 ---------------------------------------------------------------------

def test_reviewer_cannot_register(env, samples):
    db, root = env
    with pytest.raises(PermissionDeniedError):
        save_case(_meta(uid=REVIEWER), _png_bytes(samples["normal"]))
    assert not db.data and not any(root.rglob("*.png"))


@pytest.mark.parametrize("uid", [None, "", "uid_unknown"])
def test_missing_or_unknown_user_cannot_register(env, samples, uid):
    with pytest.raises(PermissionDeniedError):
        save_case(_meta(uid=uid), _png_bytes(samples["normal"]))


def test_file_over_25mb_is_rejected(env):
    with pytest.raises(ValidationError):
        save_case(_meta(), b"\x89PNG\r\n\x1a\n" + b"\0" * (25 * 1024 * 1024))


@pytest.mark.parametrize("data", [b"", b"just text, not an image", b"\x89PNG\r\n\x1a\nbroken"])
def test_unsupported_or_broken_file_is_rejected(env, monkeypatch, data):
    monkeypatch.setattr(dicom_io, "is_dicom", lambda d: False)
    with pytest.raises(ValidationError):
        save_case(_meta(), data)


def test_image_smaller_than_32px_is_rejected(env):
    with pytest.raises(ValidationError):
        save_case(_meta(), _png_bytes(np.zeros((20, 40), dtype=np.uint8)))


@pytest.mark.parametrize("bad", [{"case_label": ""}, {"case_label": "   "}, {"exam_type": "Ultrasound"}])
def test_invalid_metadata_is_rejected(env, samples, bad):
    with pytest.raises(ValidationError):
        save_case(_meta(**bad), _png_bytes(samples["normal"]))


def test_firestore_failure_removes_uploaded_files(env, samples):
    db, root = env
    db.fail_commit = True
    with pytest.raises(StorageError):
        save_case(_meta(), _png_bytes(samples["normal"]))
    assert not [p for p in root.rglob("*") if p.is_file()]  # 원본·표시용 모두 정리됨
    assert "cases" not in db.data


def test_cleanup_failure_is_recorded_as_orphan(env, samples, monkeypatch):
    db, root = env
    db.fail_commit = True

    def broken_delete(path):
        raise StorageError("삭제 실패 (테스트)")

    monkeypatch.setattr(storage, "delete_image", broken_delete)
    with pytest.raises(StorageError):
        save_case(_meta(), _png_bytes(samples["normal"]))
    log = (root / cases.ORPHAN_LOG_NAME).read_text(encoding="utf-8")
    assert "originals/case_" in log and "display/case_" in log


def test_load_case_and_image_not_found(env):
    with pytest.raises(NotFoundError):
        cases.load_case("case_does_not_exist", actor_uid="uid_admin")
    with pytest.raises(NotFoundError):
        cases.load_image("img_does_not_exist")


# --- load_case 조회 범위 (§6.1) ------------------------------------------------

def _saved_case(db, samples, assigned_reviewer=None):
    case_id, _ = save_case(_meta(), _png_bytes(samples["normal"]))  # REGISTRAR가 등록
    db.data["cases"][case_id]["assigned_reviewer_uid"] = assigned_reviewer
    return case_id


@pytest.mark.parametrize("actor_uid", [REGISTRAR, REVIEWER, "uid_admin"],
                         ids=["own_registrar", "assigned_reviewer", "admin"])
def test_load_case_allows_actor_in_scope(env, samples, actor_uid):
    db, _ = env
    case_id = _saved_case(db, samples, assigned_reviewer=REVIEWER)
    assert cases.load_case(case_id, actor_uid=actor_uid)["case_id"] == case_id


@pytest.mark.parametrize("actor_uid, assigned", [
    ("uid_other_registrar", REVIEWER),   # 다른 접수 담당자가 등록한 케이스
    ("uid_other_reviewer", REVIEWER),    # 다른 검토자에게 배정된 케이스
    (REVIEWER, None),                    # 아직 배정 전
], ids=["other_registrar", "other_reviewer", "reviewer_before_assign"])
def test_load_case_rejects_actor_out_of_scope(env, samples, actor_uid, assigned):
    db, _ = env
    case_id = _saved_case(db, samples, assigned_reviewer=assigned)
    with pytest.raises(PermissionDeniedError):
        cases.load_case(case_id, actor_uid=actor_uid)


@pytest.mark.parametrize("actor_uid", ["", None, "uid_unknown"], ids=["empty", "none", "unknown"])
def test_load_case_rejects_not_logged_in_or_unknown_user(env, samples, actor_uid):
    db, _ = env
    case_id = _saved_case(db, samples)
    with pytest.raises(PermissionDeniedError):
        cases.load_case(case_id, actor_uid=actor_uid)


def test_unknown_user_cannot_learn_whether_case_exists(env):
    # 권한 확인이 먼저라서, 없는 케이스여도 NotFoundError 대신 PermissionDeniedError가 난다.
    with pytest.raises(PermissionDeniedError):
        cases.load_case("case_does_not_exist", actor_uid="uid_unknown")


@pytest.mark.parametrize("actor_uid", ["", "uid_unknown"], ids=["empty", "unknown"])
def test_search_cases_rejects_not_logged_in_or_unknown_user(env, actor_uid):
    with pytest.raises(PermissionDeniedError):
        search_cases(actor_uid=actor_uid)


# =============================================================================
# save_quality_check (C의 check_quality 결과 저장, §4)
# =============================================================================

def _qc_result(**override):
    result = {
        "status": "needs_check",
        "metrics": {"brightness_mean": np.float64(42.8), "contrast_std": 29.4, "laplacian_variance": 50.2},
        "reasons": ["too_dark", "low_contrast", "possibly_blurry"],
        "thresholds": {"brightness_min": 50.0, "brightness_max": 205.0, "contrast_std_min": 35.0,
                       "laplacian_var_min": 80.0, "version": "demo-v1"},
        "checker_version": "1.0.0",
    }
    result.update(override)
    return result


PASS_RESULT = {"status": "pass", "reasons": []}


# --- 정상 ---------------------------------------------------------------------

def test_save_quality_check_stores_and_updates_case(env, samples):
    db, _ = env
    case_id, image_id = save_case(_meta(), _png_bytes(samples["normal"]))
    check_id = cases.save_quality_check(image_id, _qc_result())

    assert check_id.startswith("qc_")
    saved = db.data["quality_checks"][check_id]
    assert saved["case_id"] == case_id and saved["image_id"] == image_id
    assert saved["reasons"] == ["too_dark", "low_contrast", "possibly_blurry"]
    assert type(saved["metrics"]["brightness_mean"]) is float  # numpy 숫자 → float
    assert saved["actor_uid"] is None  # 등록 직후 자동 점검
    case = cases.load_case(case_id, actor_uid=REGISTRAR)
    assert case["latest_check_id"] == check_id and case["latest_quality_status"] == "needs_check"
    assert case["status"] == "registered"  # 업무 상태는 건드리지 않는다 (§5)


def test_latest_check_is_replaced_by_new_check(env, samples):
    case_id, image_id = save_case(_meta(), _png_bytes(samples["normal"]))
    cases.save_quality_check(image_id, _qc_result())
    second = cases.save_quality_check(image_id, _qc_result(**PASS_RESULT), actor_uid=REVIEWER)
    case = cases.load_case(case_id, actor_uid=REGISTRAR)
    assert case["latest_check_id"] == second and case["latest_quality_status"] == "pass"


def test_dev_mode_quality_check_shows_in_case_list(dev_env, monkeypatch):
    monkeypatch.setattr(cases, "_DEV_QUALITY", {})  # 다른 테스트와 메모리를 공유하지 않게
    image_id = search_cases(actor_uid=DEV_UID)[0]["image_id"]
    check_id = cases.save_quality_check(image_id, _qc_result(**PASS_RESULT))
    case = search_cases(actor_uid=DEV_UID)[0]
    assert case["latest_check_id"] == check_id and case["latest_quality_status"] == "pass"


# --- 오류 ---------------------------------------------------------------------

@pytest.mark.parametrize("override", [
    {"status": "ok"},                                             # 모르는 status
    {"status": "pass"},                                           # pass인데 사유 있음
    {"reasons": []},                                              # needs_check인데 사유 없음
    {"reasons": ["low_contrast", "too_dark"]},                    # 순서가 표준과 다름
    {"reasons": ["too_dark", "noisy"]},                           # 모르는 사유
    {"metrics": {"brightness_mean": 1.0, "contrast_std": 2.0}},   # 지표 누락
    {"metrics": {"brightness_mean": "밝음", "contrast_std": 2.0, "laplacian_variance": 3.0}},
    {"metrics": {"brightness_mean": float("nan"), "contrast_std": 2.0, "laplacian_variance": 3.0}},
    {"thresholds": {"brightness_min": 50.0}},                     # version 없음
    {"checker_version": ""},
])
def test_invalid_quality_result_is_rejected(env, samples, override):
    db, _ = env
    _, image_id = save_case(_meta(), _png_bytes(samples["normal"]))
    with pytest.raises(ValidationError):
        cases.save_quality_check(image_id, _qc_result(**override))
    assert "quality_checks" not in db.data


def test_quality_check_for_unknown_image_raises_not_found(env):
    with pytest.raises(NotFoundError):
        cases.save_quality_check("img_does_not_exist", _qc_result())


def test_quality_save_failure_keeps_registered_case(env, samples):
    db, root = env
    case_id, image_id = save_case(_meta(), _png_bytes(samples["normal"]))
    db.fail_commit = True
    with pytest.raises(StorageError):
        cases.save_quality_check(image_id, _qc_result())
    db.fail_commit = False
    assert cases.load_case(case_id, actor_uid=REGISTRAR)["latest_check_id"] is None  # 케이스는 그대로
    assert (root / f"originals/{case_id}/{image_id}.png").is_file()  # 원본도 그대로

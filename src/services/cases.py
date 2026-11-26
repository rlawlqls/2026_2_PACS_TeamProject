"""케이스·영상 저장/조회 (A 소유, TEAM_CONTRACT §4 A 계약).

저장 구조 (§3.2·§5, TEAM_CONTRACT v2.2):
- 원본: originals/{case_id}/{image_id}.dcm|.png|.jpg — 업로드 파일 그대로, 덮어쓰지 않음
- 표시용: display/{case_id}/{image_id}.png — (H,W) uint8 grayscale. load_image()와 자동 점검이 쓴다
- Firestore: cases/{case_id}, images/{image_id}

B·C·D는 load_image()가 돌려주는 (H,W) uint8만 쓰므로 원본이 DICOM인지 알 필요가 없다.

개발 모드(APP_ENV=development, §7.1)에서는 Firebase 대신 make_samples()로 만든
가짜 케이스·샘플 영상을 돌려준다. 탭 코드는 개발/실제 모드 구분 없이 같은 함수를 부르면 된다.
"""

import io
import logging
import uuid
from datetime import datetime, timezone

import numpy as np
from PIL import Image, UnidentifiedImageError

from src import dicom_io, models
from src.config import DEV_USER, is_dev_mode
from src.errors import AppError, NotFoundError, PermissionDeniedError, StorageError, ValidationError
from src.services import auth, firebase_client, storage

logger = logging.getLogger(__name__)

MIN_SIDE = 32  # §3.1 최소 크기
REGISTER_ROLES = ("registrar", "admin")  # §6.1 케이스/원본 등록
EXAM_TYPES = ("X-ray", "CT", "MRI", "Other")  # §3.3
ORPHAN_LOG_NAME = "orphan_files.log"  # §4 고아 파일 정리 정책 (STORAGE_DIR 아래, .gitignore 대상)

# 파일 형식별 (원본 확장자, MIME, source_format)
_FORMATS = {
    "DICOM": (".dcm", "application/dicom", "dicom"),
    "PNG": (".png", "image/png", "png"),
    "JPEG": (".jpg", "image/jpeg", "png"),  # 스키마의 source_format은 dicom/png 두 값 → 일반 영상은 png로 묶는다
}

# ---------------------------------------------------------------------------
# 개발 모드 전용 데이터 (Firebase 없이 화면 확인용)
# ---------------------------------------------------------------------------
_DEV_PREFIX_CASE = "case_dev_"
_DEV_PREFIX_IMAGE = "img_dev_"


def _dev_samples() -> dict[str, np.ndarray]:
    # 실제 모드에서는 sample_data를 import하지 않도록 함수 안에서 가져온다.
    from sample_data.generate_samples import make_samples

    return make_samples(seed=0)


def _dev_cases() -> list[dict]:
    """샘플 영상 1장당 케이스 1개. C가 샘플을 추가하면 개발용 케이스도 자동으로 늘어난다."""
    cases = []
    for number, name in enumerate(_dev_samples(), start=1):
        cases.append({
            "case_id": f"{_DEV_PREFIX_CASE}{name}",
            "image_id": f"{_DEV_PREFIX_IMAGE}{name}",
            "schema_version": 1,
            "case_label": f"DEV-{number:03d}",
            "exam_type": "X-ray",
            "description": f"개발 모드 샘플 영상 ({name})",
            "status": "registered",
            "assigned_reviewer_uid": None,
            "registered_by": DEV_USER["uid"],
            "latest_check_id": None,
            "latest_quality_status": None,
        })
    return cases


def _dev_load_case(case_id: str) -> dict:
    for case in _dev_cases():
        if case["case_id"] == case_id:
            return case
    raise NotFoundError("케이스를 찾을 수 없습니다.")


def _dev_load_image(image_id: str) -> np.ndarray:
    name = image_id.removeprefix(_DEV_PREFIX_IMAGE)
    samples = _dev_samples()
    if not image_id.startswith(_DEV_PREFIX_IMAGE) or name not in samples:
        raise NotFoundError("영상을 찾을 수 없습니다.")
    return samples[name].copy()


def _dev_search_cases(query: str, status: str | None) -> list[dict]:
    query = query.strip().lower()
    return [
        case for case in _dev_cases()
        if (not query or query in case["case_label"].lower() or query in case["description"].lower())
        and (status is None or case["status"] == status)
    ]


# ---------------------------------------------------------------------------
# 내부 도우미
# ---------------------------------------------------------------------------

def _new_id(prefix: str) -> str:
    """§3.2 UUID 생성 표준."""
    return f"{prefix}{uuid.uuid4().hex}"


def _server_timestamp():
    # google.cloud.firestore import는 느리고 경고가 나므로 실제로 쓸 때만 가져온다.
    from google.cloud.firestore import SERVER_TIMESTAMP

    return SERVER_TIMESTAMP


def _check_can_register(metadata: dict) -> str:
    """등록자 uid를 확인하고 역할이 registrar/admin인지 검사한다 (§4·§6.1). 반환: uid."""
    uid = metadata.get("registered_by") if isinstance(metadata, dict) else None
    if not isinstance(uid, str) or not uid.strip():
        raise PermissionDeniedError("로그인이 필요합니다.")
    if auth.get_user_role(uid) not in REGISTER_ROLES:
        raise PermissionDeniedError("영상 등록 권한이 없습니다. 접수 담당자 또는 관리자만 등록할 수 있습니다.")
    return uid


def _clean_metadata(metadata: dict) -> dict:
    """§3.3 metadata를 검증하고 정리한 사본을 반환한다 (입력 dict는 수정하지 않음)."""
    label = str(metadata.get("case_label") or "").strip()
    if not label:
        raise ValidationError("케이스 표시명(case_label)을 입력해 주세요.")
    exam_type = metadata.get("exam_type") or "Other"
    if exam_type not in EXAM_TYPES:
        raise ValidationError("검사 종류는 X-ray / CT / MRI / Other 중 하나여야 합니다.")
    description = str(metadata.get("description") or "").strip()
    return {"case_label": label, "exam_type": exam_type, "description": description}


def _to_uint8_gray(img: Image.Image) -> np.ndarray:
    """PIL 영상을 (H,W) uint8 grayscale로 바꾼다. RGB는 여기서 한 번만 변환한다 (§3.1)."""
    if img.mode in ("I;16", "I;16B", "I;16L", "I", "F"):
        # 16비트 등 고비트 grayscale PNG: 단순 convert("L")은 255에서 잘리므로 최대값 기준으로 줄인다.
        arr = np.asarray(img, dtype=np.float64)
        peak = arr.max()
        arr = arr / peak * 255.0 if peak > 0 else arr
        return np.clip(arr, 0, 255).astype(np.uint8)
    return np.asarray(img.convert("L"), dtype=np.uint8).copy()


def _decode_upload(image_bytes: bytes) -> tuple[str, np.ndarray, dict | None]:
    """업로드 bytes의 실제 내용으로 형식을 판별하고 표시용 영상을 만든다.

    반환: (형식 이름, gray, dicom 태그 dict 또는 None). 지원하지 않거나 깨진 파일이면 ValidationError.
    확장자는 save_case 인자에 없으므로 등록 화면(st.file_uploader type=...)에서 거르고,
    여기서는 파일 내용(매직 바이트·디코딩 결과)으로 다시 검사한다 (§3.1).
    """
    # PNG/JPEG 매직 바이트를 먼저 본다 → 일반 영상 등록은 dicom_io(C)에 의존하지 않는다.
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") or image_bytes.startswith(b"\xff\xd8\xff"):
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                fmt = img.format
                if fmt not in ("PNG", "JPEG"):
                    raise ValidationError("DICOM(.dcm)·PNG·JPEG 파일만 등록할 수 있습니다.")
                img.load()
                gray = _to_uint8_gray(img)
        except ValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as err:
            raise ValidationError("영상 파일을 읽을 수 없습니다. 손상되었거나 지원하지 않는 형식입니다.") from err
        return fmt, gray, None

    if dicom_io.is_dicom(image_bytes):
        tags = dicom_io.read_tags(image_bytes)
        gray = dicom_io.to_gray(image_bytes)
        return "DICOM", gray, tags

    raise ValidationError("DICOM(.dcm)·PNG·JPEG 파일만 등록할 수 있습니다.")


def _encode_png(gray: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(gray, mode="L").save(buf, format="PNG")
    return buf.getvalue()


def _record_orphan(path: str) -> None:
    """삭제하지 못한 고아 파일 경로를 로컬 로그에 남긴다 (§4). 경로와 시각만 적는다."""
    line = f"{datetime.now(timezone.utc).isoformat()}\t{path}\n"
    try:
        log_path = storage.storage_root() / ORPHAN_LOG_NAME
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    logger.error("고아 파일 정리 필요: %s", path)


def _cleanup_uploaded(paths: list[str]) -> None:
    """업로드한 파일을 지운다. 지우지 못한 파일은 고아 로그에 기록한다."""
    for path in paths:
        try:
            storage.delete_image(path)
        except Exception:
            _record_orphan(path)


def _find_original_image(db, case_id: str) -> dict | None:
    """케이스의 원본 영상 문서 하나를 찾는다 (images.case_id로 조회, §5)."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    query = db.collection("images").where(filter=FieldFilter("case_id", "==", case_id))
    for snap in query.stream():
        data = snap.to_dict() or {}
        if data.get("kind") == "original":
            return {"image_id": snap.id, **data}
    return None


# ---------------------------------------------------------------------------
# 계약 함수 (§4)
# ---------------------------------------------------------------------------


def save_case(metadata: dict, image_bytes: bytes) -> tuple[str, str]:
    """원본을 영상 저장소(storage.py)에 보존하고 Firestore 케이스·영상 생성.
    반환: (case_id, image_id); 실패 시 AppError 계열 예외.
    권한: registrar 또는 admin.
    Storage 업로드 성공 후 Firestore 기록 실패 시:
      - Storage 파일 삭제 시도 후 StorageError 발생
      - 삭제 실패 시 고아 파일 경로를 로그에 기록하고 StorageError 발생
    """
    uid = _check_can_register(metadata)
    meta = _clean_metadata(metadata)

    if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
        raise ValidationError("업로드된 파일이 비어 있습니다.")
    if len(image_bytes) > models.MAX_UPLOAD_BYTES:
        raise ValidationError("파일이 25MB를 넘습니다. 25MB 이하 파일만 등록할 수 있습니다.")

    fmt, gray, tags = _decode_upload(bytes(image_bytes))
    if gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상을 (H,W) uint8 grayscale로 변환하지 못했습니다.")
    height, width = gray.shape
    if height < MIN_SIDE or width < MIN_SIDE:
        raise ValidationError(f"영상이 너무 작습니다. 최소 {MIN_SIDE}×{MIN_SIDE} 픽셀이어야 합니다.")

    ext, mime, source_format = _FORMATS[fmt]
    case_id = _new_id("case_")
    image_id = _new_id("img_")
    original = models.original_path(case_id, image_id, ext)
    display = models.display_path(case_id, image_id)

    # 1) 영상 파일 저장: 원본 → 표시용. 원본 업로드가 실패하면 지울 것이 없다.
    uploaded: list[str] = []
    storage.upload_image(original, bytes(image_bytes), content_type=mime)
    uploaded.append(original)
    try:
        storage.upload_image(display, _encode_png(gray), content_type="image/png")
        uploaded.append(display)
    except Exception as err:
        _cleanup_uploaded(uploaded)
        raise StorageError("표시용 영상을 저장하지 못했습니다. 다시 시도해 주세요.") from err

    # 2) Firestore 기록: 케이스·영상 문서를 한 번에 커밋한다.
    now = _server_timestamp()
    case_doc: models.CaseDoc = {
        "schema_version": models.SCHEMA_VERSION,
        **meta,
        "status": "registered",
        "assigned_reviewer_uid": None,
        "registered_by": uid,
        "created_at": now,
        "updated_at": now,
        "latest_check_id": None,
        "latest_quality_status": None,
    }
    image_doc: models.ImageDoc = {
        "case_id": case_id,
        "kind": "original",
        "parent_image_id": None,
        "storage_path": original,
        "display_path": display,
        "source_format": source_format,
        "mime_type": mime,
        "width": int(width),
        "height": int(height),
        "byte_size": len(image_bytes),
        "uploaded_by": uid,
        "created_at": now,
    }
    if tags is not None:
        image_doc["dicom"] = dict(tags.get("dicom") or {})

    try:
        db = firebase_client.get_db()
        batch = db.batch()
        batch.set(db.collection("cases").document(case_id), case_doc)
        batch.set(db.collection("images").document(image_id), image_doc)
        batch.commit()
    except Exception as err:
        _cleanup_uploaded(uploaded)
        raise StorageError("케이스 기록을 저장하지 못했습니다. 업로드한 파일은 정리했습니다. 다시 시도해 주세요.") from err

    return case_id, image_id


def load_case(case_id: str) -> dict:
    """케이스 메타데이터/상태/최근 점검 요약 포함 dict; 없으면 NotFoundError."""
    if is_dev_mode():
        return _dev_load_case(case_id)

    if not isinstance(case_id, str) or not case_id:
        raise NotFoundError("케이스를 찾을 수 없습니다.")
    try:
        db = firebase_client.get_db()
        snap = db.collection("cases").document(case_id).get()
        if not snap.exists:
            raise NotFoundError("케이스를 찾을 수 없습니다.")
        case = {"case_id": case_id, **(snap.to_dict() or {})}
        original = _find_original_image(db, case_id)
    except AppError:
        raise
    except Exception as err:
        raise StorageError("케이스 정보를 불러오지 못했습니다.") from err

    # 화면이 바로 영상을 열 수 있도록 원본 영상 id를 같이 돌려준다 (개발 모드 형식과 동일).
    case["image_id"] = original["image_id"] if original else None
    return case


def load_image(image_id: str) -> np.ndarray:
    """Storage 파일을 디코딩하여 (H,W) uint8 grayscale로 반환."""
    if is_dev_mode():
        return _dev_load_image(image_id)

    if not isinstance(image_id, str) or not image_id:
        raise NotFoundError("영상을 찾을 수 없습니다.")
    try:
        snap = firebase_client.get_db().collection("images").document(image_id).get()
    except AppError:
        raise
    except Exception as err:
        raise StorageError("영상 정보를 불러오지 못했습니다.") from err
    if not snap.exists:
        raise NotFoundError("영상을 찾을 수 없습니다.")

    doc = snap.to_dict() or {}
    # 표시용 PNG가 기준이다 (§5). 처리 결과처럼 표시용이 따로 없으면 저장 경로의 PNG를 읽는다.
    path = doc.get("display_path") or doc.get("storage_path")
    if not path:
        raise NotFoundError("영상 파일 경로가 없습니다.")
    data = storage.download_image(path)
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            return _to_uint8_gray(img)
    except (UnidentifiedImageError, OSError, ValueError) as err:
        raise StorageError("저장된 영상을 읽을 수 없습니다.") from err


def search_cases(query: str = "", status: str | None = None) -> list[dict]:
    """권한 범위 내 케이스 목록, 등록일 내림차순.
    registrar: 본인 등록 케이스만
    reviewer: 본인 배정 케이스만
    admin: 전체
    """
    if is_dev_mode():
        return _dev_search_cases(query, status)
    raise NotImplementedError


def save_processing_run(image_id: str, algorithm: str, params: dict,
                        processed_gray: np.ndarray, actor_uid: str,
                        roi: dict | None = None) -> str:
    """결과 파일 Storage 저장 + processing_runs Firestore 기록; 반환: run_id."""
    raise NotImplementedError


def get_processing_runs(image_id: str) -> list[dict]:
    """run 이력을 최신순 반환."""
    raise NotImplementedError


def save_quality_check(image_id: str, result: dict, actor_uid: str | None = None) -> str:
    """C의 result를 검증하고 Firestore quality_checks에 저장.
    cases/{case_id}.latest_check_id, latest_quality_status도 동시 업데이트.
    반환: check_id.
    """
    raise NotImplementedError

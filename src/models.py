"""Firestore 데이터 모델 (A 작성, 전원 리뷰 — TEAM_CONTRACT §5).

실제 읽기/쓰기는 `services/`가 하고, 이 파일은 **필드 이름과 자료형을 한곳에 모아 둔다.**
런타임 검증은 하지 않는다 (TypedDict는 타입 힌트일 뿐이다). 오타를 줄이려면 문자열을
직접 쓰지 말고 여기 상수를 import해서 쓴다.

스키마를 바꾸려면 계약 변경 절차(§15)를 따른다.
"""

from typing import Literal, TypedDict

# ── 공통 상수 ────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 1

#: 업로드 허용 용량 (TEAM_CONTRACT §0·§3.1). DICOM 한 검사가 약 16MB라 여유를 둔다.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: 업로드 허용 확장자 (§0)
ALLOWED_EXTENSIONS = (".dcm", ".png", ".jpg", ".jpeg")

Role = Literal["registrar", "reviewer", "admin"]
CaseStatus = Literal["registered", "assigned", "reviewing", "needs_review", "completed"]
QualityStatus = Literal["pass", "needs_check", "error"]
ExamType = Literal["X-ray", "CT", "MRI", "Other"]
ImageKind = Literal["original", "processed"]
SourceFormat = Literal["dicom", "png"]


# ── Storage 경로 (§3.2·§10.4) ────────────────────────────────────────────────
# 원본은 절대 덮어쓰지 않는다. 표시용은 원본에서 다시 만들 수 있는 파생물이다.

def original_path(case_id: str, image_id: str, ext: str) -> str:
    """원본 파일 경로. ext는 ``.dcm`` 또는 ``.png`` 등 업로드된 실제 확장자."""
    return f"originals/{case_id}/{image_id}{ext}"


def display_path(case_id: str, image_id: str) -> str:
    """표시용 경로. 목록 화면과 자동 품질 점검이 이 파일을 쓴다."""
    return f"display/{case_id}/{image_id}.png"


def processed_path(case_id: str, run_id: str) -> str:
    """영상처리 결과 경로."""
    return f"processed/{case_id}/{run_id}.png"


# ── 문서 모델 ────────────────────────────────────────────────────────────────

class UserDoc(TypedDict):
    """``users/{uid}``"""
    display_name: str
    role: Role
    active: bool
    created_at: object  # Firestore SERVER_TIMESTAMP (UTC)


class CaseDoc(TypedDict, total=False):
    """``cases/{case_id}``

    `status`(업무 진행)와 `latest_quality_status`(자동 점검 결과)는 **서로 다른 값**이다.
    혼용하지 않는다 (§5).
    """
    schema_version: int
    case_label: str
    exam_type: ExamType
    description: str
    status: CaseStatus
    assigned_reviewer_uid: str | None
    registered_by: str
    created_at: object
    updated_at: object
    latest_check_id: str | None
    latest_quality_status: QualityStatus | None


class DicomInfo(TypedDict, total=False):
    """`ImageDoc.dicom` — `dicom_io.read_tags()`가 채운다 (§3.3).

    비식별 공개 데이터는 값이 비어 있을 수 있다. 화면에서 빈 값을 처리한다.
    """
    modality: str          # DX / CR / CT / MR ...
    body_part: str         # BodyPartExamined
    manufacturer: str
    rows: int
    cols: int
    bits_stored: int       # LIDC 흉부 X-ray는 14


class ImageDoc(TypedDict, total=False):
    """``images/{image_id}``"""
    case_id: str
    kind: ImageKind
    parent_image_id: str | None
    storage_path: str              # 원본 경로 (original_path)
    display_path: str | None       # 표시용 경로 (display_path). 원본이 PNG면 같을 수 있다
    source_format: SourceFormat
    dicom: DicomInfo               # source_format == "dicom"일 때만
    mime_type: str                 # application/dicom | image/png | image/jpeg
    width: int
    height: int
    byte_size: int
    uploaded_by: str
    created_at: object


class ProcessingRunDoc(TypedDict, total=False):
    """``processing_runs/{run_id}``"""
    case_id: str
    source_image_id: str
    result_image_id: str
    algorithm: str
    algorithm_version: str
    params: dict
    roi: dict | None
    actor_uid: str
    created_at: object


class QualityCheckDoc(TypedDict, total=False):
    """``quality_checks/{check_id}`` — C가 계산하고 A가 저장한다 (§4).

    점검은 **표시용 이미지 한 장**을 기준으로 한 번만 수행한다. 뷰어에서 사용자가
    밝기를 조절해도 판정이 바뀌면 안 되기 때문이다 (§7).
    """
    case_id: str
    image_id: str
    status: QualityStatus
    metrics: dict
    reasons: list[str]
    thresholds: dict
    checker_version: str
    actor_uid: str | None
    created_at: object


class ReviewNoteDoc(TypedDict, total=False):
    """``review_notes/{note_id}``"""
    case_id: str
    image_id: str
    run_id: str | None
    content: str
    author_uid: str
    created_at: object


class CaseEventDoc(TypedDict, total=False):
    """``case_events/{event_id}``"""
    case_id: str
    action: str
    from_status: CaseStatus
    to_status: CaseStatus
    actor_uid: str
    note: str
    created_at: object


class ReportDoc(TypedDict, total=False):
    """``reports/{report_id}``"""
    case_id: str
    summary: str
    author_uid: str
    created_at: object
    linked_run_ids: list[str]
    linked_check_ids: list[str]

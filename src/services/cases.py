"""케이스·영상 저장/조회 (A 소유, TEAM_CONTRACT §4 A 계약).

개발 모드(APP_ENV=development, §7.1)에서는 Firebase 대신 make_samples()로 만든
가짜 케이스·샘플 영상을 돌려준다. 탭 코드는 개발/실제 모드 구분 없이 같은 함수를 부르면 된다.
"""

import numpy as np

from src.config import DEV_USER, is_dev_mode
from src.errors import NotFoundError

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
    raise NotImplementedError


def load_case(case_id: str) -> dict:
    """케이스 메타데이터/상태/최근 점검 요약 포함 dict; 없으면 NotFoundError."""
    if is_dev_mode():
        return _dev_load_case(case_id)
    raise NotImplementedError


def load_image(image_id: str) -> np.ndarray:
    """Storage 파일을 디코딩하여 (H,W) uint8 grayscale로 반환."""
    if is_dev_mode():
        return _dev_load_image(image_id)
    raise NotImplementedError


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

"""케이스·영상 저장/조회 (A 소유, TEAM_CONTRACT §4 A 계약)."""

import numpy as np


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
    raise NotImplementedError


def load_image(image_id: str) -> np.ndarray:
    """Storage 파일을 디코딩하여 (H,W) uint8 grayscale로 반환."""
    raise NotImplementedError


def search_cases(query: str = "", status: str | None = None) -> list[dict]:
    """권한 범위 내 케이스 목록, 등록일 내림차순.
    registrar: 본인 등록 케이스만
    reviewer: 본인 배정 케이스만
    admin: 전체
    """
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

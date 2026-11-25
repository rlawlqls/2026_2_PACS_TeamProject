"""DICOM 읽기·변환 (C 소유, TEAM_CONTRACT §4 C 계약).

이 파일만 DICOM 형식을 안다. 다른 모듈은 여기서 나온 `(H, W) uint8` 배열만 쓰므로,
업로드된 파일이 DICOM인지 PNG인지 알 필요가 없다.

A가 Day 0 선행 작업으로 만든 stub이며, 구현은 C가 채운다.
"""

import numpy as np

# Modality(0008,0060) → metadata["exam_type"] 매핑 (TEAM_CONTRACT §3.3)
MODALITY_MAP = {
    "DX": "X-ray",
    "CR": "X-ray",
    "CT": "CT",
    "MR": "MRI",
}

# 표시용 변환에 쓰는 백분위 구간 (TEAM_CONTRACT §3.1)
DISPLAY_PERCENTILES = (1.0, 99.0)


def is_dicom(data: bytes) -> bool:
    """data가 DICOM 파일이면 True. 어떤 입력에도 예외를 내지 않는다.

    판별 기준: 128바이트 preamble 뒤에 `DICM` 매직 바이트가 있는지.
    등록 화면이 `.dcm`과 PNG/JPEG를 구분할 때 쓴다.
    """
    raise NotImplementedError


def read_tags(data: bytes) -> dict:
    """DICOM 태그를 읽어 등록 화면용 metadata dict로 반환한다 (§3.3).

    반환 형식::

        {
            "case_label": "LIDC-IDRI-0001",      # PatientID, 없으면 "UNKNOWN"
            "exam_type": "X-ray",                # MODALITY_MAP 변환, 모르면 "Other"
            "description": "CHEST",              # SeriesDescription 또는 BodyPartExamined
            "dicom": {
                "modality": "DX",
                "body_part": "CHEST",
                "manufacturer": "GE MEDICAL SYSTEMS",
                "rows": 2022,
                "cols": 2022,
                "bits_stored": 14,
            },
        }

    **빈 값과 없는 태그를 모두 처리해야 한다.** 비식별 공개 데이터는 환자 이름·성별·
    나이가 빈 문자열이고, 촬영 방향(ViewPosition)·검사 설명 태그는 아예 없다.
    값이 없으면 문자열은 `""`, 숫자는 `0`으로 채우고 예외를 내지 않는다.

    DICOM이 아니거나 읽을 수 없으면 ValidationError.
    """
    raise NotImplementedError


def to_gray(data: bytes) -> np.ndarray:
    """DICOM 픽셀을 표시용 `(H, W) uint8` grayscale로 변환한다 (§3.1).

    변환 순서:

    1. `RescaleSlope` / `RescaleIntercept`를 적용한다.
    2. 픽셀값의 1~99 백분위 구간을 0~255로 펼친다 (`DISPLAY_PERCENTILES`).
       **DICOM의 WindowCenter / WindowWidth는 쓰지 않는다** — 공개 데이터에 잘못된
       값이 들어 있어, 그대로 적용하면 화면이 흰색으로 포화된다
       (LIDC-IDRI-0001에서 `WindowCenter=-600`, `WindowWidth=1600` 확인).
    3. `PhotometricInterpretation`이 `MONOCHROME1`이면 흑백을 반전한다.

    결과는 입력 해상도를 유지한다 (ROI 좌표 역변환을 단순하게 두기 위함, §3.1).
    픽셀 데이터가 없거나 2차원이 아니면 ValidationError.
    """
    raise NotImplementedError

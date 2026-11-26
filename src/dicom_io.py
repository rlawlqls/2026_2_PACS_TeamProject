"""DICOM 읽기·변환 (C 소유, TEAM_CONTRACT §4 C 계약, #22).

이 파일만 DICOM 형식을 안다. 다른 모듈은 여기서 나온 `(H, W) uint8` 배열만 쓰므로,
업로드된 파일이 DICOM인지 PNG인지 알 필요가 없다.

오류 규칙: 이 파일의 함수는 **`ValidationError`만** 낸다. A의 `save_case`가
`dicom_io` 오류를 따로 감싸지 않으므로, pydicom 내부 예외가 화면까지 올라가지 않게
여기서 모두 바꿔 준다 (`is_dicom`은 예외를 아예 내지 않는다).
"""

import io

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from src.errors import ValidationError

# Modality(0008,0060) → metadata["exam_type"] 매핑 (TEAM_CONTRACT §3.3)
MODALITY_MAP = {
    "DX": "X-ray",
    "CR": "X-ray",
    "CT": "CT",
    "MR": "MRI",
}

# 표시용 변환에 쓰는 백분위 구간 (TEAM_CONTRACT §3.1)
DISPLAY_PERCENTILES = (1.0, 99.0)

# PatientID가 없을 때 case_label 기본값 (case_label은 필수 값이므로 빈 문자열을 쓰지 않는다)
UNKNOWN_LABEL = "UNKNOWN"

_PREAMBLE_SIZE = 128
_MAGIC = b"DICM"


# ---------------------------------------------------------------------------
# 판별
# ---------------------------------------------------------------------------
def is_dicom(data: bytes) -> bool:
    """data가 DICOM 파일이면 True. 어떤 입력에도 예외를 내지 않는다.

    판별 기준: 128바이트 preamble 뒤에 `DICM` 매직 바이트가 있는지.
    등록 화면이 `.dcm`과 PNG/JPEG를 구분할 때 쓴다.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        return False
    if len(data) < _PREAMBLE_SIZE + len(_MAGIC):
        return False
    return bytes(data[_PREAMBLE_SIZE:_PREAMBLE_SIZE + len(_MAGIC)]) == _MAGIC


def _read_dataset(data: bytes, *, with_pixels: bool) -> Dataset:
    """DICOM bytes를 pydicom Dataset으로 읽는다. 실패하면 ValidationError."""
    if not is_dicom(data):
        raise ValidationError("DICOM 파일이 아닙니다.")
    try:
        return pydicom.dcmread(io.BytesIO(bytes(data)), stop_before_pixels=not with_pixels)
    except Exception as err:  # pydicom은 깨진 파일에 여러 종류의 예외를 낸다
        raise ValidationError("DICOM 파일을 읽을 수 없습니다. 파일이 손상되었을 수 있습니다.") from err


# ---------------------------------------------------------------------------
# 태그 읽기
# ---------------------------------------------------------------------------
def _text(ds: Dataset, keyword: str) -> str:
    """태그 값을 문자열로. 태그가 없거나 비었거나 값이 깨졌으면 ""."""
    try:
        value = ds.get(keyword)
    except Exception:
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _int(ds: Dataset, keyword: str) -> int:
    """태그 값을 정수로. 태그가 없거나 숫자로 바꿀 수 없으면 0."""
    try:
        value = ds.get(keyword)
        return int(value) if value not in (None, "") else 0
    except Exception:
        return 0


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

    **빈 값과 없는 태그를 모두 처리한다.** 비식별 공개 데이터는 환자 이름·성별·
    나이가 빈 문자열이고, 촬영 방향(ViewPosition)·검사 설명 태그는 아예 없다.
    값이 없으면 문자열은 `""`, 숫자는 `0`으로 채우고 예외를 내지 않는다.
    헤더가 잘린 파일도 읽힌 만큼만 채운다 (계약 §4: 읽기 실패로 예외를 내지 않는다).
    이런 파일은 이어서 부르는 `to_gray`가 ValidationError로 막는다.
    픽셀은 읽지 않으므로 큰 파일도 빠르다.

    DICOM이 아니면(또는 pydicom이 아예 열지 못하면) ValidationError.
    """
    ds = _read_dataset(data, with_pixels=False)

    modality = _text(ds, "Modality").upper()
    body_part = _text(ds, "BodyPartExamined")
    return {
        "case_label": _text(ds, "PatientID") or UNKNOWN_LABEL,
        "exam_type": MODALITY_MAP.get(modality, "Other"),
        "description": _text(ds, "SeriesDescription") or body_part,
        "dicom": {
            "modality": modality,
            "body_part": body_part,
            "manufacturer": _text(ds, "Manufacturer"),
            "rows": _int(ds, "Rows"),
            "cols": _int(ds, "Columns"),
            "bits_stored": _int(ds, "BitsStored"),
        },
    }


# ---------------------------------------------------------------------------
# 표시용 변환
# ---------------------------------------------------------------------------
def _decode_pixels(ds: Dataset) -> np.ndarray:
    """픽셀 배열을 꺼낸다. 픽셀이 없거나 디코딩할 수 없으면 ValidationError."""
    if "PixelData" not in ds:
        raise ValidationError("영상(픽셀)이 없는 DICOM입니다. 구조화 보고서 같은 파일은 등록할 수 없습니다.")
    try:
        return ds.pixel_array
    except Exception as err:
        file_meta = getattr(ds, "file_meta", None)
        syntax = file_meta.get("TransferSyntaxUID") if file_meta is not None else None
        if syntax is not None and syntax.is_compressed:
            raise ValidationError(
                f"압축된 DICOM({syntax.name})은 지원하지 않습니다. 비압축 DICOM으로 등록해 주세요."
            ) from err
        raise ValidationError("DICOM 영상의 픽셀을 읽을 수 없습니다.") from err


def _rescale(ds: Dataset, pixels: np.ndarray) -> np.ndarray:
    """저장값 × RescaleSlope + RescaleIntercept (태그가 없으면 1, 0). CT라면 HU가 된다."""
    try:
        slope = float(ds.get("RescaleSlope", 1) or 1)
        intercept = float(ds.get("RescaleIntercept", 0) or 0)
    except (TypeError, ValueError):
        slope, intercept = 1.0, 0.0
    return pixels.astype(np.float64) * slope + intercept


def _stretch_to_uint8(values: np.ndarray) -> np.ndarray:
    """1~99 백분위 구간을 0~255로 펼친다. 구간 밖 값은 0 또는 255로 자른다.

    극단값(검출기 바깥, 금속, 글자 마커) 1%씩을 무시해서, 대부분의 조직이 화면의
    명암 폭을 넉넉하게 쓰게 한다. 백분위 폭이 0이면 최솟값~최댓값을 쓰고,
    그것도 0이면(완전히 같은 값) 검은 영상을 돌려준다.
    """
    low, high = np.percentile(values, DISPLAY_PERCENTILES)
    if high <= low:
        low, high = float(values.min()), float(values.max())
    if high <= low:
        return np.zeros(values.shape, dtype=np.uint8)
    scaled = (values - low) / (high - low) * 255.0
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8)


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
    ds = _read_dataset(data, with_pixels=True)
    pixels = _decode_pixels(ds)

    if pixels.ndim != 2:
        if _int(ds, "SamplesPerPixel") > 1:
            raise ValidationError("컬러 DICOM은 지원하지 않습니다. 흑백(grayscale) 영상만 등록할 수 있습니다.")
        raise ValidationError("여러 장(프레임)이 든 DICOM은 지원하지 않습니다. 2차원 영상 1장만 등록할 수 있습니다.")

    gray = _stretch_to_uint8(_rescale(ds, pixels))

    if _text(ds, "PhotometricInterpretation").upper() == "MONOCHROME1":
        gray = 255 - gray          # MONOCHROME1은 값이 클수록 어둡게 표시하는 형식
    return gray

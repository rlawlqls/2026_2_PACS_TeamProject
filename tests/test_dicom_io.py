"""dicom_io 테스트 (C 소유, #22).

DICOM 파일은 커밋하지 않으므로 pydicom으로 가짜 DICOM을 코드에서 만들어 시험한다.
`dicom_data/`에 LIDC-IDRI가 있으면 실제 파일로도 확인한다 (없으면 건너뜀).
"""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.uid import (
    ExplicitVRLittleEndian,
    JPEGBaseline8Bit,
    SecondaryCaptureImageStorage,
    generate_uid,
)

from src import dicom_io
from src.errors import ValidationError

LIDC_FILES = sorted(Path("dicom_data").glob("LIDC-IDRI-*/**/*.dcm"))


def make_dicom(pixels: np.ndarray | None = None, *, transfer_syntax=ExplicitVRLittleEndian,
               photometric: str = "MONOCHROME2", bits_stored: int = 14, **tags) -> bytes:
    """테스트용 DICOM bytes를 만든다. tags로 태그를 넣거나(값) 빼거나(None) 할 수 있다."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = transfer_syntax

    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID = meta.MediaStorageSOPClassUID
    ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    defaults = {"PatientID": "LIDC-IDRI-0001", "PatientName": "", "Modality": "DX",
                "BodyPartExamined": "CHEST", "Manufacturer": "GE MEDICAL SYSTEMS"}
    for keyword, value in {**defaults, **tags}.items():
        if value is not None:
            setattr(ds, keyword, value)

    if pixels is not None:
        ds.Rows, ds.Columns = pixels.shape[-2], pixels.shape[-1]
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = photometric
        ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, bits_stored, bits_stored - 1
        ds.PixelRepresentation = 0
        if pixels.ndim == 3:
            ds.NumberOfFrames = pixels.shape[0]
        ds.PixelData = pixels.astype(np.uint16).tobytes()

    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def gradient_14bit(height: int = 64, width: int = 48) -> np.ndarray:
    """0~16383 (14비트) 범위의 가로 그라데이션."""
    return np.tile(np.linspace(0, 16383, width), (height, 1)).astype(np.uint16)


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.zeros((8, 8), dtype=np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# is_dicom
# ---------------------------------------------------------------------------
def test_is_dicom_true_for_dicom_bytes():
    data = make_dicom(gradient_14bit())
    assert dicom_io.is_dicom(data) is True
    assert dicom_io.is_dicom(bytearray(data)) is True


@pytest.mark.parametrize("data", [png_bytes(), b"", b"DICM", b"\0" * 131, None, "DICM", 123,
                                  b"\0" * 128 + b"DICX"])
def test_is_dicom_false_without_exception(data):
    assert dicom_io.is_dicom(data) is False


# ---------------------------------------------------------------------------
# read_tags
# ---------------------------------------------------------------------------
def test_read_tags_maps_lidc_style_tags():
    tags = dicom_io.read_tags(make_dicom(gradient_14bit(64, 48)))
    assert tags == {
        "case_label": "LIDC-IDRI-0001",
        "exam_type": "X-ray",
        "description": "CHEST",
        "dicom": {"modality": "DX", "body_part": "CHEST", "manufacturer": "GE MEDICAL SYSTEMS",
                  "rows": 64, "cols": 48, "bits_stored": 14},
    }


def test_read_tags_matches_keys_used_by_save_case_tests():
    """A의 #14 테스트(fake_dicom)가 쓰는 반환 형식과 키가 같아야 한다."""
    tags = dicom_io.read_tags(make_dicom(gradient_14bit()))
    assert set(tags) == {"case_label", "exam_type", "description", "dicom"}
    assert set(tags["dicom"]) == {"modality", "body_part", "manufacturer", "rows", "cols", "bits_stored"}


@pytest.mark.parametrize(("modality", "exam_type"), [
    ("DX", "X-ray"), ("CR", "X-ray"), ("CT", "CT"), ("MR", "MRI"), ("US", "Other"),
])
def test_read_tags_modality_mapping(modality, exam_type):
    assert dicom_io.read_tags(make_dicom(Modality=modality))["exam_type"] == exam_type


def test_read_tags_prefers_series_description():
    tags = dicom_io.read_tags(make_dicom(SeriesDescription="Chest PA"))
    assert tags["description"] == "Chest PA"


def test_read_tags_fills_defaults_for_missing_and_empty_tags():
    """비식별 공개 데이터처럼 태그가 비었거나 아예 없어도 예외 없이 기본값을 채운다."""
    data = make_dicom(PatientID="", Modality=None, BodyPartExamined=None, Manufacturer=None)
    tags = dicom_io.read_tags(data)     # 픽셀도 없는 DICOM
    assert tags["case_label"] == "UNKNOWN"
    assert tags["exam_type"] == "Other"
    assert tags["description"] == ""
    assert tags["dicom"] == {"modality": "", "body_part": "", "manufacturer": "",
                             "rows": 0, "cols": 0, "bits_stored": 0}


def test_read_tags_rejects_non_dicom():
    with pytest.raises(ValidationError):
        dicom_io.read_tags(png_bytes())


def test_truncated_dicom_read_tags_gives_defaults_but_to_gray_rejects():
    """계약 §4: read_tags는 읽기 실패로 예외를 내지 않는다 → 기본값.
    잘린 파일은 이어서 부르는 to_gray가 ValidationError로 막으므로 save_case 등록은 거절된다."""
    truncated = make_dicom(gradient_14bit())[:140]      # 'DICM' 직후에서 잘린 파일
    tags = dicom_io.read_tags(truncated)
    assert tags["case_label"] == "UNKNOWN" and tags["dicom"]["rows"] == 0
    with pytest.raises(ValidationError):
        dicom_io.to_gray(truncated)


# ---------------------------------------------------------------------------
# to_gray
# ---------------------------------------------------------------------------
def test_to_gray_converts_14bit_to_uint8_keeping_size():
    gray = dicom_io.to_gray(make_dicom(gradient_14bit(64, 48)))
    assert gray.shape == (64, 48) and gray.dtype == np.uint8
    assert gray.min() == 0 and gray.max() == 255


def test_to_gray_ignores_window_tags():
    """WindowCenter=-600 / Width=1600을 따르면 0~16383 픽셀이 전부 흰색이 된다 (LIDC에서 실제 확인)."""
    data = make_dicom(gradient_14bit(), WindowCenter=-600, WindowWidth=1600)
    gray = dicom_io.to_gray(data)
    assert 100 < gray.mean() < 155          # 그라데이션 그대로 → 평균은 중간 밝기
    assert (gray == 255).mean() < 0.05      # 흰색 포화 없음


def test_to_gray_percentile_ignores_extreme_pixels():
    pixels = np.full((50, 50), 1000, dtype=np.uint16)
    pixels[:, 25:] = 2000
    pixels[0, 0] = 16383                    # 마커처럼 아주 밝은 점 하나
    gray = dicom_io.to_gray(make_dicom(pixels))
    assert gray[10, 10] == 0 and gray[10, 40] == 255   # 점 하나 때문에 대비가 줄지 않음


def test_to_gray_rescale_with_positive_slope_keeps_display():
    """양의 기울기 Rescale은 백분위 펼치기 결과를 바꾸지 않는다 (상대적인 밝기 순서가 같으므로)."""
    plain = dicom_io.to_gray(make_dicom(gradient_14bit()))
    rescaled = dicom_io.to_gray(make_dicom(gradient_14bit(), RescaleSlope=2, RescaleIntercept=-1024))
    assert np.array_equal(plain, rescaled)


def test_to_gray_inverts_monochrome1():
    mono2 = dicom_io.to_gray(make_dicom(gradient_14bit(), photometric="MONOCHROME2"))
    mono1 = dicom_io.to_gray(make_dicom(gradient_14bit(), photometric="MONOCHROME1"))
    assert np.array_equal(mono1, 255 - mono2)


def test_to_gray_constant_image_returns_black():
    gray = dicom_io.to_gray(make_dicom(np.full((16, 16), 500, dtype=np.uint16)))
    assert gray.shape == (16, 16) and gray.dtype == np.uint8 and not gray.any()


@pytest.mark.parametrize("data", [
    png_bytes(),                                                     # DICOM 아님
    make_dicom(None),                                                # 픽셀 없음 (구조화 보고서 같은 파일)
    make_dicom(np.zeros((2, 8, 8), dtype=np.uint16)),                # 여러 프레임 (3차원)
    make_dicom(gradient_14bit())[:-100],                             # 픽셀 데이터가 잘림
])
def test_to_gray_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        dicom_io.to_gray(data)


def test_to_gray_compressed_dicom_explains_reason():
    meta_only = make_dicom(None, transfer_syntax=JPEGBaseline8Bit)
    # 압축 형식으로 선언했지만 디코딩할 수 없는 픽셀을 넣는다
    from pydicom import dcmread
    ds = dcmread(io.BytesIO(meta_only))
    ds.Rows, ds.Columns, ds.SamplesPerPixel = 8, 8, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
    ds.PixelData = encapsulate([b"not-a-jpeg"])
    ds["PixelData"].VR = "OB"                   # 압축 픽셀은 OB로 저장
    buffer = io.BytesIO()
    ds.save_as(buffer, enforce_file_format=True)

    with pytest.raises(ValidationError, match="압축"):
        dicom_io.to_gray(buffer.getvalue())


# ---------------------------------------------------------------------------
# 실제 LIDC-IDRI 파일 (python sample_data/download_lidc.py로 받았을 때만)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not LIDC_FILES, reason="dicom_data/에 LIDC-IDRI가 없음 (download_lidc.py로 받기)")
@pytest.mark.parametrize("path", LIDC_FILES[:5],   # 파일이 없으면 빈 목록 → 테스트 건너뜀
                         ids=[next(part for part in p.parts if part.startswith("LIDC-IDRI-"))
                              for p in LIDC_FILES[:5]])
def test_real_lidc_file(path):
    data = path.read_bytes()
    assert dicom_io.is_dicom(data)

    tags = dicom_io.read_tags(data)
    assert tags["case_label"].startswith("LIDC-IDRI-")
    assert tags["exam_type"] == "X-ray"

    gray = dicom_io.to_gray(data)
    assert gray.shape == (tags["dicom"]["rows"], tags["dicom"]["cols"])
    assert gray.dtype == np.uint8
    assert 30 < gray.mean() < 225           # 흰색·검은색으로 포화되지 않음

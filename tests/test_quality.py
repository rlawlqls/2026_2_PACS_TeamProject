"""품질 점검 관련 테스트 (C 소유).

지금은 합성 샘플(`make_samples`)과 변형 함수만 확인한다 (#20).
check_quality 구현 후 같은 파일에 판정 테스트를 추가한다.
"""

import cv2
import numpy as np
import pytest

from sample_data import generate_samples as gs
from sample_data.generate_samples import make_samples
from src.errors import ValidationError
from src.quality.checker import check_quality
from src.quality.thresholds import DEFAULT_THRESHOLDS

SAMPLE_NAMES = {"normal", "dark", "bright", "low_contrast", "blur", "gaussian_noise", "salt_pepper"}

#: 품질 점검 샘플마다 기대하는 점검 사유 (TEAM_CONTRACT §4 reasons 순서)
EXPECTED_REASONS = {
    "normal": [],
    "dark": ["too_dark"],
    "bright": ["too_bright"],
    "low_contrast": ["low_contrast"],
    "blur": ["possibly_blurry"],
}


def contract_reasons(gray: np.ndarray, thresholds: dict) -> list[str]:
    """샘플이 실제 점검 함수(check_quality)에서 받는 사유.

    예전에는 계약 식을 테스트 안에서 따로 계산했는데, 계약이 바뀌면(v2.4 512px 축소)
    실제 구현과 어긋나므로 check_quality 결과를 그대로 쓴다.
    """
    return check_quality(gray, thresholds)["reasons"]


# ---------------------------------------------------------------------------
# make_samples — 정상 입력
# ---------------------------------------------------------------------------
def test_make_samples_returns_seven_images_in_image_spec(samples):
    assert set(samples) == SAMPLE_NAMES
    for name, image in samples.items():
        assert image.ndim == 2, name
        assert image.dtype == np.uint8, name
        assert image.shape == samples["normal"].shape, name


def test_make_samples_same_seed_gives_same_images():
    first, second = make_samples(seed=3), make_samples(seed=3)
    for name in SAMPLE_NAMES:
        assert np.array_equal(first[name], second[name]), name


def test_make_samples_different_seed_gives_different_images():
    assert not np.array_equal(make_samples(seed=0)["normal"], make_samples(seed=1)["normal"])


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("name", sorted(EXPECTED_REASONS))
def test_quality_sample_triggers_only_intended_reason(seed, name):
    image = make_samples(seed=seed)[name]
    assert contract_reasons(image, DEFAULT_THRESHOLDS) == EXPECTED_REASONS[name]


def test_noise_samples_are_noisier_than_normal(samples):
    normal = samples["normal"].astype(np.int16)
    assert np.abs(samples["gaussian_noise"].astype(np.int16) - normal).mean() > 10
    changed = samples["salt_pepper"] != samples["normal"]
    assert 0.02 < changed.mean() < 0.06          # 약 4%가 바뀜
    assert set(np.unique(samples["salt_pepper"][changed])) <= {0, 255}


def test_save_samples_writes_png_per_sample(tmp_path):
    paths = gs.save_samples(tmp_path, seed=0)
    assert {path.stem for path in paths} == SAMPLE_NAMES
    reloaded = cv2.imread(str(tmp_path / "normal.png"), cv2.IMREAD_GRAYSCALE)
    assert np.array_equal(reloaded, make_samples(seed=0)["normal"])


# ---------------------------------------------------------------------------
# 변형 함수 — LIDC 같은 다른 크기 영상에도 적용 가능, 원본 불변
# ---------------------------------------------------------------------------
DEGRADERS = [
    lambda g: gs.adjust_exposure(g, *gs.DARK_EXPOSURE),
    lambda g: gs.adjust_exposure(g, *gs.BRIGHT_EXPOSURE),
    lambda g: gs.reduce_contrast(g),
    lambda g: gs.blur(g),
    lambda g: gs.add_gaussian_noise(g, 20.0, np.random.default_rng(0)),
    lambda g: gs.add_salt_pepper(g, 0.04, np.random.default_rng(0)),
]


@pytest.mark.parametrize("degrade", DEGRADERS)
def test_degraders_keep_spec_and_do_not_modify_input(degrade):
    gray = np.random.default_rng(7).integers(0, 256, (300, 200), dtype=np.uint8)
    before = gray.copy()
    out = degrade(gray)
    assert out.shape == gray.shape and out.dtype == np.uint8
    assert np.array_equal(gray, before)
    assert out is not gray


# ---------------------------------------------------------------------------
# 오류 입력
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [-1, 1.5, "0", True, None])
def test_make_samples_rejects_invalid_seed(seed):
    with pytest.raises(ValidationError):
        make_samples(seed=seed)


@pytest.mark.parametrize("bad", [
    np.zeros((8, 8, 3), dtype=np.uint8),     # 컬러(3채널)
    np.zeros((8, 8), dtype=np.float64),      # uint8 아님
    [[0, 1], [2, 3]],                        # 배열 아님
])
@pytest.mark.parametrize("degrade", DEGRADERS)
def test_degraders_reject_non_gray_input(degrade, bad):
    with pytest.raises(ValidationError):
        degrade(bad)


@pytest.mark.parametrize("call", [
    lambda g: gs.adjust_exposure(g, 0, 10),
    lambda g: gs.reduce_contrast(g, 0),
    lambda g: gs.reduce_contrast(g, 1.5),
    lambda g: gs.blur(g, 0),
    lambda g: gs.add_gaussian_noise(g, -1, np.random.default_rng(0)),
    lambda g: gs.add_salt_pepper(g, 1.5, np.random.default_rng(0)),
])
def test_degraders_reject_invalid_parameters(call):
    with pytest.raises(ValidationError):
        call(np.zeros((8, 8), dtype=np.uint8))

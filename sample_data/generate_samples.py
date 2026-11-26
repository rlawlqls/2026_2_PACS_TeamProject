"""테스트·시연용 합성 샘플 영상 생성 (C 소유, TEAM_CONTRACT §3.4·§8.1).

테스트는 PNG 파일을 읽지 않고 `make_samples()`를 호출해서 영상을 얻는다.
화면 확인용 PNG가 필요하면 아래처럼 실행한다 (생성된 PNG는 커밋하지 않는다)::

    python sample_data/generate_samples.py

구성
- `make_phantom()`: 모의 흉부 X-ray (공기·몸통·폐·종격동·심장·갈비뼈 + 약한 잡음)
- 변형 함수: `adjust_exposure`, `reduce_contrast`, `blur`, `add_gaussian_noise`, `add_salt_pepper`
  모두 `(H, W) uint8`을 받아 새 배열을 돌려주므로 LIDC 실제 영상(`dicom_io.to_gray` 결과)에도
  같은 조건을 적용할 수 있다 (비교 실험용, TEAM_CONTRACT §8.5).

품질 점검 샘플(dark·bright·low_contrast·blur)은 demo-v1 기준값에서 **의도한 점검 사유 1개만**
나오도록 변형 강도를 정했다. §8.1의 원래 생성식은 어둡게·흐리게 만들 때 대비(std)까지 떨어져
`low_contrast`가 겹치므로, §3.4의 C 재량 범위에서 방식을 바꿨다 (#20).
"""

import sys
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    # `python sample_data/generate_samples.py`로 직접 실행하면 저장소 루트가 import 경로에 없으므로 넣어 준다.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.errors import ValidationError  # noqa: E402

#: 샘플 세트 버전. 생성 방식이나 강도를 바꾸면 올린다.
SAMPLES_VERSION = "1.0.0"

#: 합성 영상 크기 (정사각형). 개발 모드가 화면을 열 때마다 생성하므로 작게 유지한다.
SIZE = 256

# 품질 점검 샘플의 변형 강도 (demo-v1 기준값에서 사유가 1개만 나오도록 seed 0~29로 확인)
DARK_EXPOSURE = (1.4, -145.0)    # 저노출: 어두운 부분이 검게 뭉개짐 → 평균 밝기 약 39
BRIGHT_EXPOSURE = (1.8, 100.0)   # 과노출: 밝은 부분이 하얗게 날아감 → 평균 밝기 약 221
LOW_CONTRAST_FACTOR = 0.45       # 평균 중심으로 명암 폭을 45%로 줄임 → 표준편차 약 27
BLUR_SIGMA = 2.5                 # 초점 흐림 → Laplacian 분산 약 4

# Gaussian·Median 전후 비교용 잡음 강도
GAUSSIAN_NOISE_SIGMA = 20.0
SALT_PEPPER_AMOUNT = 0.04        # 전체 픽셀의 4%를 흰 점·검은 점으로


# ---------------------------------------------------------------------------
# 입력 검사
# ---------------------------------------------------------------------------
def _check_gray(gray: np.ndarray) -> None:
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
        raise ValidationError("영상은 (H, W) 모양의 uint8 grayscale 배열이어야 합니다.")


def _to_uint8(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 모의 흉부 X-ray
# ---------------------------------------------------------------------------
def make_phantom(rng: np.random.Generator, size: int = SIZE) -> np.ndarray:
    """모의 흉부 X-ray를 만든다. 밝기·대비·선명도 모두 보통인 '정상' 영상이다.

    실제 해부 구조가 아니라, X-ray처럼 보이는 밝기 분포와 경계를 가진 도형 조합이다.
    뼈·종격동은 밝게, 공기가 찬 폐는 어둡게 (1회차 특강: X선 감쇠가 클수록 희다).
    """
    y, x = np.mgrid[0:size, 0:size].astype(np.float64) / size   # 0~1 좌표
    image = np.full((size, size), 25.0)                           # 몸 바깥 공기

    body = ((x - 0.5) / 0.46) ** 2 + ((y - 0.55) / 0.52) ** 2 <= 1
    image[body] = 150.0                                           # 몸통 연부조직
    for center_x in (0.32, 0.68):                                 # 좌우 폐
        lung = ((x - center_x) / 0.15) ** 2 + ((y - 0.50) / 0.33) ** 2 <= 1
        image[lung] = 70.0
    spine = (np.abs(x - 0.5) < 0.07) & body
    image[spine] = 185.0                                          # 종격동·척추
    heart = ((x - 0.58) / 0.13) ** 2 + ((y - 0.66) / 0.14) ** 2 <= 1
    image[heart] = 175.0                                          # 심장 (환자 왼쪽 = 화면 오른쪽)
    for k in range(7):                                            # 갈비뼈: 아래로 휜 띠
        rib_y = 0.25 + 0.075 * k + 0.64 * (x - 0.5) ** 2
        rib = (np.abs(y - rib_y) < 0.012) & body & ~spine
        image[rib] += 35.0

    image = cv2.GaussianBlur(image, (0, 0), 1.2)                  # 경계를 부드럽게
    image += rng.normal(0.0, 7.0, image.shape)                    # 검출기 잡음
    return _to_uint8(image)


# ---------------------------------------------------------------------------
# 변형 함수 (합성 영상·LIDC 실제 영상 공용)
# ---------------------------------------------------------------------------
def adjust_exposure(gray: np.ndarray, gain: float, offset: float) -> np.ndarray:
    """`gray * gain + offset`을 0~255로 자른다. 노출 부족·과다를 흉내 낸다."""
    _check_gray(gray)
    if gain <= 0:
        raise ValidationError("gain은 0보다 커야 합니다.")
    return _to_uint8(gray.astype(np.float64) * gain + offset)


def reduce_contrast(gray: np.ndarray, factor: float = LOW_CONTRAST_FACTOR) -> np.ndarray:
    """평균 밝기는 그대로 두고 명암 폭을 factor배로 줄인다 (0 < factor ≤ 1)."""
    _check_gray(gray)
    if not 0 < factor <= 1:
        raise ValidationError("factor는 0보다 크고 1 이하여야 합니다.")
    mean = gray.mean()
    return _to_uint8(mean + (gray.astype(np.float64) - mean) * factor)


def blur(gray: np.ndarray, sigma: float = BLUR_SIGMA) -> np.ndarray:
    """Gaussian 흐림으로 초점이 맞지 않은 영상을 흉내 낸다 (sigma > 0, 픽셀 단위)."""
    _check_gray(gray)
    if sigma <= 0:
        raise ValidationError("sigma는 0보다 커야 합니다.")
    return cv2.GaussianBlur(gray, (0, 0), sigma)


def add_gaussian_noise(gray: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """평균 0, 표준편차 sigma인 Gaussian 잡음을 더한다 (sigma ≥ 0)."""
    _check_gray(gray)
    if sigma < 0:
        raise ValidationError("sigma는 0 이상이어야 합니다.")
    return _to_uint8(gray.astype(np.float64) + rng.normal(0.0, sigma, gray.shape))


def add_salt_pepper(gray: np.ndarray, amount: float, rng: np.random.Generator) -> np.ndarray:
    """전체 픽셀 중 amount 비율을 절반은 흰 점(255), 절반은 검은 점(0)으로 바꾼다 (0 ≤ amount ≤ 1)."""
    _check_gray(gray)
    if not 0 <= amount <= 1:
        raise ValidationError("amount는 0 이상 1 이하여야 합니다.")
    out = gray.copy()
    hit = rng.random(gray.shape)
    out[hit < amount / 2] = 0
    out[(hit >= amount / 2) & (hit < amount)] = 255
    return out


# ---------------------------------------------------------------------------
# 계약 진입점 (TEAM_CONTRACT §3.4)
# ---------------------------------------------------------------------------
def make_samples(seed: int = 0) -> dict[str, np.ndarray]:
    """샘플 영상 이름 → (H, W) uint8 grayscale 배열. seed가 같으면 같은 영상이 나온다.

    | 이름 | 기대 판정 (demo-v1) |
    |---|---|
    | normal | 경고 없음 (pass) |
    | dark / bright | too_dark / too_bright |
    | low_contrast | low_contrast |
    | blur | possibly_blurry |
    | gaussian_noise / salt_pepper | Gaussian·Median 처리 전후 비교용 |
    """
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValidationError("seed는 0 이상의 정수여야 합니다.")

    rng = np.random.default_rng(seed)
    normal = make_phantom(rng)
    return {
        "normal": normal,
        "dark": adjust_exposure(normal, *DARK_EXPOSURE),
        "bright": adjust_exposure(normal, *BRIGHT_EXPOSURE),
        "low_contrast": reduce_contrast(normal),
        "blur": blur(normal),
        "gaussian_noise": add_gaussian_noise(normal, GAUSSIAN_NOISE_SIGMA, rng),
        "salt_pepper": add_salt_pepper(normal, SALT_PEPPER_AMOUNT, rng),
    }


def save_samples(out_dir: Path, seed: int = 0) -> list[Path]:
    """make_samples() 결과를 out_dir/<이름>.png로 저장하고 저장한 경로 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, image in make_samples(seed).items():
        path = out_dir / f"{name}.png"
        if not cv2.imwrite(str(path), image):
            raise OSError(f"PNG 저장 실패: {path}")
        paths.append(path)
    return paths


if __name__ == "__main__":
    for saved in save_samples(Path(__file__).resolve().parent):
        print(f"저장: {saved}")
    print(f"샘플 버전 {SAMPLES_VERSION} — PNG는 커밋하지 않는다 (.gitignore)")

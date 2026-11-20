"""테스트·시연용 샘플 영상 생성 (C 소유, TEAM_CONTRACT §3.4·§8.1).

A가 Day 0 선행 작업으로 만든 최소 stub이다. 지금은 normal 영상 1장만 반환한다.
테스트는 PNG 파일을 읽지 않고 make_samples()를 호출해서 영상을 얻는다.
"""

import numpy as np


def make_samples(seed: int = 0) -> dict[str, np.ndarray]:
    """샘플 영상 이름 → (H, W) uint8 grayscale 배열. seed가 같으면 같은 영상이 나온다."""
    rng = np.random.default_rng(seed)
    height, width = 256, 256

    # normal: 왼쪽→오른쪽으로 밝아지는 그라데이션 + 약한 잡음 (밝기·대비·선명도 모두 보통)
    gradient = np.tile(np.linspace(30, 225, width), (height, 1))
    noise = rng.normal(0, 10, (height, width))
    normal = np.clip(gradient + noise, 0, 255).astype(np.uint8)

    # TODO(C): dark, bright, low_contrast, blur, gaussian_noise, salt_pepper 추가 (§2·§8.1)
    return {"normal": normal}


# TODO(C): `python sample_data/generate_samples.py` 실행 시 sample_data/*.png로 저장하는 기능 (§7.1)

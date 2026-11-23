"""공통 pytest 설정 (A 소유, TEAM_CONTRACT §3.4).

이 파일이 저장소 루트에 있으면 pytest가 루트를 import 경로에 넣어 주므로,
테스트에서 `from src... import ...`, `from sample_data... import ...`를 쓸 수 있다.
"""

import pytest

from sample_data.generate_samples import make_samples


@pytest.fixture(scope="session")
def samples() -> dict:
    """코드로 만든 샘플 영상 dict (PNG 파일을 읽지 않음). 예: samples["normal"]."""
    return make_samples(seed=0)

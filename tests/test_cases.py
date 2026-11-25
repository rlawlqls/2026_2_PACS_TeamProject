"""케이스·영상 조회 테스트 (A 소유).

지금은 개발 모드(§7.1) 동작만 검사한다. Firebase 연결 후 실제 저장·조회 테스트를 추가한다.
"""

import numpy as np
import pytest

from src.config import is_dev_mode
from src.errors import NotFoundError
from src.services.cases import load_case, load_image, search_cases


@pytest.fixture
def dev_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")


@pytest.fixture
def prod_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")


# --- 개발 모드 켜기/끄기 ---------------------------------------------------

def test_dev_mode_on_only_for_development(dev_env):
    assert is_dev_mode() is True


@pytest.mark.parametrize("value", ["production", "", "dev", "Production "])
def test_dev_mode_off_for_other_values(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert is_dev_mode() is False


def test_dev_mode_off_when_app_env_missing(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert is_dev_mode() is False


# --- 개발 모드 정상 동작 -----------------------------------------------------

def test_dev_search_cases_returns_sample_cases(dev_env):
    cases = search_cases()
    assert len(cases) >= 1
    assert all(case["case_id"].startswith("case_") for case in cases)
    assert all(case["image_id"].startswith("img_") for case in cases)


def test_dev_load_image_follows_image_spec(dev_env):
    case = search_cases()[0]
    gray = load_image(case["image_id"])
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert min(gray.shape) >= 32


def test_dev_load_image_returns_copy(dev_env):
    image_id = search_cases()[0]["image_id"]
    first = load_image(image_id)
    first[:] = 0
    assert load_image(image_id).any()


def test_dev_load_case_matches_search(dev_env):
    case = search_cases()[0]
    assert load_case(case["case_id"]) == case


# --- 오류 입력 -----------------------------------------------------------------

def test_dev_load_case_unknown_raises_not_found(dev_env):
    with pytest.raises(NotFoundError):
        load_case("case_does_not_exist")


def test_dev_load_image_unknown_raises_not_found(dev_env):
    with pytest.raises(NotFoundError):
        load_image("img_does_not_exist")


def test_production_does_not_return_dev_cases(prod_env):
    # 실제 조회는 아직 미구현이므로, 개발용 가짜 데이터가 새어 나오지 않는지만 확인한다.
    with pytest.raises(NotImplementedError):
        search_cases()

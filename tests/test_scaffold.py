"""프로젝트 뼈대 확인 테스트 (A 소유).

핵심 모듈이 import되는지, 공통 예외·임계값·샘플 fixture가 계약 형식인지만 확인한다.
"""

import importlib

import numpy as np
import pytest

CORE_MODULES = [
    "src.errors",
    "src.config",
    "src.models",
    "src.dicom_io",
    "src.quality.thresholds",
    "src.quality.checker",
    "src.services.firebase_client",
    "src.services.auth",
    "src.services.storage",
    "src.services.cases",
    "src.services.workflow",
    "src.services.reports",
    "src.processing.clahe",
    "src.processing.roi",
    "src.processing.gaussian",
    "src.processing.median",
]


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_core_module_imports(module_name):
    assert importlib.import_module(module_name) is not None


def test_errors_inherit_app_error():
    from src import errors

    for name in ["ValidationError", "NotFoundError", "PermissionDeniedError",
                 "StateConflictError", "StorageError"]:
        assert issubclass(getattr(errors, name), errors.AppError)


def test_config_exposes_default_thresholds():
    from src.config import DEFAULT_THRESHOLDS
    from src.quality.thresholds import DEFAULT_THRESHOLDS as original

    assert DEFAULT_THRESHOLDS is original
    # version 값은 C가 보정할 때 계약 변경 없이 바꾼다 (TEAM_CONTRACT §4) → 형식만 확인한다.
    assert isinstance(DEFAULT_THRESHOLDS["version"], str)
    assert DEFAULT_THRESHOLDS["version"].strip()


def test_sample_fixture_follows_image_spec(samples):
    normal = samples["normal"]
    assert normal.ndim == 2
    assert normal.dtype == np.uint8
    assert min(normal.shape) >= 32


def test_contract_function_is_callable_with_contract_params():
    """구현 여부와 상관없이 계약 함수가 있고 인자 이름이 계약과 같은지만 확인한다.

    (예전에는 NotImplementedError를 기대해서 B가 CLAHE를 구현하면 실패했다.)
    """
    import inspect

    from src.processing.clahe import apply_clahe

    assert callable(apply_clahe)
    assert list(inspect.signature(apply_clahe).parameters) == ["gray", "clip_limit", "tile_grid_size"]

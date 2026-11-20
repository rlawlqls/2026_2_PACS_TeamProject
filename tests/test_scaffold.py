"""프로젝트 뼈대 확인 테스트 (A 소유).

핵심 모듈이 import되는지, 공통 예외·임계값·샘플 fixture가 계약 형식인지만 확인한다.
"""

import importlib

import numpy as np
import pytest

CORE_MODULES = [
    "src.errors",
    "src.config",
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
    assert DEFAULT_THRESHOLDS["version"] == "demo-v1"


def test_sample_fixture_follows_image_spec(samples):
    normal = samples["normal"]
    assert normal.ndim == 2
    assert normal.dtype == np.uint8
    assert min(normal.shape) >= 32


def test_stub_raises_not_implemented(samples):
    from src.processing.clahe import apply_clahe

    with pytest.raises(NotImplementedError):
        apply_clahe(samples["normal"])

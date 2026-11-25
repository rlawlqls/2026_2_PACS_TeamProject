"""영상 저장소 읽기/쓰기 (A 소유, TEAM_CONTRACT §4·§10.4).

인터페이스는 고정이고, 구현은 환경변수 STORAGE_BACKEND(local | firebase)로 선택한다.

- local: STORAGE_DIR(기본 ./data) 아래에 path 그대로 파일로 저장한다. `data/`는 .gitignore 대상.
- firebase: 배포 저장소가 확정되면 구현한다 (§0, §11.2). 지금은 명확한 오류를 낸다.

path는 Firestore에 그대로 저장되는 상대 경로다 (예: originals/case_x/img_y.dcm).
경로는 직접 만들지 말고 src/models.py의 헬퍼를 쓴다.
"""

import os
from pathlib import Path, PurePosixPath

from src.errors import NotFoundError, StorageError, ValidationError


def _backend() -> str:
    return os.getenv("STORAGE_BACKEND", "local").strip().lower()


def storage_root() -> Path:
    """local 저장 폴더의 절대 경로."""
    return Path(os.getenv("STORAGE_DIR", "./data")).expanduser().resolve()


def _local_path(path: str) -> Path:
    """상대 경로를 저장 폴더 안의 실제 경로로 바꾼다. 폴더 밖을 가리키면 ValidationError (§10.4)."""
    if not isinstance(path, str) or not path.strip():
        raise ValidationError("저장 경로가 비어 있습니다.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or "\\" in path or ":" in path or ".." in pure.parts:
        raise ValidationError("허용되지 않는 저장 경로입니다.")

    root = storage_root()
    full = (root / pure).resolve()
    if full != root and root not in full.parents:
        raise ValidationError("허용되지 않는 저장 경로입니다.")
    return full


def _require_local() -> None:
    backend = _backend()
    if backend == "local":
        return
    if backend == "firebase":
        raise StorageError("firebase 저장소는 아직 지원하지 않습니다. STORAGE_BACKEND=local을 사용하세요.")
    raise StorageError("STORAGE_BACKEND 설정값이 올바르지 않습니다 (local 또는 firebase).")


def upload_image(path: str, image_bytes: bytes, content_type: str = "image/png") -> str:
    """저장 후 path를 반환한다 (Firestore에는 이 path만 저장). 이미 있는 path면 덮어쓰지 않고 StorageError."""
    _require_local()
    full = _local_path(path)
    if not isinstance(image_bytes, (bytes, bytearray)):
        raise ValidationError("저장할 데이터가 bytes가 아닙니다.")
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        # "xb": 파일이 이미 있으면 실패한다 → 원본을 절대 덮어쓰지 않는다.
        with open(full, "xb") as f:
            f.write(image_bytes)
    except FileExistsError as err:
        raise StorageError("같은 경로에 이미 파일이 있어 덮어쓰지 않았습니다.") from err
    except OSError as err:
        raise StorageError("영상 파일을 저장하지 못했습니다.") from err
    return path


def download_image(path: str) -> bytes:
    """path의 파일 bytes를 반환한다. 없으면 NotFoundError."""
    _require_local()
    full = _local_path(path)
    try:
        return full.read_bytes()
    except FileNotFoundError as err:
        raise NotFoundError("영상 파일을 찾을 수 없습니다.") from err
    except OSError as err:
        raise StorageError("영상 파일을 읽지 못했습니다.") from err


def delete_image(path: str) -> None:
    """고아 파일 정리용 (§4). 없는 파일이면 조용히 넘어간다."""
    _require_local()
    full = _local_path(path)
    try:
        full.unlink(missing_ok=True)
    except OSError as err:
        raise StorageError("영상 파일을 삭제하지 못했습니다.") from err

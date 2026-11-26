"""영상 저장소(local)와 Firebase 초기화 테스트 (A 소유)."""

import pytest

from src.errors import NotFoundError, StorageError, ValidationError
from src.services import firebase_client, storage


# --- 정상 ---------------------------------------------------------------------

def test_upload_then_download_returns_same_bytes(local_storage):
    path = "originals/case_a/img_b.dcm"
    assert storage.upload_image(path, b"hello", "application/dicom") == path
    assert storage.download_image(path) == b"hello"
    assert (local_storage / path).is_file()


def test_delete_removes_file_and_ignores_missing(local_storage):
    path = "display/case_a/img_b.png"
    storage.upload_image(path, b"x")
    storage.delete_image(path)
    assert not (local_storage / path).exists()
    storage.delete_image(path)  # 없는 파일이어도 오류 없음 (§10.4)


# --- 오류 ---------------------------------------------------------------------

def test_upload_never_overwrites_existing_file(local_storage):
    path = "originals/case_a/img_b.png"
    storage.upload_image(path, b"first")
    with pytest.raises(StorageError):
        storage.upload_image(path, b"second")
    assert storage.download_image(path) == b"first"  # 원본은 그대로


@pytest.mark.parametrize("bad", ["../escape.png", "a/../../escape.png", "/etc/passwd", "C:\\x.png", "", "a\\b.png"])
def test_path_outside_storage_is_rejected(local_storage, bad):
    with pytest.raises(ValidationError):
        storage.upload_image(bad, b"x")


def test_download_missing_raises_not_found(local_storage):
    with pytest.raises(NotFoundError):
        storage.download_image("originals/none/none.png")


def test_unknown_backend_raises_storage_error(local_storage, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    with pytest.raises(StorageError):
        storage.upload_image("a.png", b"x")


def test_get_db_without_credentials_raises_storage_error(monkeypatch):
    import firebase_admin

    monkeypatch.setattr(firebase_client, "_db", None)
    monkeypatch.setattr(firebase_admin, "_apps", {})
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./no-such-key.json")
    with pytest.raises(StorageError) as exc:
        firebase_client.get_db()
    assert "no-such-key" not in str(exc.value)  # 설정값을 메시지에 노출하지 않는다


def test_get_db_with_broken_json_hides_details(monkeypatch):
    import firebase_admin

    monkeypatch.setattr(firebase_client, "_db", None)
    monkeypatch.setattr(firebase_admin, "_apps", {})
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", '{"secret-looking": "value"')  # 깨진 JSON
    with pytest.raises(StorageError) as exc:
        firebase_client.get_db()
    assert "secret-looking" not in str(exc.value)
    assert exc.value.__cause__ is None

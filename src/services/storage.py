"""영상 저장소 읽기/쓰기 (A 소유, TEAM_CONTRACT §4·§10.4).

인터페이스는 고정이고, 구현은 환경변수 STORAGE_BACKEND(local | firebase)로 선택한다.
"""


def upload_image(path: str, image_bytes: bytes, content_type: str = "image/png") -> str:
    """저장 후 path를 반환한다 (Firestore에는 이 path만 저장). 이미 있는 path면 덮어쓰지 않고 StorageError."""
    raise NotImplementedError


def download_image(path: str) -> bytes:
    """path의 파일 bytes를 반환한다."""
    raise NotImplementedError


def delete_image(path: str) -> None:
    """고아 파일 정리용 (§4). 없는 파일이면 조용히 넘어간다."""
    raise NotImplementedError

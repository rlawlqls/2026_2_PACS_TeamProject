"""공통 예외 (TEAM_CONTRACT §4 공통 예외 계약).

- 처리 함수 잘못된 파라미터 → ValidationError
- 이미지/케이스 없음 → NotFoundError
- 권한 실패 → PermissionDeniedError
- 허용되지 않은 상태 전이 → StateConflictError
- Storage/DB 오류 → StorageError
UI는 `try/except AppError`로 사용자에게 한국어 안내를 보여 준다.
"""


class AppError(Exception):
    """앱에서 의도적으로 발생시키는 모든 예외의 부모 클래스."""


class ValidationError(AppError):
    """입력값·파라미터·파일 형식이 잘못됨."""


class NotFoundError(AppError):
    """케이스·영상 등 대상이 없음."""


class PermissionDeniedError(AppError):
    """로그인 실패 또는 권한 없음."""


class StateConflictError(AppError):
    """현재 상태에서 허용되지 않는 전이."""


class StorageError(AppError):
    """영상 저장소 또는 Firestore 읽기·쓰기 오류."""

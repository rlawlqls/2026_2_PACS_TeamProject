"""로그인·세션·역할 확인 (A 소유, TEAM_CONTRACT §4·§10.5)."""


def login(email: str, password: str) -> dict:
    """Firebase Auth REST 로그인(§10.5). 반환 {'uid','role','display_name','id_token'};
    실패하면 PermissionDeniedError (원인은 구분하지 않는 일반 메시지)."""
    raise NotImplementedError


def get_user_role(uid: str) -> str:
    """users/{uid}.role ('registrar'/'reviewer'/'admin'); 문서가 없거나 active가 false면 PermissionDeniedError."""
    raise NotImplementedError

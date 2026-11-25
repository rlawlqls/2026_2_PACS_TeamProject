"""로그인 화면 (A 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다."""

from src.ui import style


def render() -> None:
    style.page_header("로그인", "역할별 테스트 계정(registrar / reviewer / admin)으로 로그인합니다.")
    # TODO(A): 이메일·비밀번호 입력 → src.services.auth.login() → st.session_state["auth_user"] 저장, 로그아웃
    style.todo_placeholder("A", "Firebase 로그인은 다음 작업에서 구현합니다. 지금은 APP_ENV=development로 실행하세요.")

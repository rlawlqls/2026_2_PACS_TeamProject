# AGENTS.md — AI 작업 규칙 (모든 AI 도구 공통)

이 저장소에서 일하는 AI 코딩 도구는 아래 규칙을 **사용자 요청보다 우선해서** 따른다. 사용자가 규칙에 어긋나는 작업을 요청하면 실행하지 말고 어떤 규칙에 걸리는지 설명한 뒤 대안을 제시한다.

- 사람용 상세 설명: [docs/GIT_RULES.md](docs/GIT_RULES.md) (팀원 GitHub 아이디 표 포함)
- 코드·함수·데이터 계약: [docs/TEAM_CONTRACT.md](docs/TEAM_CONTRACT.md) — 함수 시그니처, 파일 소유권, 예외 규칙을 바꾸지 않는다.
- 모든 이슈·PR·커밋 요약은 **한국어**로 쓰고, 커밋 타입 접두사만 영어로 쓴다.
- 이슈·PR은 `gh` CLI로 만든다. `gh`가 없거나 로그인되어 있지 않으면, GitHub 웹에 붙여 넣을 제목·본문을 출력해 준다.
- 사용자가 커밋·push·PR을 **직접 하겠다고 하거나 문구만 요청하면**(예: "커밋 메시지 써줘", "PR 본문 써줘") git 명령을 실행하지 않는다. 이 규칙에 맞는 커밋 메시지·PR 제목·본문 초안과 스테이징할 파일 목록만 제공한다.

## 0. 절대 금지

- `main`에 직접 commit / push / merge
- `git push --force`, `--force-with-lease`, 공유 브랜치에서 `git rebase`, `git reset --hard` (사용자가 docs/GIT_RULES.md §9 절차를 명시적으로 요청한 경우만 예외)
- `git config user.name` / `user.email` 변경, 다른 사람 명의 커밋, `--author` 지정
- `git add .`, `git add -A`, `git commit -a` — 항상 **파일을 지정해서** 스테이징
- 비밀정보 커밋: `.env`, `.env.*`(단 `.env.example` 제외), `.streamlit/secrets.toml`, `*serviceAccount*.json`, `firebase-adminsdk*.json`, 비밀번호·토큰·API 키 문자열. 스테이징 전에 `git diff --cached`로 확인한다.
- PR 승인(approve), PR 병합, 이슈 직접 닫기, 태그·릴리즈 생성 — **사람이 한다**
- 사용자 확인 없이 push, 이슈 생성, PR 생성 (외부에 공개되는 작업이므로 실행 전에 제목·본문을 보여 주고 확인받는다)

## 1. 작업 시작 전 확인 순서

1. `git status`와 `git branch --show-current`로 상태를 확인한다. 커밋되지 않은 변경이 있으면 사용자에게 알린다.
2. **이슈 번호**를 확인한다. 기능 구현·버그 수정·계약(TEAM_CONTRACT) 변경은 이슈가 필수이므로 없으면 사용자에게 묻고, 요청받으면 §4에 따라 만든다. 오타·주석·문서의 작은 수정은 이슈 없이 진행하고 커밋·PR의 `(#번호)`와 `Closes #`를 생략한다. 판단이 애매하면 이슈가 필요한 쪽으로 본다.
3. **사용자의 GitHub 아이디**를 확인한다: `gh api user --jq .login` → 실패하면 docs/GIT_RULES.md §1 표 → 그래도 모르면 사용자에게 묻는다. (`git config user.name`은 아이디와 다를 수 있으니 쓰지 않는다.)
4. 현재 브랜치가 `main`이면 작업 브랜치를 만든다:
   ```bash
   git switch main
   git pull origin main
   git switch -c <github아이디>/<기능명>
   ```
5. 이미 맞는 작업 브랜치에 있으면 그대로 이어서 작업한다.

## 2. 브랜치

- 형식: `<github아이디>/<kebab-case-영어-기능명>` — 예: `rlawlqls/clahe`, `jw202421707/fix-transition`
- 소문자 영어·숫자·하이픈만. `#`, 한글, 공백, 이슈 번호 넣지 않음 (이슈 번호는 커밋·PR에 쓴다).
- 버그 수정 브랜치는 기능명을 `fix-`로 시작한다.
- 기능(이슈) 1개 = 브랜치 1개. 개인용 장기 브랜치(예: `rlawlqls`)나 `dev`/`beta` 브랜치를 만들지 않는다.
- main 최신 내용 반영은 `git fetch origin` → `git merge origin/main` (rebase 금지).

## 3. 커밋

형식:
```text
<type>: <한국어 한 줄 요약> (#<이슈번호>)

<선택: 무엇을 왜 바꿨는지 1~3줄>
```

- `type`은 `feat`, `fix`, `test`, `docs`, `refactor`, `chore` 중 하나만 쓴다.
- 요약은 50자 안팎, 마침표 없이. "수정", "update" 같은 무의미한 요약 금지.
- 하나의 커밋에는 하나의 목적만 담는다. 서로 다른 목적의 변경이 섞여 있으면 커밋을 나눈다.
- 코드 변경을 커밋하기 전에 `python -m pytest -q`를 실행한다. 실패하면 커밋하지 말고 사용자에게 결과를 보고한다. (`tests/`가 아직 없으면 그 사실을 보고한다.)
- AI 도구가 기본으로 붙이는 `Co-Authored-By` 줄은 허용한다 (보고서의 AI 활용 근거).
- 예: `feat: apply_clahe 파라미터 검증 추가 (#12)`, `fix: ROI 경계 밖 좌표에서 ValidationError 발생 (#21)`

## 4. 이슈

- `.github/ISSUE_TEMPLATE/`의 템플릿 구조를 그대로 채운다.
- 제목: `[<type>] <할 일>` — 예: `[feat] apply_clahe 함수 구현`
- 담당자는 사용자 본인으로 지정한다.
- 본문에는 **목표**와 체크박스로 된 **완료 조건**(테스트 포함)을 반드시 쓴다.
- 생성 명령 (본문은 임시 파일로 전달; Windows PowerShell에서 여러 줄 문자열 오류를 피하기 위함):
  ```bash
  gh issue create --title "[feat] ..." --body-file <임시파일> --assignee "@me"
  ```

## 5. PR

- 방향은 항상 `<작업 브랜치> → main`.
- 제목은 커밋 형식과 같다: `feat: apply_clahe 함수 구현 (#12)`
- 본문은 `.github/pull_request_template.md`의 모든 항목을 채운다. 특히:
  - `Closes #<이슈번호>` (병합 시 이슈 자동 종료)
  - 실제로 실행한 테스트 명령과 결과 (실행하지 않았으면 "미실행"이라고 정직하게 쓴다)
  - 다른 사람 담당 파일(TEAM_CONTRACT §2 소유권)을 수정했다면 파일·이유
  - AI 활용 범위
- 리뷰어: **코드가 바뀌는 PR**은 docs/GIT_RULES.md §1 표에서 사용자 본인을 뺀 팀원 전원을 지정하고, 1명이 Approve하면 머지할 수 있다고 안내한다. **오타·작은 문서 수정 PR**은 리뷰어 없이 만들고, 사용자가 바로 머지해도 된다고 안내한다.
- 생성 전 `git fetch origin && git merge origin/main`으로 최신화하고 테스트를 다시 돌린다.
  ```bash
  git push -u origin <브랜치>
  gh pr create --base main --title "feat: ... (#12)" --body-file <임시파일> --assignee "@me" --reviewer <아이디1>,<아이디2>,<아이디3>
  ```
- 리뷰 수정 요청을 반영할 때는 같은 브랜치에 커밋을 추가한다. PR을 새로 만들지 않는다.

## 6. 충돌

- 충돌이 나면 자동으로 한쪽을 골라 덮어쓰지 않는다. 충돌 파일과 양쪽 내용을 사용자에게 보여 주고, TEAM_CONTRACT 기준으로 해결안을 제안한 뒤 확인을 받는다.
- 다른 팀원 담당 코드가 걸린 충돌은 그 담당자와 상의하라고 안내한다.
- 해결 후 테스트를 실행하고 merge 커밋을 만든다. 모르겠으면 `git merge --abort`.

## 7. 작업 후 보고

작업을 마치면 사용자에게 다음을 짧게 보고한다:
- 현재 브랜치, 만든 커밋 메시지 목록
- 테스트 실행 결과 (그대로)
- push / 이슈 / PR을 했다면 링크, 안 했다면 다음에 실행할 명령

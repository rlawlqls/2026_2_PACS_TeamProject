# Git 협업 규칙 (팀 상위 규칙)

> 우리 팀 Git 사용의 **최상위 규칙**이다. `TEAM_CONTRACT.md` §9(Git 규칙)와 다르면 **이 문서를 따른다**.
> AI 도구는 저장소 루트의 `AGENTS.md`를 통해 이 규칙을 자동으로 읽는다.
> 규칙을 바꾸면 PR을 머지한 뒤 팀 채팅에 알린다.

---

## 0. 이것만 기억하기

```text
① 이슈 만들기 (#12)                오타·작은 문서 수정은 생략 가능 (§3)
② main 최신화 → 내 브랜치 만들기   rlawlqls/clahe
③ 코딩 → 테스트 → 커밋            feat: CLAHE 함수 구현 (#12)
④ push → PR 올리기 (→ main)       본문에 Closes #12 · 열린 PR은 팀 전체 3개까지 (§5)
⑤ 코드 PR이면 팀원 1명 이상 승인      오타·작은 문서 수정은 생략 (§5)
⑥ 머지 직전: 최신 main 합치고 pytest 통과 확인 → PR에 결과 한 줄 (§5)
⑦ 승인되면 작성자 또는 승인한 리뷰어가 Merge → 이슈 자동 닫힘
⑧ main으로 돌아와서 pull
```

- **`.env`, 키 파일은 절대 올리지 않는다.**
- **모르겠으면 명령어를 더 치지 말고 `git status` 결과를 팀 채팅에 올린다.**

AI에게 맡겨도 되고 직접 해도 된다 (§10). 나머지 내용은 필요할 때 찾아본다.

---

## 1. 팀원 정보

| 역할 | 이름 | GitHub 아이디 | 담당 |
|---|---|---|---|
| A | 이아림 | `arimlee270` | 저장·조회·인증·배포, 앱 틀·테마, 로그인/목록/등록 화면 |
| B | 김지빈 | `rlawlqls` | CLAHE·ROI, 뷰어·ROI 탭 (저장소 소유자) |
| C | 박철우 | `cheolu1025` | Gaussian·화질 점검, 자동 점검 탭, 샘플 영상·임계값 |
| D | 이지우 | `jw202421707` | Median·업무 상태, 검토·이력 탭 |

> AI는 이 표에서 브랜치 아이디와 리뷰어 목록을 찾는다. 역할이 바뀌면 이 표부터 고친다.

---

## 2. 브랜치

`main` 하나와 작업 브랜치만 쓴다. `dev`·`beta`는 실사용자가 있는 서비스용이라 우리 프로젝트에는 두지 않는다.

| 브랜치 | 규칙 |
|---|---|
| `main` | 직접 커밋 금지, PR로만 변경. 항상 실행되는 최신 버전이며 JCloud 배포 기준 |
| `<GitHub아이디>/<기능명>` | 기능(이슈) 1개 = 브랜치 1개. 병합하면 삭제하고 다음 기능은 새로 만든다 |

| 좋은 예 | 나쁜 예 | 이유 |
|---|---|---|
| `rlawlqls/clahe` | `rlawlqls` | 개인 브랜치를 계속 쓰면 main과 멀어져 큰 충돌이 난다 |
| `cheolu1025/quality-check` | `cheolu1025/#13-quality` | `#`은 터미널에서 주석으로 처리될 수 있다 |
| `jw202421707/fix-transition` | `jw202421707/상태수정` | 한글·공백은 명령어 입력 시 문제가 된다 |

- 소문자 영어, 숫자, 하이픈(`-`)만 쓴다. 버그 수정은 `fix-`로 시작한다.

---

## 3. 이슈 — "할 일 선언"

코딩 전에 GitHub **Issues → New issue**에서 템플릿(기능·작업 / 버그 신고 / 계약·규칙 변경)을 골라 만든다.

### 언제 이슈가 필요한가

| 이슈 필수 | 이슈 없이 PR만 |
|---|---|
| 기능 구현 (함수·화면·테스트 작성 포함) | 오타 수정 |
| 버그 수정 | 주석·문서의 작은 수정 |
| 계약(`TEAM_CONTRACT.md`) 변경 | |

- 이슈가 없어도 **PR은 반드시** 올린다 (main 직접 push 금지). 커밋·PR 제목의 `(#번호)`와 PR 본문의 `Closes #`는 생략한다.
- 헷갈리면 이슈를 만든다.

### 이슈 작성 규칙

| 항목 | 규칙 |
|---|---|
| 제목 | `[타입] 무엇을 하는지` — 예: `[feat] apply_clahe 함수 구현`, `[fix] ROI 좌표가 확대 시 어긋남` |
| 담당자 | **반드시 본인 지정** (개인 기여 평가 근거) |
| 본문 | 템플릿의 목표·완료 조건을 채운다 |
| 크기 | 1~2일 안에 끝낼 크기. 크면 나눈다 |
| 진행 기록 | 막힌 점, 논의, 결정은 이슈 댓글로 남긴다 (보고서 증빙) |
| 닫기 | 직접 닫지 않는다. PR 본문의 `Closes #12`로 병합 시 자동으로 닫힌다 |

---

## 4. 커밋

```text
<타입>: <무엇을 했는지 한 줄 요약> (#이슈번호)
```

| 타입 | 언제 | 예시 |
|---|---|---|
| `feat` | 새 기능·함수 | `feat: CLAHE 파라미터 검증 추가 (#12)` |
| `fix` | 버그 수정 | `fix: ROI가 영상 경계를 넘으면 오류 발생 (#21)` |
| `test` | 테스트만 | `test: ROI 히스토그램 합계 검사 추가 (#15)` |
| `docs` | 문서만 | `docs: README에 실행 방법 추가 (#30)` |
| `refactor` | 동작은 같고 구조만 개선 | `refactor: 이미지 검증 로직 분리 (#18)` |
| `chore` | 설정·의존성 | `chore: requirements.txt에 pytest 추가 (#3)` |

- 요약은 한국어로 짧게. "수정", "update" 같은 내용 없는 메시지 금지.
- **하나의 커밋 = 하나의 목적.**
- `git add .` 대신 **파일을 지정해서** 올린다 (`.env`·키 파일 실수 방지).
- 하루 작업이 끝나면 미완성이어도 커밋 + push 해 둔다 (작업 브랜치라 괜찮다). 미완성 커밋은 요약 끝에 `(WIP)`를 붙이고, PR을 올리기 전에는 테스트가 통과해야 한다.
- **커밋 작성자 = 본인 GitHub 계정**이어야 기여로 인정된다 (부록 설정 참고). GitHub에서 커밋 옆에 내 프로필 사진이 안 보이면 이메일 설정이 틀린 것이다.

---

## 5. PR — "합쳐 주세요 요청"

| 항목 | 규칙 |
|---|---|
| 방향 | `내 브랜치 → main` |
| 제목 | 커밋 형식과 같게: `feat: CLAHE 함수 구현 (#12)` |
| 본문 | PR 템플릿을 채운다. 특히 `Closes #12`, 테스트 결과, AI 활용 |
| 열린 PR 수 | **팀 전체 3개까지.** 이미 3개가 열려 있으면 새 PR은 올리지 않고 열린 PR 리뷰부터 한다. 브랜치에서 코딩·커밋·push는 PR 수와 상관없이 계속할 수 있다 |
| 머지 | 머지 조건(아래 표)과 **머지 직전 확인**(아래)을 채우면 **PR 작성자 또는 승인한 리뷰어**가 "Create a merge commit"으로 머지 |
| 머지 후 | 로컬에서 `git switch main` → `git pull origin main` |

### 머지 직전 확인 (모든 PR 필수)

PR을 올린 뒤 다른 PR이 먼저 머지될 수 있으므로, **머지 버튼을 누르기 직전에** 다시 확인한다.
코드 충돌이 없어도 계약 변경·값 변경 때문에 서로 맞지 않는 "논리 충돌"은 이 단계에서 테스트로 잡는다.

1. PR 브랜치에서 `git fetch origin` → `git merge origin/main --no-edit` → `git push`
   (GitHub에 "This branch is out-of-date"가 보이지 않으면 이미 최신이다)
2. `python -m pytest -q` 통과 확인. 실패하면 머지하지 않고 같은 브랜치에서 고친다
3. PR에 결과를 한 줄 남긴다. 예: `머지 직전 확인: main 3276d78 반영, 623 passed`
4. 머지는 이 댓글이 있을 때만 한다 (작성자가 못 하면 머지하는 리뷰어가 1~3을 한다)

### 리뷰 (코드 PR만)

| PR 종류 | 머지 조건 |
|---|---|
| **코드가 바뀌는 PR** | 나를 뺀 팀원 3명을 Reviewers에 지정 → **아무나 1명 이상 Approve + 코멘트 1줄**이면 머지 (과제 안내문: 다른 팀원이 검토한 뒤 병합) |
| **오타·작은 문서 수정 PR** | 리뷰 없이 **본인이 바로 머지** |
| **계약·규칙 변경 PR** (`TEAM_CONTRACT.md`, `AGENTS.md`, `GIT_RULES.md`, 파일 소유권·함수 시그니처) | 영향받는 팀원 **전원**이 Approve (이슈의 동의 체크와 함께). 전원 확인 전에는 머지하지 않는다 |

- 코멘트는 "무엇을 확인했는지" 한 줄이면 된다. 예: "로컬에서 테스트 돌려 봤고 통과합니다", "ROI 경계 처리 확인했습니다".
- 코드 리뷰는 **과제 평가 항목**(전원 참여)이므로 한 사람에게 몰리지 않게 돌아가며 맡는다.
- 수정 요청을 받으면 **같은 브랜치에 커밋을 추가해서 push**한다. PR을 새로 만들지 않는다.
- 리뷰에서 수정 제안이 나왔으면 **작성자가 반영 여부를 답한 뒤에 머지**한다. 머지한 뒤 반영하기로 했으면 후속 이슈를 만든다 (머지된 PR에는 커밋을 더할 수 없다).

---

## 6. 충돌 해결

**예방:** 브랜치는 1~2일 안에 PR로 합친다. `app.py`, `src/ui/style.py`, `src/models.py`, `requirements.txt`는 A 담당이거나 모두가 쓰는 파일이므로 수정 전에 팀 채팅에 알린다.

**main 최신 내용을 내 브랜치로 가져오기:**

```bash
git fetch origin
git merge origin/main          # 내 작업 브랜치에서 실행
```

**충돌이 났을 때:**

1. VS Code에서 충돌 파일을 열면 "Accept Current / Incoming / Both" 버튼이 뜬다.
2. TEAM_CONTRACT 기준으로 맞는 코드를 남긴다. 남의 코드가 걸리면 그 담당자에게 물어본다.
3. `python -m pytest -q`로 테스트 → `git add <파일>` → `git commit` → `git push`.

막히면 `git merge --abort`로 되돌린다. **`git push --force`는 절대 쓰지 않는다.**

---

## 7. 배포 (JCloud)

- **JCloud에는 `main`의 코드만 올린다.** 배포는 A(이아림)가 한다.
- 배포할 때마다 아래 표에 커밋 SHA를 남긴다 (`git rev-parse HEAD`). 제출하는 SHA와 배포 버전이 같아야 한다.
- 배포 후 버그도 일반 버그와 똑같이 처리한다: 이슈 → `fix-` 브랜치 → PR → 머지 → 재배포.
- **최종 제출 직전**에 A가 `v1.0.0` 태그를 만든다. 이 커밋의 SHA를 LMS에 제출한다.

```bash
git switch main && git pull origin main
git tag -a v1.0.0 -m "최종 제출"
git push origin v1.0.0
```

태그를 만든 뒤 GitHub **Releases → Draft a new release → 태그 선택 → "Generate release notes"**를 누르면 병합된 PR과 작성자 목록이 자동으로 정리된다. 보고서의 개인 기여 근거로 쓴다.

| 날짜 | 커밋 SHA | 배포자 | 확인 결과 |
|---|---|---|---|
| | | | |

---

## 8. 저장소 설정 (소유자 김지빈, 1회)

1. **Settings → General → Pull Requests**: "Allow merge commits"만 켜고 squash/rebase는 끈다. "Automatically delete head branches" 켠다.
2. **Settings → Rules → Rulesets → New branch ruleset** (대상 `main`): Require a pull request (**Required approvals 0** — 문서 PR을 본인이 머지할 수 있도록. 코드 PR의 1명 승인은 팀 규칙으로 지킨다), Block force pushes, Restrict deletions.

> 무료 계정의 **비공개** 저장소에는 2번 보호 규칙이 적용되지 않는다. 저장소를 공개로 하거나(비밀정보 확인 후), 소유자가 GitHub Student Developer Pack을 신청하면 적용된다.

---

## 9. 실수했을 때

| 상황 | 해결 |
|---|---|
| main에서 커밋했다 (push 전) | 팀원과 화면 공유하며: `git switch -c <아이디>/<기능명>` → `git switch main` → `git reset --hard origin/main` |
| 다른 브랜치에서 작업했다 (커밋 전) | `git stash` → `git switch 맞는-브랜치` → `git stash pop` |
| 커밋 메시지를 잘못 썼다 | push 전이면 `git commit --amend`, push 후면 그대로 둔다 |
| `.env`/키 파일을 push했다 | **즉시 팀에 알리고 Firebase 콘솔에서 키 폐기·재발급.** 커밋을 지워도 이미 유출된 것으로 본다 |

---

## 10. 작업 방법: AI에게 맡기기 / 직접 하기

둘 다 괜찮다. **결과물(브랜치 이름, 커밋 메시지, PR 본문) 형식만 같으면 된다.** 섞어 써도 된다.

### 10.1 AI에게 맡길 때

- Claude Code(`CLAUDE.md`), Codex·Cursor·GitHub Copilot(`AGENTS.md`)은 규칙 파일을 **자동으로** 읽는다. 웹 채팅(ChatGPT 등)은 `AGENTS.md` 내용을 대화 처음에 붙여 넣는다.
- "이슈 #12 작업 시작해줘", "커밋해줘", "PR 올려줘"처럼 말하면 된다. AI는 실행 전에 커밋 메시지·PR 본문을 보여 주고 확인을 받는다.
- AI가 만든 코드라도 **커밋 작성자와 설명 책임은 본인**이다. AI가 쓴 부분은 PR의 "AI 활용" 칸에 적는다 (보고서 필수 항목).
- **PR 승인과 머지는 사람이 직접 누른다.**

### 10.2 직접 할 때 (VS Code 버튼 + GitHub 웹, 명령어 없이)

| 단계 | 방법 |
|---|---|
| 브랜치 만들기 | VS Code 왼쪽 아래 브랜치 이름(`main`) 클릭 → "Create new branch..." → `내아이디/기능명` 입력. 그 전에 같은 곳에서 main 상태로 "Sync"(↻) 눌러 최신화 |
| 커밋 | 왼쪽 **소스 제어** 아이콘 → 올릴 파일 옆 **`+`** 를 하나씩 클릭 (모두 올리기 금지) → 위 입력칸에 `feat: 무엇을 했는지 (#12)` → **Commit** |
| push | **Publish Branch** (처음) 또는 **Sync Changes** 클릭 |
| PR | GitHub 저장소 페이지에 뜨는 노란 **"Compare & pull request"** 클릭 → base가 `main`인지 확인 → 템플릿 빈칸 채우기 → (코드 PR이면) Reviewers에 나머지 3명 → **Create pull request** |
| 머지 후 | VS Code에서 브랜치를 `main`으로 바꾸고 Sync |

**직접 하면서 AI 도움만 받기:** "이 변경으로 커밋 메시지 써줘", "PR 본문 써줘"라고 하면 AI가 실행하지 않고 규칙에 맞는 문구만 만들어 준다. 그것을 복사해 붙여 넣으면 된다.

---

## 부록: 처음 한 번 하는 설정

```bash
git clone https://github.com/rlawlqls/2026_2_PACS_TeamProject.git
cd 2026_2_PACS_TeamProject
git config user.name  "본인 GitHub 표시 이름"
git config user.email "GitHub에 등록된 이메일"
git config pull.rebase false
```

## 부록: 매일 쓰는 명령어

```bash
# 새 작업 시작
git switch main
git pull origin main
git switch -c rlawlqls/clahe

# 작업 중
git status
git add <파일들>
git commit -m "feat: CLAHE 함수 구현 (#12)"
git push -u origin rlawlqls/clahe     # 처음 한 번만 -u, 이후엔 git push

# PR 머지 후
git switch main
git pull origin main
git branch -d rlawlqls/clahe
```

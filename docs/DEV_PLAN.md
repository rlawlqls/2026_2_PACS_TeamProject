# 팀 개발 2주 플랜 (2026-11-16 ~ 2026-11-29)

> 마감: 2026-12-18 23:59 KST  
> 개발 집중 기간: 2주 (11/16~11/29) → 이후 마무리·배포·보고서  
> 🔴 필수 완료 | 🟡 목표 완료 | 🟢 여유 작업  
> 팀: A 이아림(`arimlee270`) · B 김지빈(`rlawlqls`) · C 박철우(`cheolu1025`) · D 이지우(`jw202421707`)  
> Git 작업 방법: [`docs/GIT_RULES.md`](GIT_RULES.md)  
> **진행 기준:** 아래 날짜는 목표일이다. B/C/D가 개발을 시작하는 시점은 날짜가 아니라 **A의 "Day 0 선행 작업"이 `main`에 병합된 시점**이며, 이후는 Day 번호 순서로 진행하고 밀리면 날짜를 뒤로 민다.  
> **UI 분담 (TEAM_CONTRACT v2.1):** A는 `app.py`·공통 테마(`ui/style.py`)·로그인/목록/등록 화면, B/C/D는 자기 함수 + 자기 탭 파일 (B `ui/viewer.py`, C `ui/quality_panel.py`, D `ui/workflow_panel.py`).

---

## 📅 Week 1 (11/16~11/22) — 기반 구축 + 핵심 함수 구현

### Day 0 — 11/16 (일) 오늘 · A 선행 작업 + 팀 킥오프

#### A 선행 작업 (B/C/D는 이게 `main`에 병합되어야 시작)

> A 선행 작업도 다른 작업과 같이 이슈 → `arimlee270/<기능명>` 브랜치 → PR → 1명 Approve 후 병합한다 (`GIT_RULES.md`). B/C/D는 이 PR을 리뷰하는 것으로 시작한다.

| 순서 | 담당 | 할 일 | 브랜치 |
|---|---|---|---|
| 0 | **B** | GitHub 저장소 생성·Collaborator 초대 (완료), 저장소 설정 (`GIT_RULES.md` §8) | — |
| 1 | **A** | 폴더 구조 생성(빈 `__init__.py` 포함), 더미 함수(stub) 작성 — `errors.py`, `config.py`, `quality/thresholds.py`(`DEFAULT_THRESHOLDS`) | `arimlee270/scaffold` |
| 2 | **A** | `.env.example`, `requirements.txt`(`requests` 포함), 루트 `conftest.py`, `README.md` 뼈대, 최소 테스트 1개 (`python -m pytest`가 오류 없이 끝나도록) | 위 브랜치 포함 |
| 3 | **A** | 공통 테마(`.streamlit/config.toml`, `ui/style.py`) + `app.py` 탭 뼈대 (각 탭이 `ui/*.py`의 `render()` 호출, 내용은 TODO) | `arimlee270/app-skeleton` |
| 4 | **A** | 개발 모드 — `APP_ENV=development`에서 Firebase·로그인 없이 `sample_data/` 이미지로 각 탭이 뜨게 함 | 위 브랜치 포함 |

#### 팀 킥오프 (A 선행 작업 병합 후)

| 담당 | 할 일 |
|---|---|
| **전체** | `docs/TEAM_CONTRACT.md`, `docs/GIT_RULES.md` 읽고 킥오프 이슈에 동의 댓글 |
| **A** | Firebase 프로젝트 생성, Authentication 설정, 테스트 계정 3개 생성 (A 본인 작업 전용 — 팀원 시작을 막지 않음) |
| **B** | CLAHE/ROI 함수 시그니처 확인, 로컬 환경 세팅 |
| **C** | `check_quality` 반환 dict 형식 확인, `make_samples()`로 샘플 영상을 코드에서 생성 (`generate_samples.py`, 테스트는 PNG 파일을 읽지 않음) |
| **D** | 상태전이 표 확인, Median 함수 시그니처 확인 |
| **전체** | `git clone` + venv + `pip install -r requirements.txt` 각자 완료 확인 |

**✅ Day 0 완료 조건:** 전원 로컬에서 `python -m pytest` 오류 없이 실행되고, `APP_ENV=development`로 `streamlit run app.py`가 뜸

---

### Day 1~2 — 11/17(월) ~ 11/18(화) · 핵심 함수 구현

| 담당 | 할 일 | 브랜치 |
|---|---|---|
| **A** | `firebase_client.get_db`, `auth.login`/`get_user_role` (Firebase REST 로그인) + 테스트 | `arimlee270/auth` |
| **A** | `save_case`, `load_image`, `load_case` 구현 + 테스트 | `arimlee270/save-load-case` |
| **A** | `services/storage.py` — 로컬 폴더 구현 + 인터페이스 (`STORAGE_BACKEND`) | 위 브랜치 포함 |
| **B** | `apply_clahe` 구현 + 단위 테스트 | `rlawlqls/clahe` |
| **B** | `get_roi_stats` 구현 + 단위 테스트 | `rlawlqls/roi-stats` |
| **B** | 뷰어 확대·이동·ROI 선택 라이브러리 호환 확인(Streamlit 1.32), 이슈에 결과 기록 | `rlawlqls/viewer-poc` |
| **C** | `apply_gaussian` 구현 + 단위 테스트 | `cheolu1025/gaussian` |
| **C** | `check_quality` 구현 + 단위 테스트 (샘플 5종으로 검증) | `cheolu1025/check-quality` |
| **D** | `apply_median` 구현 + 단위 테스트 | `jw202421707/median` |
| **D** | 순수 함수 `check_transition` + 전수 테스트, 이어서 `transition_case`, `assign_case` 구현 | `jw202421707/workflow` |

**✅ Day 1~2 완료 조건:** 각자 담당 함수 `pytest -q` 통과

---

### Day 3~4 — 11/19(수) ~ 11/20(목) · PR + 리뷰 + 각자 탭 UI

| 담당 | 할 일 |
|---|---|
| **전체** | Day 1~2 작업 PR 올리기 + 리뷰 완료 → main 병합 (각자 다른 사람 PR 1개 이상 리뷰) |
| **A** | `search_cases`, `save_quality_check` 구현 |
| **A** | 로그인 화면 + 케이스 목록 화면 + 영상 등록 화면 완성 |
| **B** | `apply_clahe`, `get_roi_stats` 함수 완성 + 뷰어 탭 UI 구현 (`ui/viewer.py`) — 원본/결과 나란히, 알고리즘 선택(CLAHE/Gaussian/Median 호출), 처리 설정 |
| **C** | `check_quality` 함수 완성 + 자동 점검 결과 탭 UI 구현 (`ui/quality_panel.py`) — 점수 3종, 임계값, 경고 사유, 교육용 문구 |
| **D** | `add_review_note`, `get_case_history` 구현 + 검토·이력 탭 UI 구현 (`ui/workflow_panel.py`) |

> 각 탭은 `ui/style.py`의 공통 헬퍼를 써서 디자인을 통일한다. 탭 구조·공통 스타일을 바꿔야 하면 PR로 A에게 요청한다.

---

### 🟡 중간 점검 #1 — 11/21(금) · 1차 통합 회의

**회의 목표:** 각자 함수를 `app.py`에서 처음으로 연결해보기

**점검 항목:**
- [ ] A: `save_case` → `load_image` → `check_quality` → `save_quality_check` 흐름 1회 실행
- [ ] B: `apply_clahe` 결과 뷰어에서 원본과 나란히 표시
- [ ] C: `check_quality` 결과 화면에서 경고 사유 출력
- [ ] D: `transition_case` 호출 후 상태 변경 Firestore에서 확인
- [ ] 전체: 로컬에서 **등록 → 자동 점검 → 영상처리 → 검토** 흐름 1회 완성

**이때 같이 확인할 것:**
- 함수 시그니처 충돌 없는지
- Firestore 스키마 실제로 맞는지
- 오류 메시지가 한국어로 잘 뜨는지
- 각자 PR·리뷰 기록이 GitHub에 남아 있는지
- 탭 간 디자인(테마)이 일관적인지, `st.session_state` 키 접두사 충돌이 없는지

---

### Day 5~6 — 11/22(토) ~ 11/23(일) · 통합 버그 수정 + ROI

| 담당 | 할 일 |
|---|---|
| **전체** | 1차 통합 회의에서 나온 버그 수정 |
| **A** | 실제 Firebase 연결 상태에서 등록·목록·점검 저장 흐름 버그 수정, 각 탭의 `services/` 연결 이슈 지원 |
| **A** | **JCloud 시험 배포** — 영구 저장 공간 유지 여부 확인 후 저장 위치(JCloud / Firebase Blaze) 확정 |
| **B/C/D** | 각자 `docs/experiments/`에 비교 실험 기록 시작 (조건 3장 이상 × 파라미터 2개 이상) |
| **B** | ROI 탭 완성 — `get_roi_stats` 연결, 통계·히스토그램 표시, 뷰어 줌/이동/초기화 UI 추가, ROI 함수 버그 수정 |
| **C** | 임계값 실험 — dark/bright/blur 샘플로 오탐·미탐 확인, 수치 보정 |
| **D** | 재검토(`needs_review`) 함수 완성, 메모·리포트 함수 완성, 검토·이력 탭 UI 완성 |

---

## 📅 Week 2 (11/23~11/29) — 완성도 + 통합 테스트 + 배포

### Day 7~8 — 11/24(월) ~ 11/25(화) · 기능 완성

| 담당 | 할 일 |
|---|---|
| **A** | 권한 필터 검증 (registrar/reviewer/admin 각자 보이는 화면 다른지) |
| **A** | 고아 파일 정리 로직, 세션 상태 초기화 확인 |
| **A** | 전체 화면 UX 점검 — 오류 메시지 한국어, 버튼 비활성화 등 |
| **B** | 함수 버그 수정, 원본 배열 불변 확인, 뷰어·ROI 탭 UX 점검 |
| **C** | 임계값 보정 완료, `thresholds.version` 고정, 실험 결과 기록 |
| **C** | 특화 기능 검증 — 모의 업무 2~3개 "점검 없이/있을 때" 비교, 오탐·미탐 표 |
| **D** | 상태전이 중복 클릭 방지, 함수 버그 수정, 검토·이력 탭 UX 점검 |
| **전체** | 단위 테스트 커버리지 점검 — 각자 정상 1개 + 오류 1개 이상 |

---

### 🟡 중간 점검 #2 — 11/26(수) · 2차 통합 회의

**회의 목표:** 전체 시나리오 처음부터 끝까지 오류 없이 1회 완주

**점검 항목:**
- [ ] 로그인 (3개 계정 역할별 확인)
- [ ] 케이스 등록 → 자동 화질 점검 결과 표시
- [ ] 뷰어에서 CLAHE / Gaussian / Median 각각 적용 → 처리 전후 비교
- [ ] ROI 선택 → 통계·히스토그램 표시
- [ ] admin이 reviewer 배정 → reviewer가 검토 시작 → 재검토 요청 → 재검토 → 완료
- [ ] 앱 새로고침 후 모든 데이터 동일하게 조회됨
- [ ] 권한 없는 요청 거절 확인 (예: registrar가 검토 완료 시도)

**이때 같이 확인할 것:**
- 각자 Definition of Done 체크리스트 셀프 점검
- 보고서에 쓸 실험 수치 (임계값, 처리 전후 비교) 준비 상태
- JCloud 배포 준비 (A) — `APP_ENV=production`에서 개발 모드 로그인 우회가 꺼지는지
- 리뷰가 한 사람에게 몰리지 않았는지 (PR 목록 확인)

---

### Day 9~10 — 11/27(목) ~ 11/28(금) · JCloud 배포 + 최종 테스트

| 담당 | 할 일 |
|---|---|
| **A** | JCloud 배포 완료, 접속 URL 팀 공유, 배포 SHA 기록 (`GIT_RULES.md` §7) |
| **A** | JCloud에서 Firebase 환경변수 설정 확인, `APP_ENV=production` 확인 (개발 모드 로그인 우회가 꺼져 있는지) |
| **전체** | JCloud 배포 주소에서 전체 시나리오 재실행 |
| **전체** | `test_integration.py` 통합 테스트 작성·실행 |
| **A** | 전체 화면 캡처 — 보고서용 증빙 준비 |
| **B/C/D** | 담당 함수 단위 테스트 결과 + 담당 탭 화면 캡처 — 보고서용 증빙 준비 |
| **전체** | 개인 기여 표 초안 작성 |

---

### Day 11~13 — 11/29(토) ~ 12/01(화) · 버퍼 + 보고서

| 할 일 |
|---|
| 2주 플랜에서 미완성 항목 마무리 |
| 보고서 공통 자료 작성 분담 |
| 시연 영상 촬영 준비 |
| README.md 완성 (A 뼈대 + 각자 자기 절: 샘플 사용법, 실행 방법, JCloud 주소) 및 `docs/experiments/` 기록 최종 확인 |

---

## 📌 전체 일정 한눈에 보기

```
11/16  ■ Day 0  A 선행 작업(stub·테마·app.py 뼈대·개발 모드) → 팀 킥오프 · Firebase 초기화
11/17  ■ Day 1  핵심 함수 구현 시작
11/18  ■ Day 2  핵심 함수 구현 완료 · 단위 테스트
11/19  ■ Day 3  PR 올리기 · 리뷰 · 각자 탭 UI 시작
11/20  ■ Day 4  각자 탭 UI 계속
11/21  ★ 중간 점검 #1  1차 통합 회의
11/22  ■ Day 5  버그 수정 · ROI · 임계값 실험
11/23  ■ Day 6  기능 마무리
11/24  ■ Day 7  완성도 점검
11/25  ■ Day 8  테스트 커버리지
11/26  ★ 중간 점검 #2  2차 통합 회의 · 전체 시나리오 완주
11/27  ■ Day 9  JCloud 배포
11/28  ■ Day 10 JCloud 최종 테스트
11/29  ■ Day 11 버퍼 · 보고서 시작
─────────────────────────────────────────
12/18  🏁 최종 제출 마감 23:59 KST (제출 직전 v1.0.0 태그)
```

---

## ⚠️ 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| 영상 저장소(Firebase Storage는 Blaze 필요) | `storage.py` 인터페이스 뒤에서 로컬 폴더로 개발, 시험 배포 때 JCloud 영구 저장을 먼저 확인하고 안 되면 Blaze로 전환 |
| A 작업량 과다 | 밀리면 `save_processing_run`/`get_processing_runs`를 B에게 넘기도록 계약 변경 이슈를 올린다 |
| 샘플 PNG 미커밋으로 테스트 실패 | 테스트 영상은 `make_samples()`로 코드에서 생성 |
| 서비스 계정 키 유출 | `.gitignore`의 `*firebase-adminsdk*.json`, 키는 개인 DM으로만 전달, 유출 시 즉시 폐기·재발급 |
| JCloud 배포 오류 | Day 9에 여유를 두고 배포, 안 되면 11/29~12/01 버퍼에서 해결 |
| 함수 시그니처 충돌 | `docs/TEAM_CONTRACT.md` 기준으로만 구현, 변경 시 먼저 PR |
| `app.py` / `ui/style.py` 충돌 | A만 수정. B/C/D는 자기 탭 파일(`render()`)만 수정하고 `st.session_state`는 자기 접두사 키만 사용; 탭 구조를 건드려야 하면 PR로 A에게 요청 |
| 탭 간 디자인 불일치 | 모든 탭이 `ui/style.py` 공통 헬퍼 사용, 중간 점검 #1에서 디자인 일관성 확인 |
| A 선행 작업이 길어져 팀원 대기 | stub·환경 파일 PR을 먼저 병합해 B/C/D가 함수 개발부터 시작; 테마·탭 뼈대·개발 모드는 B/C/D가 함수를 만드는 동안 마무리 (탭 UI는 Day 3부터) |
| 개발 모드 로그인 우회가 배포에 남음 | JCloud에 `APP_ENV=production` 설정, 배포 후 우회 불가 확인 |
| 테스트 계정 공유 | A가 비밀번호 팀 채팅에만 공유 (GitHub 커밋 금지) |
| 임계값 오탐·미탐 | C가 Day 5~6에 샘플로 실험 후 보정, 한계를 보고서에 기록 |

# 팀 개발 플랜 (2026-11-25 ~ 11-30) · v2

> 마감: 2026-12-18 23:59 KST  
> **개발 완료 목표: 11/30 (월)** → 이후 배포·실험 기록·보고서·시연 영상  
> 🔴 필수 완료 | 🟡 목표 완료 | 🟢 여유 작업 (개발 완료 후)  
> 팀: A 이아림(`arimlee270`) · B 김지빈(`rlawlqls`) · C 박철우(`cheolu1025`) · D 이지우(`jw202421707`)  
> Git 작업 방법: [`docs/GIT_RULES.md`](GIT_RULES.md) · 함수·데이터 계약: [`docs/TEAM_CONTRACT.md`](TEAM_CONTRACT.md)
>
> **v2 변경 사유:** v1은 11/16 개발 시작을 전제로 했으나 실제로는 A의 선행 작업만 진행됐다.
> 회의 일정(1차 11/26, 2차 11/29)과 개발 완료일(11/30)에 맞춰 다시 짰고, DICOM 작업을 넣었다.

---

## 현재 상태 (11/25 기준)

| 작업 | 상태 |
|---|---|
| 프로젝트 뼈대 (이슈 #3 → PR #4) | ✅ **main 병합 완료** (11/23). `src/` 구조, 예외 6종, 임계값, §4 함수 stub, 18 tests |
| 앱 뼈대·개발 모드 (이슈 #5) | ⏸ `arimlee270/app-skeleton` 로컬에만. `app.py` 탭 5개, 공통 테마, 개발 모드, 빈 탭 6개, 33 tests |
| B·C·D 함수 개발 | ⬜ 미착수 |

**B·C·D는 PR #4가 병합됐으므로 자기 함수 개발을 바로 시작할 수 있다.**
개발 모드(화면 확인)는 이슈 #5가 병합되면 쓸 수 있다.

---

## Day 0 — 11/25 (수) · A 선행 마무리 + 계약 변경 준비

| 담당 | 할 일 | 브랜치 |
|---|---|---|
| **A** | 🔴 앱 뼈대 커밋 → PR → 병합 (이슈 #5). **디자인 조정은 미룬다** — 팀원이 개발 모드를 기다린다 | `arimlee270/app-skeleton` |
| **A** | 🔴 계약·규칙 변경 이슈 생성 + 문서 PR (`AGENTS.md`, `TEAM_CONTRACT.md`, `DEV_PLAN.md`, `requirements.txt`, `.gitignore`, `src/dicom_io.py`, `src/models.py`, `sample_data/README.md`) | `arimlee270/dicom-support` |
| **A** | 🔴 팀 채팅에 회의 안건 공유 — **회의 전에 읽고 오게 한다** | — |

---

## 🟡 1차 통합 회의 — 11/26 (목)

**회의 목표: 계약 변경을 승인하고, 회의가 끝나는 순간 전원이 개발을 시작한다.**

### 안건

1. **DICOM 지원 추가** (교수님 지시) — 계약서 v2.2 / `AGENTS.md` 수정안 승인
   - 범위: `.dcm` 업로드 + 태그 자동 추출 + 원본 보관 (TEAM_CONTRACT §3.5)
   - 뷰어 Window/Level·3D는 **범위 밖** → 🟢 여유 작업
   - `src/dicom_io.py` 담당 **C**. 기존 담당은 변경 없음
   - **§3.1 이미지 규격과 §4 함수 시그니처는 그대로 → B·D는 영향 없음**
2. **`requirements.txt`** — `pydicom==3.0.2`, `pyarrow==19.0.1` 추가
   - `pyarrow`를 고정하지 않으면 `st.dataframe`·히스토그램에서 오류가 난다
3. **저장소 설정** (B) — Settings → General → Pull Requests에서 **squash/rebase 끄기**
   - 현재 squash가 켜져 있어 병합 시 커밋 SHA가 바뀐다 (`GIT_RULES.md` §8)

> 계약·규칙 변경 PR은 **영향받는 팀원 전원 Approve** 후 병합 (`GIT_RULES.md` §5).

### 회의 직후

- [ ] 문서 PR 병합 → 전원 `git pull origin main`
- [ ] 전원 `pip install -r requirements.txt` 다시 실행 (pydicom·pyarrow)
- [ ] 각자 담당 이슈 생성 (`[feat] ...`, 담당자 본인 지정)
- [ ] 전원 `python -m pytest -q` 통과 확인

---

## Day 1 — 11/27 (금) · 핵심 함수

| 담당 | 할 일 | 브랜치 |
|---|---|---|
| **C** | 🔴 **`download_lidc.py` 먼저** → 샘플 받아 팀에 공유 (다른 사람도 써야 한다) | `cheolu1025/dicom-samples` |
| **C** | 🔴 `dicom_io.is_dicom` / `read_tags` / `to_gray` + 테스트 | `cheolu1025/dicom-io` |
| **A** | 🔴 `storage.py` 로컬 구현, `save_case` / `load_image` / `load_case` (DICOM 분기 포함) | `arimlee270/save-load-case` |
| **B** | 🔴 `apply_clahe` + 테스트 | `rlawlqls/clahe` |
| **B** | 🔴 `get_roi_stats` + 테스트 | `rlawlqls/roi-stats` |
| **D** | 🔴 `apply_median` + 테스트 | `jw202421707/median` |
| **D** | 🔴 순수 함수 `check_transition` + 전수 테스트 | `jw202421707/workflow` |

**의존 관계:** A는 `dicom_io` stub에 의존하므로 C를 기다리지 않는다. 시그니처가 계약서 §4에
확정돼 있어 import만 하면 된다. 실제 동작 확인은 C의 PR 병합 후.

**✅ 완료 조건:** 각자 담당 함수 `pytest -q` 통과

---

## Day 2 — 11/28 (토) · 화면 + 나머지 함수

| 담당 | 할 일 |
|---|---|
| **A** | 🔴 `auth.login` / `get_user_role`, `search_cases`, `save_quality_check` |
| **A** | 🔴 로그인·케이스 목록·**영상 등록 화면** (`.dcm` 업로드 → 태그 자동 입력 → 저장) |
| **B** | 🔴 뷰어·ROI 탭 (`ui/viewer.py`) — 원본/결과 나란히, 알고리즘 3종 호출, 확대·이동·초기화 |
| **C** | 🔴 `apply_gaussian`, `check_quality` + 자동 점검 탭 (`ui/quality_panel.py`) |
| **D** | 🔴 `transition_case`, `assign_case`, `add_review_note`, `get_case_history` + 검토·이력 탭 |

각 탭은 `ui/style.py`의 공통 헬퍼로 디자인을 통일한다. `app.py`·`ui/style.py`는 A만 수정한다.

**✅ 완료 조건:** 개발 모드에서 각 탭이 뜨고, 자기 함수가 화면에서 한 번은 돌아간다

---

## 🟡 2차 통합 회의 — 11/29 (일)

**회의 목표: 등록 → 자동 점검 → 영상처리 → 검토 흐름을 한 번 완주한다.**

| 점검 항목 |
|---|
| [ ] `.dcm` 업로드 → 환자 ID·검사 종류·촬영 부위가 **자동으로 채워지는지** |
| [ ] 등록 직후 자동 품질 점검 결과가 화면에 뜨는지 |
| [ ] 뷰어에서 CLAHE / Gaussian / Median 각각 적용 → 원본과 나란히 비교 |
| [ ] ROI 선택 → 평균·분산·히스토그램 표시 |
| [ ] admin 배정 → reviewer 검토 시작 → 재검토 요청 → 완료 |
| [ ] 새로고침 후 원본·결과·기록이 그대로 조회되는지 |
| [ ] 권한 없는 요청이 거절되는지 |

**같이 확인:** 함수 시그니처 충돌, `st.session_state` 키 접두사 충돌, 탭 간 디자인 일관성,
PR·리뷰가 한 사람에게 몰리지 않았는지

**안 되는 것은 전부 목록으로 만든다.** 11/30에 그것만 고친다.

---

## Day 3 — 11/30 (월) · 🔴 개발 완료

| 담당 | 할 일 |
|---|---|
| **전체** | 2차 회의에서 나온 버그 수정 |
| **전체** | Definition of Done 셀프 점검 (TEAM_CONTRACT §8.4) |
| **전체** | 담당별 테스트 정상 1개 + 오류 1개 이상 확보 |
| **A** | 권한 필터 검증 (역할별로 보이는 화면이 다른지), 고아 파일 정리 |

**✅ 개발 완료 기준:** 로컬에서 전체 시나리오가 오류 없이 돌고, `python -m pytest -q` 전체 통과

---

## 12/1 이후 — 마무리

| 시기 | 할 일 |
|---|---|
| 12/1~12/3 | **A** JCloud 배포 (`APP_ENV=production` 확인, 영구 저장 확인) · 배포 주소에서 전체 시나리오 재실행 |
| 12/1~12/5 | **B/C/D** `docs/experiments/` 비교 실험 기록 (조건 3장 이상 × 파라미터 2개 이상) |
| 12/3~12/5 | **C** 임계값 보정·오탐/미탐 표, 특화 기능 검증 (점검 없이 / 있을 때 비교) |
| 12/6~12/8 | `test_integration.py`, 화면 캡처, README 완성 |
| 12/9~12/15 | 보고서 작성 (안내문 12쪽 필수 6항목), 개인 기여 표 |
| 12/16~12/17 | 시연 영상 3~5분 촬영 |
| 12/18 | 최종 커밋 → `v1.0.0` 태그 → LMS 제출 (전원) |

---

## 🟢 여유 작업 (개발 완료 후, 시간이 남으면)

| 작업 | 담당 | 비고 |
|---|---|---|
| 뷰어 밝기·대비 조절 (Window/Level) | B | 원본 `.dcm`을 보관하므로 나중에 붙여도 구조가 안 바뀐다. `load_image_raw` 추가 필요 (계약 변경) |
| 화면 디자인 조정 | A | `app.py`·`ui/style.py`만 바꾸면 되므로 팀원 코드에 영향 없음 |
| CT 3D·MPR | — | 범위 밖 (TEAM_CONTRACT §3.5). 과제 필수 아님 |
| `generate_samples.py` 나머지 6종 | C | 현재 `normal` 1종만 구현됨 |

---

## ⚠️ 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| **개발 기간이 실질 3일** | 🟢 여유 작업을 전부 12월로 미룬다. 과제 필수 구성(저장·조회·뷰어·알고리즘 3종·ROI·검토·특화)만 11/30까지 |
| **1차 회의에서 승인이 안 남** | 안건을 **회의 전날 공유**해 읽고 오게 한다. 승인이 밀리면 개발일이 하루 줄어든다 |
| **A 작업량 과다** (여전함) | 밀리면 `save_processing_run`/`get_processing_runs`를 B에게 넘기는 계약 변경 이슈를 올린다 |
| C에 DICOM 부담 집중 | C가 어려워하면 `dicom_io.py`만 B로 분리한다 (`download_lidc.py`는 C 유지) |
| DICOM 샘플 다운로드가 느림 | TCIA 서버가 요청받고 압축하므로 한 건당 10~40초. `download_lidc.py`가 이미 받은 케이스는 건너뛴다 |
| 임계값이 DICOM 변환본과 안 맞음 | 임계값 수치는 계약서가 아니라 `quality/thresholds.py`가 단일 출처 → C가 합의 없이 보정 (§4) |
| 샘플 영상 미커밋으로 테스트 실패 | 합성 영상은 `make_samples()`로 코드 생성, DICOM은 `download_lidc.py` (§3.4) |
| 서비스 계정 키 유출 | `.gitignore`의 `*firebase-adminsdk*.json`, 키는 개인 DM으로만 전달 |
| JCloud 배포 오류 | 12/1~12/3에 여유를 두고, 안 되면 12/4~12/8에 해결 |
| `app.py` / `ui/style.py` 충돌 | A만 수정. B/C/D는 자기 탭 파일과 자기 접두사 `st.session_state` 키만 |
| 병합 시 커밋 SHA가 바뀜 | 저장소 squash merge를 끈다 (1차 회의 안건 3) |

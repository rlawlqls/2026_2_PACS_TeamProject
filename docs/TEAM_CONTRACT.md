# 영상 품질 자동 점검 — 팀 공통 개발 규약 v2.0

> **목적:** A·B·C·D가 다른 파일에서 동시에 개발해도, 마지막에 `app.py`에서 곧바로 연결되도록 **함수 계약(API), 데이터 구조, 화면·권한·업무 상태, 저장, 검증, Git 규칙**을 고정한다.  
> **적용 대상:** 초급프로젝트 PBL 교육용 웹 PACS / 팀 4명 / Python + Streamlit + Firebase Authentication + Cloud Firestore + JCloud  
> **문서 상태:** **v2.0 확정안**. 과제 지시서에 적힌 내용은 `[과제 필수]`, 기획안에 적힌 내용은 `[기획안]`, 본 문서에서 인터페이스 충돌을 막기 위해 새로 정한 세부사항은 `[팀 합의안]`으로 구분한다. **코딩 시작 전에 네 명 모두 이 문서를 읽고 Issue #0에 동의 댓글을 남긴다.**  
> **Git 규칙:** 브랜치·커밋·이슈·PR·리뷰 규칙은 [`docs/GIT_RULES.md`](GIT_RULES.md)가 최상위 규칙이다. 이 문서와 다르면 GIT_RULES를 따른다.

---

## 0. 개발 전 결정표 — 전항목 확정

| 항목 | 확정 결정 | 근거 |
|---|---|---|
| 백엔드/화면 | Python 3.11 + Streamlit 1.32 단일 앱 | 안정 버전, Firebase SDK 호환 |
| 인증/DB/배포 | Firebase Authentication / Cloud Firestore / JCloud `[과제 필수]` | 변경 불가 |
| 실제 영상 저장 | **Firebase Storage** 무료 플랜(5GB); 원본: `originals/{case_id}/{image_id}.png`; 처리 결과: `processed/{case_id}/{run_id}.png` | 무료 한도 내 시연 충분 |
| 영상 입력 | PNG/JPG/JPEG, **8-bit grayscale `np.ndarray`** (H,W) uint8; 10MB 이하; DICOM 범위 밖 `[팀 합의안]` | 확정 |
| 원본 보관 | 원본 파일 절대 덮어쓰기 금지 `[과제 필수]` | 변경 불가 |
| 필수 영상처리 3종 | B: CLAHE / C: Gaussian / D: Median `[팀 합의안]` | 확정 |
| 화질 특화 기능 | C가 밝기·대비·흐림 점수 계산, A 등록 시 실행, A 결과 표시, D 재검토로 연결 | 확정 |
| UI↔기능 연결 | **A가 `app.py` UI 전체 틀 담당**; B/C/D는 함수(로직)만 구현해서 넘김; A가 함수를 화면에 연결; UI 코드가 Firestore에 직접 쓰지 않기 | 통합 담당 A |
| UI 개발 방식 | A가 공통 레이아웃·탭 구조·스타일 먼저 잡기; B/C/D는 담당 탭 내부 UI를 `app.py`에 추가; `app.py` 탭 구조는 A만 수정 | A Day 1~2 완료 후 |
| ID 형식 | `case_id = "case_" + uuid4().hex`, `image_id = "img_" + uuid4().hex`, `run_id = "run_" + uuid4().hex`, `check_id = "qc_" + uuid4().hex` | 확정 |
| 저장 시간 | 모든 Firestore Timestamp는 **UTC 기준 서버 시간** (`SERVER_TIMESTAMP`); 화면 표시만 KST 변환 | 확정 |
| 검토 상태 | `registered` → `assigned` → `reviewing` → `completed`; 예외 `needs_review` | 확정 |
| 점검 결과 | `pass` / `needs_check`; 저장 계층 오류 시 `error`; **의학적 적합 판정 아님** | 확정 |
| 코드 리뷰 | 작업당 Issue → `아이디/기능명` 브랜치 → 커밋 → PR → **코드 PR은 다른 팀원 1명 리뷰** → 병합 (상세: `docs/GIT_RULES.md`) | `[과제 필수]` |
| Python 환경 | Python 3.11.x, venv 사용 | 확정 |
| 의존성 버전 | `requirements.txt` 버전 고정 (아래 §12 참고) | 확정 |

**참고:** 점수나 품질 경계값은 과제 PDF에 정해져 있지 않다. 아래 수치는 **교육용 시연을 위한 임시 기본값**이며 실제 샘플로 조정 후 근거·한계를 보고서에 기록한다. `pass`는 **팀 기준상 경고 없음**만 뜻한다.

---

## 1. 공통 아키텍처와 실행 흐름

```text
[Streamlit 브라우저]
   ├─ Firebase 로그인/로그아웃 (Auth)
   └─ app.py  ← A가 전체 UI 틀 담당 (탭 구조, 공통 스타일, 함수 호출)
       ├─ A: services/cases.py, services/storage.py, services/auth.py
       │    ├─ Firebase Storage: 이미지 바이너리 원본/결과
       │    └─ Cloud Firestore: 메타데이터/업무/처리 기록
       ├─ B: processing/clahe.py, processing/roi.py   ← 함수만; UI는 A가 연결
       ├─ C: processing/gaussian.py, quality/checker.py  ← 함수만; UI는 A가 연결
       └─ D: processing/median.py, services/workflow.py, services/reports.py  ← 함수만; UI는 A가 연결
```

**UI 개발 원칙:**
- A가 `app.py`에 탭 구조와 공통 스타일을 먼저 만든다 (Day 1~2).
- B/C/D는 각자 담당 탭 내부에 UI 요소를 추가한다 (Day 3~4).
- `app.py`의 탭 구조·공통 레이아웃은 **A만 수정**; B/C/D가 건드려야 할 경우 PR로 A에게 요청.
- B/C/D의 함수는 Streamlit을 직접 호출하지 않는다 (순수 로직만).

### 실제 정상 시나리오 (팀 전체가 동일한 순서로 구현)

1. **로그인**: Firebase Auth ID token을 확인하고 역할 `registrar` / `reviewer` / `admin`을 읽는다.
2. **등록**: 등록 담당자가 모의 케이스의 `metadata`와 PNG/JPEG를 업로드 → A의 `save_case`가 원본을 영구 저장 → `case_id`, `image_id` 반환.
3. **자동 화질 점검**: `load_image(image_id)` → C의 `check_quality(gray, thresholds)` → 점검 결과를 `quality_checks`에 저장하고 케이스에 최신 점검 상태를 연결. **점검 실패해도 원본 등록은 보존**하고 UI에 오류를 표시.
4. **조회/뷰어**: 검색·필터로 케이스 선택 → 원본 표시, 줌/이동/초기화, 알고리즘 처리 전후 비교.
5. **ROI**: 선택한 사각형 좌표를 B의 `get_roi_stats`로 전달 → 통계·히스토그램 표시. **통계 대상이 원본인지 결과인지 UI에 명확히 표시**.
6. **검토 업무**: 배정 후 검토자가 점검 사유를 보고, 처리 결과와 메모를 기록하고 `needs_review` 또는 `completed`로 전환.
7. **재조회**: 새로고침/앱 재시작 후 원본, 결과, 알고리즘·설정, 점검·메모·상태 이력이 동일하게 조회됨.

**중요한 분리:** (a) CLAHE·Gaussian·Median은 **사용자가 선택하는 영상처리 알고리즘 3종**, (b) 밝기·대비·Laplacian 분산은 **자동 품질 점검을 위한 측정 지표**이다. 지표 3개를 필수 영상처리 알고리즘 3종으로 잘못 계산하지 않는다.

---

## 2. 폴더 및 파일 소유권 (오늘 그대로 생성)

```text
pacs-quality-check/
├── app.py                      # A: UI 통합(각 팀원 UI 모듈 임포트)
├── requirements.txt            # 공통 의존성 (버전 고정 — §12 참고)
├── .gitignore
├── .env.example                # 변수 이름만; 실제 비밀정보 금지
├── README.md
├── docs/
│   ├── TEAM_CONTRACT.md        # 이 문서: 계약 바뀌면 PR 필수
│   ├── TEST_PLAN.md
│   └── assets/                 # 보고서용 다이어그램/안전한 샘플
├── src/
│   ├── models.py               # A 작성, 전원 리뷰: TypedDict/데이터 모델
│   ├── config.py               # A: 설정, 임계값 로드
│   ├── errors.py               # A: 공통 예외
│   ├── services/
│   │   ├── auth.py             # A: 세션, 역할 확인
│   │   ├── storage.py          # A: Storage 읽기/쓰기
│   │   ├── cases.py            # A: save/load/search
│   │   ├── quality_history.py  # C 구현 + A 저장 API 조율
│   │   ├── workflow.py         # D: 배정/상태 전환
│   │   └── reports.py          # D: 메모/리포트/이력
│   ├── processing/
│   │   ├── clahe.py            # B
│   │   ├── roi.py              # B
│   │   ├── gaussian.py         # C
│   │   └── median.py           # D
│   ├── quality/
│   │   └── checker.py          # C: 화질 판정 로직
│   └── ui/
│       ├── viewer.py           # A: 뷰어·ROI 화면 (B 함수 호출)
│       ├── quality_panel.py    # A: 자동 점검 결과 화면 (C 함수 호출)
│       └── workflow_panel.py   # A: 검토·이력 화면 (D 함수 호출)
├── tests/
│   ├── test_processing.py      # B/C/D 공동, 각자 자기 함수 검사
│   ├── test_quality.py         # C
│   ├── test_cases.py           # A
│   ├── test_workflow.py        # D
│   └── test_integration.py     # A 총괄, 전원 참여
└── sample_data/
    ├── README.md               # 공개·가상 영상 출처/라이선스; 민감정보 금지
    ├── normal.png
    ├── dark.png
    ├── bright.png
    ├── low_contrast.png
    ├── blur.png
    ├── gaussian_noise.png
    ├── salt_pepper.png
    └── invalid.txt
```

**규칙:** 다른 사람 소유 파일을 변경해야 하면 PR 설명에 이유와 영향을 기록하고 해당 담당자에게 알린다. 공통 스키마(`models.py`)와 계약 문서는 어느 한 사람의 독단으로 바꾸지 않는다.

---

## 3. 팀원 간 공유 데이터 형식 — 바꾸지 말 것

### 3.1 공통 Python 이미지 규격 `[팀 합의안]`

```python
import numpy as np

# 함수에 전달하는 gray의 규격:
# type: numpy.ndarray
# shape: (height, width)  # 2차원만 허용
# dtype: np.uint8         # 0~255
# 0 = 검정, 255 = 흰색
# 1채널 grayscale; RGB/BGR은 파일을 읽을 때 한 번만 변환
# 최소 크기: 32 x 32 픽셀 (팀 시연 가이드)
```

- 함수의 결과 영상도 **입력과 같은 `(H,W), uint8`**, 특별히 다른 출력 형식을 정의한 경우에만 예외.
- 원본 배열 수정 금지: `out = gray.copy()` 또는 OpenCV가 새 배열을 반환하도록 구현.
- 영상 업로드 제한: **10 MB 이하**, 확장자와 실제 디코딩 결과 동시 검사; 잘못된 파일이면 명확한 오류.
- **이미지 방향:** Python/OpenCV 배열의 좌표 원점은 **왼쪽 위 `(x=0,y=0)`**, `x`는 오른쪽, `y`는 아래쪽. Streamlit UI 좌표를 원본 해상도로 역변환해 ROI에 전달.
- 히스토그램은 **256개 bin**으로 고정, 결과가 JSON/Firestore에 저장될 때는 `list[int]`로 바꾼다.
- `np.ndarray`와 바이너리는 **Firestore에 직접 저장하지 않음**.

### 3.2 ID, 타임스탬프, JSON 저장 규칙

| 키 | 자료형 | 생성 방법 | 예시 |
|---|---|---|---|
| `case_id` | `str` | `"case_" + uuid.uuid4().hex` | `case_7b1c3f...` |
| `image_id` | `str` | `"img_" + uuid.uuid4().hex` | `img_8d02a1...` |
| `run_id` | `str` | `"run_" + uuid.uuid4().hex` | `run_61ab9c...` |
| `check_id` | `str` | `"qc_" + uuid.uuid4().hex` | `qc_a94e7b...` |
| `note_id` | `str` | `"note_" + uuid.uuid4().hex` | `note_3c18...` |
| `event_id` | `str` | `"evt_" + uuid.uuid4().hex` | `evt_f20d...` |
| `uid` | `str` | Firebase UID (검증된 세션에서) | Firebase 자동 생성 |
| `created_at`, `updated_at` | Firestore SERVER_TIMESTAMP (UTC) | `firestore.SERVER_TIMESTAMP` | 자동 |
| 경로 | `str` | `originals/{case_id}/{image_id}.png` | 이미지 파일은 Storage, 경로는 Firestore |
| `schema_version` | `int` | 상수 `1` | `1` |

**UUID 생성 표준 코드:**
```python
import uuid

def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex}"

# 사용 예
case_id  = new_id("case_")   # "case_7b1c3f8a..."
image_id = new_id("img_")    # "img_8d02a1..."
run_id   = new_id("run_")    # "run_61ab9c..."
check_id = new_id("qc_")     # "qc_a94e7b..."
```

### 3.3 `metadata` 표준 — A에 넘기는 입력

```python
metadata = {
    "case_label": "DEMO-001",          # 화면용 모의 케이스 ID, 필수
    "exam_type": "X-ray",             # X-ray / CT / MRI / Other (시연용 분류)
    "description": "모의 흉부 영상",     # 선택, 없으면 ""
    "registered_by": "firebase-uid",  # 로그인 사용자 UID, 서버에서 검증
}
```

- 환자 실명·주민번호 등 **실제 개인정보는 금지**. `case_label`은 화면 표시용이며 고유한 DB 키가 아님.
- 파일명·길이·크기·등록시각은 클라이언트를 신뢰하지 않고 A가 실제 파일에서 생성·검증한다.
- `image_bytes`에는 **PNG/JPEG 파일 자체의 bytes**를 넘김. `np.ndarray.tobytes()`와 혼동하지 않는다.

---

## 4. 팀원 간 함수 계약(API) — 이 시그니처로 구현

> 함수에 변경이 필요하면 **먼저 `docs/TEAM_CONTRACT.md` 수정 PR → 전원 확인 → 실제 코드 변경**. 아래 서명에서 `...`는 사용하지 않고 명시된 이름을 쓴다. 기본 설정값도 문서와 코드가 동일해야 한다.

### A: 케이스·영상 저장/조회 (공통 기반)

```python
def save_case(metadata: dict, image_bytes: bytes) -> tuple[str, str]:
    """원본을 Firebase Storage에 보존하고 Firestore 케이스·영상 생성.
    반환: (case_id, image_id); 실패 시 AppError 계열 예외.
    권한: registrar 또는 admin.
    Storage 업로드 성공 후 Firestore 기록 실패 시:
      - Storage 파일 삭제 시도 후 StorageError 발생
      - 삭제 실패 시 고아 파일 경로를 로그에 기록하고 StorageError 발생
    """

def load_case(case_id: str) -> dict:
    """케이스 메타데이터/상태/최근 점검 요약 포함 dict; 없으면 NotFoundError."""

def load_image(image_id: str) -> np.ndarray:
    """Storage 파일을 디코딩하여 (H,W) uint8 grayscale로 반환."""

def search_cases(query: str = "", status: str | None = None) -> list[dict]:
    """권한 범위 내 케이스 목록, 등록일 내림차순.
    registrar: 본인 등록 케이스만
    reviewer: 본인 배정 케이스만
    admin: 전체
    """

def save_processing_run(image_id: str, algorithm: str, params: dict,
                        processed_gray: np.ndarray, actor_uid: str,
                        roi: dict | None = None) -> str:
    """결과 파일 Storage 저장 + processing_runs Firestore 기록; 반환: run_id."""

def get_processing_runs(image_id: str) -> list[dict]:
    """run 이력을 최신순 반환."""

def save_quality_check(image_id: str, result: dict, actor_uid: str | None = None) -> str:
    """C의 result를 검증하고 Firestore quality_checks에 저장.
    cases/{case_id}.latest_check_id, latest_quality_status도 동시 업데이트.
    반환: check_id.
    """
```

**A와 C의 조율:** C는 `check_quality()`에서 **순수 계산만 수행**(Firestore 직접 접근 금지), A가 `save_quality_check()`로 영구 저장한다. 화질 측정으로 원본 저장 전체가 실패하게 만들지 않는다.

**고아 파일 정리 정책:**
- Storage 업로드 성공 후 Firestore 기록 실패 → Storage 파일 즉시 삭제 시도
- 삭제도 실패 → 고아 경로를 `orphan_files` 로컬 로그에 기록 (민감정보 제외)
- 재시작 시 `orphan_files` 로그 확인 후 수동 삭제

### B: CLAHE + ROI

```python
def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0,
                tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """uint8 grayscale 반환. clip_limit > 0, tile_grid_size 각 정수 >= 1."""

def get_roi_stats(gray: np.ndarray, roi: dict) -> dict:
    """roi={'x':int,'y':int,'width':int,'height':int};
    반환 {'roi': roi, 'mean':float, 'variance':float,
          'std':float, 'min':int, 'max':int,
          'histogram':list[int], 'pixel_count':int}.
    유효하지 않거나 영역 밖이면 ValidationError.
    """
```

- ROI 경계는 반열림 구간 `gray[y:y+height, x:x+width]`; `width > 0`, `height > 0`, 영상 범위 이내.
- ROI 통계는 **모집단 분산(`ddof=0`)**으로 통일; 평균/분산은 픽셀값 그대로 계산.
- CLAHE는 OpenCV `cv2.createCLAHE(clipLimit=..., tileGridSize=...)` 이용.

### C: Gaussian + 품질 자동 점검

```python
def apply_gaussian(gray: np.ndarray, kernel_size: int = 5,
                   sigma: float = 0.0) -> np.ndarray:
    """kernel_size는 양의 홀수, sigma >= 0, uint8 grayscale 반환."""

def check_quality(gray: np.ndarray, thresholds: dict) -> dict:
    """밝기/대비/흐림 기초 지표 측정 후 팀 규칙에 따라 판정.
    결과는 아래 표준 결과 dict 형식을 정확히 따름.
    외부 DB/API 쓰기 없음. 재현 가능해야 함.
    """
```

#### `thresholds` 표준 (임시 기본값; 실제 샘플 확인 후 보정)

```python
# src/config.py에 DEFAULT_THRESHOLDS로 정의
DEFAULT_THRESHOLDS = {
    "brightness_min": 50.0,       # mean < 50 → too_dark
    "brightness_max": 205.0,      # mean > 205 → too_bright
    "contrast_std_min": 35.0,     # std < 35 → low_contrast
    "laplacian_var_min": 80.0,    # Laplacian variance < 80 → possibly_blurry
    "version": "demo-v1",
}
```

**구현 식:** `mean = np.mean(gray)`, `std = np.std(gray)`, `laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()`. 단위는 **8-bit grayscale 기준**.

#### `check_quality` 반환값 표준

```python
{
    "status": "needs_check",     # 'pass' / 'needs_check'
    "metrics": {
        "brightness_mean": 42.8,
        "contrast_std": 29.4,
        "laplacian_variance": 50.2,
    },
    "reasons": ["too_dark", "low_contrast", "possibly_blurry"],
    "thresholds": {
        "brightness_min": 50.0, "brightness_max": 205.0,
        "contrast_std_min": 35.0, "laplacian_var_min": 80.0,
        "version": "demo-v1"
    },
    "checker_version": "1.0.0",
}
```

- `reasons` 순서: **`too_dark`/`too_bright` → `low_contrast` → `possibly_blurry`**. 경고 없으면 빈 리스트 + `pass`.
- 표시 메시지는 UI에서 코드→한글 매핑: `too_dark`=어두움, `too_bright`=너무 밝음, `low_contrast`=낮은 대비, `possibly_blurry`=흐림 의심.
- `status`가 `pass`여도 **진단 가능/재촬영 불필요를 보장하지 않음**.

### D: Median + 업무 상태 전환

```python
def apply_median(gray: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """kernel_size는 3 이상의 홀수. uint8 grayscale 반환."""

def transition_case(case_id: str, action: str,
                    actor_uid: str, note: str = "") -> dict:
    """로그인 사용자 역할·담당자·현재 상태/허용 전이 검사 후
    Firestore 트랜잭션으로 상태 및 event 이력 저장.
    반환: 변경 후 케이스 dict; 실패 시 PermissionDeniedError 또는 StateConflictError.
    """

def assign_case(case_id: str, reviewer_uid: str, actor_uid: str) -> dict:
    """admin만 배정 가능; registered → assigned 처리 및 이벤트 저장."""

def add_review_note(case_id: str, image_id: str,
                    actor_uid: str, content: str,
                    run_id: str | None = None) -> str:
    """메모 저장; 반환 note_id. 빈 메모 금지, 대상 케이스와 이미지 관계 확인."""

def get_case_history(case_id: str) -> list[dict]:
    """업무 이벤트/메모/처리 기록을 조회 가능한 형태로 반환."""
```

**호출 예:** `transition_case(case_id, "start_review", uid)`, `transition_case(case_id, "request_recheck", uid, "낮은 대비 확인 요청")`.

### 공통 예외 계약

```python
# src/errors.py
class AppError(Exception): ...
class ValidationError(AppError): ...
class NotFoundError(AppError): ...
class PermissionDeniedError(AppError): ...
class StateConflictError(AppError): ...
class StorageError(AppError): ...
```

- 처리 함수 잘못된 파라미터 → `ValidationError`
- 이미지/케이스 없음 → `NotFoundError`
- 권한 실패 → `PermissionDeniedError`
- Storage/DB 오류 → `StorageError`
- UI는 `try/except AppError`로 사용자에게 한국어 안내; 예상 못 한 오류는 **로그에 상세 기록, UI에는 민감정보 없는 일반 메시지**.
- Firebase 자격증명, 토큰, 환경변수 값은 로그에 출력 금지.

---

## 5. Cloud Firestore 공통 스키마 v1.0

Firestore는 **업무 데이터**, Storage는 **실제 영상 파일**.

| 컬렉션/문서 | 주요 필드 | 작성/변경 담당 |
|---|---|---|
| `users/{uid}` | `display_name`, `role` (`registrar`/`reviewer`/`admin`), `active`, `created_at` | A |
| `cases/{case_id}` | `schema_version`, `case_label`, `exam_type`, `description`, `status`, `assigned_reviewer_uid`, `registered_by`, `created_at`, `updated_at`, `latest_check_id`, `latest_quality_status` | A 작성, D 상태 변경 |
| `images/{image_id}` | `case_id`, `kind` (`original`/`processed`), `parent_image_id`, `storage_path`, `mime_type`, `width`, `height`, `byte_size`, `uploaded_by`, `created_at` | A |
| `processing_runs/{run_id}` | `case_id`, `source_image_id`, `result_image_id`, `algorithm`, `algorithm_version`, `params`, `roi`, `actor_uid`, `created_at` | A 저장, B/C/D 값 공급 |
| `quality_checks/{check_id}` | `case_id`, `image_id`, `status`, `metrics`, `reasons`, `thresholds`, `checker_version`, `actor_uid`, `created_at` | C 계산, A 저장 |
| `review_notes/{note_id}` | `case_id`, `image_id`, `run_id`, `content`, `author_uid`, `created_at` | D |
| `case_events/{event_id}` | `case_id`, `action`, `from_status`, `to_status`, `actor_uid`, `note`, `created_at` | D |
| `reports/{report_id}` | `case_id`, `summary`, `author_uid`, `created_at`, `linked_run_ids`, `linked_check_ids` | D |

**예시 케이스 문서**

```json
{
  "schema_version": 1,
  "case_label": "DEMO-001",
  "exam_type": "X-ray",
  "description": "모의 흉부 영상",
  "status": "registered",
  "assigned_reviewer_uid": null,
  "registered_by": "uid_registrar_1",
  "latest_check_id": "qc_abc123",
  "latest_quality_status": "needs_check"
}
```

- **`latest_quality_status`와 `status`는 서로 다른 값.** `status`는 *업무 진행 상황*, `latest_quality_status`는 *자동 화질 점검 결과*. 절대 혼용하지 않는다.
- 컬렉션 간 참조는 문자열 ID. v1에서는 UI에서 하드 삭제 기능 제공하지 않음.
- 원본 Storage 경로: `originals/{case_id}/{image_id}.png`; 처리 결과: `processed/{case_id}/{run_id}.png`.
- **보안 주의:** Python Firebase Admin SDK는 Firestore Security Rules를 우회한다. Streamlit 서버 측 모든 읽기/쓰기 함수에서 확인된 로그인 사용자 UID와 DB 역할을 직접 검사해야 한다.

---

## 6. 역할·권한·상태전이 규칙

### 6.1 기본 권한 매트릭스

| 작업 | `registrar` | `reviewer` (본인 배정 건) | `admin` |
|---|:---:|:---:|:---:|
| 로그인 후 허용 목록 조회 | O | O | O |
| 케이스/원본 등록 | O | X | O |
| 영상 열람/처리·ROI | O (본인 등록 건) | O | O |
| 검토자 배정 | X | X | O |
| 검토 시작·완료 | X | O | O |
| 재검토 요청 | X | O | O |
| 메모·리포트 | X | O | O |
| 계정 역할 변경 | X | X | O |

**권한 범위:** `registrar`는 자신이 등록한 케이스, `reviewer`는 자신에게 배정된 케이스만 조회. `admin`은 전부. 검색·파일 다운로드·메모 조회에서도 동일한 필터를 적용한다.

### 6.2 상태 전이 표

| 현재 `status` | `action` | 다음 `status` | 실행자 / 조건 |
|---|---|---|---|
| `registered` | `assign_case` | `assigned` | admin; 담당 reviewer 지정 |
| `assigned` | `start_review` | `reviewing` | 배정 reviewer 또는 admin |
| `reviewing` | `request_recheck` | `needs_review` | 배정 reviewer/admin; **사유(note) 필수** |
| `needs_review` | `resume_review` | `reviewing` | 배정 reviewer/admin; 확인 후 재검토 |
| `reviewing` | `complete_review` | `completed` | 배정 reviewer/admin; 메모 또는 리포트 1개 이상 |

- 위에 없는 전이는 `StateConflictError`.
- **`needs_review`는 사람이 재검토를 요청한 업무 상태**이며 C의 `needs_check`(자동 경고)와 다름.
- 상태 변경은 **DB 트랜잭션**으로 현재 상태 확인 + 사건 기록을 하나의 논리 작업으로 묶는다.

---

## 7. 화면·값 전달 규칙

| 화면(탭) | UI 담당 | 함수 제공 | 호출 함수 | 반드시 보여줄 정보 |
|---|---|---|---|---|
| 로그인 | **A** | A | `auth` | 로그인/로그아웃, 역할, 권한 오류 |
| 케이스 목록 | **A** | A | `search_cases` | 케이스 ID, 검사 종류, 담당자, 업무 상태, 자동 점검 상태 |
| 영상 등록 | **A** | A | `save_case` → `load_image` → `check_quality` → `save_quality_check` | 업로드 결과, 자동 점검 사유, 검사 실패 안내 |
| 영상 뷰어 | **A** | B | `load_image`, `apply_clahe/gaussian/median`, `save_processing_run` | 원본/결과 나란히, 알고리즘 선택, 처리 설정, 확대·축소/이동/초기화 |
| ROI 분석 | **A** | B | `get_roi_stats` | ROI 좌표·크기, 평균·분산·히스토그램 |
| 자동 점검 결과 | **A** | C | `check_quality`, `save_quality_check` | 점수 3종, 적용 임계값, 경고 사유, 교육용 문구 |
| 검토·재검토 | **A** | D | `assign_case`, `transition_case`, `add_review_note` | 상태 변경 버튼, 사유, 담당자·이력 |
| 이력·리포트 | **A** | D | `get_case_history`, `get_processing_runs` | 작성자, 설정, 실행/저장 시간, 결과 재열기 |

> **UI 담당은 전부 A.** B/C/D는 함수만 완성해서 넘기고, A가 각 탭에 연결한다.  
> B/C/D가 담당 탭 내부 UI를 직접 추가할 때는 A가 만든 공통 스타일을 그대로 사용하고, `app.py` 탭 구조는 건드리지 않는다.

- Streamlit `st.session_state` 키 접두사: `auth_*`, `selected_case_id`, `selected_image_id`, `viewer_*`, `roi_*`, `quality_*`, `workflow_*`.
- 처리 함수가 버튼 UI를 그리거나 Streamlit 상태를 직접 바꾸지 않도록 분리.
- 영상 선택이 달라지면 이전 ROI·처리 결과·경고 표시 캐시를 초기화.

---

## 8. 테스트 데이터와 완료 기준

### 8.1 샘플 이미지 — 생성 담당 C, Day 0까지

| 샘플명 | 생성 방법 | 기대 검증 |
|---|---|---|
| `normal.png` | 128x128 uint8 평균밝기 120, std 50 무작위 | 임계값 조정 시 `pass` |
| `dark.png` | normal에서 `np.clip(gray * 0.2, 0, 255)` | `too_dark` |
| `bright.png` | normal에서 `np.clip(gray * 1.8 + 30, 0, 255)` | `too_bright` |
| `low_contrast.png` | `cv2.normalize(gray, None, 100, 150, cv2.NORM_MINMAX)` | `low_contrast` |
| `blur.png` | `cv2.GaussianBlur(gray, (21,21), 10)` | `possibly_blurry` |
| `gaussian_noise.png` | normal에 `np.random.normal(0, 25, shape)` 추가 | Gaussian 처리 전후 비교 |
| `salt_pepper.png` | normal에 소금·후추 잡음 추가 | Median 처리 전후 비교 |
| `invalid.txt` | 텍스트 파일 | 업로드 거절 |

**샘플 생성 스크립트:** `sample_data/generate_samples.py` — C가 작성, `sample_data/`에 저장.  
저작권 없음(직접 생성), `sample_data/README.md`에 생성 방법·버전 기록.

### 8.2 담당별 최소 단위 테스트

- **A:** 정상 PNG/JPEG 업로드·재열기, 파일 깨짐/크기 초과/권한 실패, DB 저장 실패 시 고아 파일 정리, 새로고침/재시작 후 재조회.
- **B:** CLAHE 결과 shape/dtype 유지, 입력 배열 원본 불변, ROI 평균·분산·256-bin 합계 `== pixel_count`, 경계 바깥 ROI 오류.
- **C:** Gaussian 홀수 커널 제약, 인위적 밝기·대비·흐림 점검, 경고 사유·순서와 threshold 버전 고정, 원본 불변.
- **D:** Median 커널 오류, 허용/금지 상태 전이, 배정되지 않은 reviewer 거절, 재검토 사유 없는 요청 거절, 중복 상태변경과 이력 확인.
- **전원:** 등록→자동 점검→영상처리 저장→ROI→메모/재검토→완료→재조회 통합 시나리오, JCloud 배포 주소에서 재실행.

### 8.3 테스트 증빙 표준

| 필드 | 예시 |
|---|---|
| 테스트 ID | `TC-QC-03` |
| 준비 상태 | `blur.png`, threshold `demo-v1` |
| 수행 | 업로드 후 자동 품질 검사 |
| 예상 | `possibly_blurry` 경고 |
| 실제 | 점수, 사유, 화면 캡처 |
| 결과 | PASS / FAIL / 보류 |
| 수행자·일시·관련 커밋 | C / 날짜 / SHA |

### 8.4 Definition of Done

- [ ] 기능이 명시한 입력/반환·예외 계약을 지킴
- [ ] 최소 정상 1개 + 오류 1개 테스트 존재, 실행 명령과 결과를 PR에 기록
- [ ] Firestore 데이터 구조/Storage 원본 보존 규칙 유지
- [ ] 권한·상태변경이 있는 기능이면 부정 권한/잘못된 상태를 거절함
- [ ] 새로고침/앱 재시작 후 관련 데이터 재조회 확인
- [ ] 담당 코드/설정/실험 한계 설명을 README 또는 docs에 추가
- [ ] 본인 브랜치 커밋 + PR + 다른 팀원의 리뷰 후 병합

---

## 9. Git/GitHub

> `[과제 필수]` **한 저장소**에서 전원 본인 계정으로 Issue·브랜치·커밋·PR·리뷰 기록을 남겨야 한다.
> 브랜치·커밋·이슈·PR·리뷰·충돌 해결·배포 규칙은 **[`docs/GIT_RULES.md`](GIT_RULES.md)**를 따른다.

### 9.1 처음 한 번 하는 개발 환경 설정

```bash
git clone https://github.com/rlawlqls/2026_2_PACS_TeamProject.git
cd 2026_2_PACS_TeamProject
git config user.name "각자_GitHub_표시이름"
git config user.email "각자_GitHub에_연결된_이메일"
git config pull.rebase false
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**PowerShell에서 실행 정책 오류가 나면** `.venv\Scripts\python.exe -m pip install -r requirements.txt`처럼 가상환경 Python 경로를 직접 호출해도 된다.

### 9.2 `.gitignore` 필수 항목

```gitignore
.venv/
__pycache__/
.pytest_cache/
.env
.env.*
!.env.example
.streamlit/secrets.toml
*serviceAccount*.json
firebase-adminsdk*.json
*.log
.DS_Store
sample_data/*.png
sample_data/*.jpg
!sample_data/README.md
```

---

## 10. Firebase 초기 설정 가이드 (A 담당, Day 0)

### 10.1 Firebase 프로젝트 생성

1. [Firebase Console](https://console.firebase.google.com) → **프로젝트 추가** → 이름: `pacs-quality-check`
2. **Authentication** → 시작하기 → **이메일/비밀번호** 로그인 방식 사용 설정
3. **Firestore Database** → 시작하기 → **테스트 모드** (초기 개발용; 배포 전 보안 규칙 적용)
4. **Storage** → 시작하기 → 무료 플랜(5GB) 확인 → 기본 버킷 생성
5. **프로젝트 설정** → 서비스 계정 → Python용 Admin SDK → **새 비공개 키 생성**
   - 다운로드된 JSON 파일명: `firebase-adminsdk-*.json`
   - `.gitignore`에 포함되어 있으므로 절대 커밋하지 않음

### 10.2 역할별 테스트 계정 생성 (A가 Firebase Console에서 직접 생성)

| 계정 | 이메일 | 역할 | 용도 |
|---|---|---|---|
| 등록 담당자 | `registrar@pacs.test` | `registrar` | 케이스 등록 테스트 |
| 검토자 | `reviewer@pacs.test` | `reviewer` | 검토 업무 테스트 |
| 관리자 | `admin@pacs.test` | `admin` | 전체 기능 테스트 |

**역할 등록 방법:** Firebase Console → Firestore → `users` 컬렉션 → 각 UID로 문서 생성:
```json
{
  "display_name": "테스트 등록자",
  "role": "registrar",
  "active": true,
  "created_at": "서버 타임스탬프"
}
```

### 10.3 환경변수 설정

`.env.example` (커밋 가능):
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-adminsdk-*.json
APP_ENV=development
```

`.env` (커밋 금지, `.gitignore` 포함):
```
FIREBASE_PROJECT_ID=pacs-quality-check
FIREBASE_STORAGE_BUCKET=pacs-quality-check.appspot.com
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-adminsdk-xxxxx.json
APP_ENV=development
```

### 10.4 Storage 접근 경로 확정

```
Firebase Storage 버킷 구조:
├── originals/
│   └── {case_id}/
│       └── {image_id}.png        # 원본 (절대 덮어쓰지 않음)
└── processed/
    └── {case_id}/
        └── {run_id}.png          # 처리 결과
```

**Storage 접근 코드 패턴 (A가 `services/storage.py`에 구현):**
```python
from firebase_admin import storage

def upload_image(path: str, image_bytes: bytes, content_type: str = "image/png") -> str:
    bucket = storage.bucket()
    blob = bucket.blob(path)
    blob.upload_from_string(image_bytes, content_type=content_type)
    return path  # Firestore에 저장할 경로 반환

def download_image(path: str) -> bytes:
    bucket = storage.bucket()
    blob = bucket.blob(path)
    return blob.download_as_bytes()
```

---

## 11. JCloud 배포 가이드 (A 담당, Day 5~)

### 11.1 배포 준비

```bash
# Streamlit 앱 로컬 실행 확인
streamlit run app.py

# 의존성 최신화
pip freeze > requirements.txt
```

### 11.2 JCloud 배포 절차

> JCloud 접속 주소와 계정 정보는 과제 지시서 또는 교수님 안내에 따름.

1. JCloud 대시보드 로그인
2. 새 앱 생성 → Python/Streamlit 선택
3. GitHub 저장소 연결 (main 브랜치)
4. 환경변수 설정 (`.env` 내용을 JCloud 비밀 환경변수로 등록)
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_STORAGE_BUCKET`
   - `FIREBASE_SERVICE_ACCOUNT_JSON` (JSON 내용을 문자열로)
5. 배포 실행 → 접속 URL 확인
6. 역할별 테스트 계정으로 전체 시나리오 재실행

### 11.3 배포 환경에서 서비스 계정 처리

JCloud에서는 파일 경로 대신 **환경변수로 JSON 내용** 전달:
```python
# src/services/auth.py
import json, os
import firebase_admin
from firebase_admin import credentials

def init_firebase():
    if not firebase_admin._apps:
        json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if json_str:
            cred = credentials.Certificate(json.loads(json_str))
        else:
            path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
            cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred, {
            "storageBucket": os.environ["FIREBASE_STORAGE_BUCKET"]
        })
```

---

## 12. `requirements.txt` 버전 고정

```
# requirements.txt — 버전 변경 시 전원 합의 필요
streamlit==1.32.0
firebase-admin==6.4.0
opencv-python-headless==4.9.0.80
numpy==1.26.4
Pillow==10.2.0
python-dotenv==1.0.1
pytest==8.1.0
```

> `opencv-python-headless` 사용 이유: JCloud 등 서버 환경에서 GUI 없이 동작.  
> 로컬에서 `cv2` import 오류 시: `pip install opencv-python-headless==4.9.0.80`

---

## 13. 인터페이스 통합을 앞당기는 순서

| 시점 | A | B | C | D | 전체 통합 체크 |
|---|---|---|---|---|---|
| **Day 0** | 환경/Firebase 초기 설정/더미 함수 생성 | CLAHE/ROI 함수 계약 확인 | 점검 결과 dict 확정 + 샘플 생성 | 전이 표 확정 | `docs/TEAM_CONTRACT.md` 합의, 임포트 확인 |
| **Day 1~2** | `save_case/load_image/load_case` 구현 | CLAHE + ROI 테스트 | Gaussian + `check_quality` 테스트 | Median + 전이/메모 테스트 | **모든 함수 단독 테스트 통과** |
| **Day 3~4** | 저장/조회 화면 + Auth/Firestore | 뷰어·비교·ROI 화면 | 자동 점검 연결/API 지원 | 검토 화면·이력 | **등록→자동 점검→검토 흐름 1회** |
| **Day 5~** | Storage 영구성/JCloud 배포 | ROI 비교/UX 개선 | 임계값 실험·오탐/미탐 검증 | 재검토 후속 이력/리포트 | 특화 기능 시간·단계 비교 실험 + 배포 검증 |

### 초기 통합용 최소 코드 호출 예시

```python
# 앱 흐름을 설명하는 간략 예시. 실제 배포에서는 검증된 로그인 세션/권한 검사가 필수.
from src.config import DEFAULT_THRESHOLDS

case_id, image_id = save_case(metadata, uploaded_file.getvalue())
gray = load_image(image_id)
qc = check_quality(gray, DEFAULT_THRESHOLDS)
check_id = save_quality_check(image_id, qc, actor_uid=verified_uid)

clahe_result = apply_clahe(gray)
gauss_result = apply_gaussian(gray, kernel_size=5)
median_result = apply_median(gray, kernel_size=5)
roi_info = get_roi_stats(gray, {"x": 10, "y": 10, "width": 50, "height": 50})
run_id = save_processing_run(image_id, "clahe", {"clip_limit": 2.0,
    "tile_grid_size": [8, 8]}, clahe_result, verified_uid)
# 배정/검토 상태 조건을 갖춘 뒤 D 함수 실행:
# transition_case(case_id, "start_review", reviewer_uid)
```

---

## 14. 제출과 검증 자료

**마감:** 2026-12-18 23:59 KST  
**제출:** GitHub 저장소, JCloud 접속 정보·역할별 테스트 계정, PDF 보고서, 팀 전체 3~5분 시연 영상. 팀원 전원이 LMS에 각자 제출하고 동일 보고서를 첨부한다.

- **보고서 공통 자료:** 요구사항/상태전이도, 서비스·데이터 구조, 알고리즘 3종 원리·파라미터·전후 비교·실패 조건, ROI, 자동 점검 사용 전/후 시나리오, 테스트 결과, 데이터 출처, AI/외부 코드 출처, JCloud 실행 증빙.
- **개인 기여 표:** 이름·학번·GitHub 계정·담당 함수/파일·테스트·실험·관련 Issue/PR/커밋 SHA/리뷰 링크.
- **최종 검사:** `git rev-parse HEAD` SHA, JCloud 배포 코드 버전 일치, 서비스 재시작 후 데이터 유지, 권한 없는 요청 거절, 샘플과 시연 방법 README에 명시.
- **성능 표현 제한:** 밝기·대비·선명도 같은 간단 지표로 진단 품질이나 재촬영 필요 여부를 판단했다고 표현하지 않는다. **교육용 점검 참고**로만 표시.

---

## 15. 첫 회의에서 최종 체크 (이 15개 확인 후 개발 시작)

- [x] 팀원 A/B/C/D 실제 이름과 GitHub 계정 정함 (`docs/GIT_RULES.md` §1)
- [x] Repo 이름 및 Collaborator 초대 완료
- [ ] `main` 보호/PR+리뷰 규칙 합의 (`docs/GIT_RULES.md`)
- [ ] `requirements.txt` 버전 고정 확인 (§12)
- [ ] Firebase 프로젝트 생성 완료 (§10.1)
- [ ] Firebase Authentication 로그인 방식(이메일/비밀번호) 설정 완료
- [ ] 역할별 테스트 계정 3개 생성 완료 (§10.2)
- [ ] Firebase Storage 버킷 생성 완료 (§10.4)
- [ ] `.env` 파일 각자 로컬 설정 완료 (`.gitignore` 확인)
- [ ] `case_id/image_id/roi/gray` 형식 확인 (§3)
- [ ] 함수 시그니처와 예외 규칙 확인 (§4)
- [ ] 업무 상태전이 표 및 권한 매트릭스 확인 (§6)
- [ ] 화질 지표/임계값 임시값 승인 및 보정 담당 C로 확정 (§4)
- [ ] 샘플 이미지 생성 담당 C, Day 0까지 (§8.1)
- [ ] JCloud 배포 담당 A, 첫 통합 날짜 정함 (§11)

### 리뷰

코드 PR은 나를 뺀 팀원 전원을 리뷰어로 지정하고, 아무나 1명이 Approve + 코멘트 1줄이면 머지한다. 오타·작은 문서 수정 PR은 리뷰 없이 본인이 머지한다 (`docs/GIT_RULES.md` §5).

### 최종 담당-제공물 표

| 담당 | 외부에 제공할 필수 API | 코드/시험 증거 |
|---|---|---|
| **A** 이아림 | `save_case`, `load_case`, `load_image`, `search_cases`, `save_processing_run`, `save_quality_check` + **전체 UI (`app.py`, `ui/*.py`)** | `src/services/*`, `ui/*.py`, `test_cases.py`, 배포·권한 점검 |
| **B** 김지빈 | `apply_clahe`, `get_roi_stats` (함수만) | `clahe.py`, `roi.py`, 단위 테스트 결과 |
| **C** 박철우 | `apply_gaussian`, `check_quality` (함수만) + 샘플 이미지 생성 | `gaussian.py`, `checker.py`, 점검 실험표/한계 |
| **D** 이지우 | `apply_median`, `transition_case`, `assign_case`, `add_review_note` (함수만) | `median.py`, `workflow.py`, 상태전이/이력 테스트 |

**계약 변경 규칙:** 새 함수/필드/상태/권한/임계값 버전을 바꾸는 PR은 **문서 → 테스트 → 구현 → 리뷰** 순서로 진행한다.

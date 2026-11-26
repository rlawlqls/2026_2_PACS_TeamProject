# 샘플 영상 — 출처와 이용 조건

> 이 프로젝트는 **실제 환자정보와 비공개 병원 자료를 사용하지 않는다** (과제 안내문 07).
> 모든 영상은 공개 데이터이거나 코드로 생성한 합성 영상이며, 화면에는 모의 케이스임을 표시한다.
> 환자를 식별하려는 시도는 하지 않는다.

샘플 영상 파일은 커밋하지 않는다(`.gitignore`). 각자 아래 방법으로 로컬에 만든다.

---

## 1. 합성 영상 — `generate_samples.py` (C 소유)

품질 점검 임계값 검증용으로 **코드에서 생성**한다. 저작권 없음.

```bash
python sample_data/generate_samples.py     # 화면 확인용 PNG 저장 (선택)
```

테스트는 PNG 파일을 읽지 않고 `make_samples(seed=0)`를 호출한다 (TEAM_CONTRACT §3.4).
`seed`가 같으면 항상 같은 영상이 나온다. **샘플 버전 1.0.0** (`SAMPLES_VERSION`, #20)

기본 영상 `normal`은 **모의 흉부 X-ray**(공기·몸통·폐·종격동·심장·갈비뼈 도형 + 약한 잡음, 256×256)이고,
나머지는 `normal`에 변형 함수를 하나씩 적용해 만든다. 변형 함수는 `(H, W) uint8`이면 크기와 상관없이
쓸 수 있으므로 **LIDC 실제 영상에도 같은 조건을 적용**해 비교 실험을 할 수 있다 (TEAM_CONTRACT §8.5).

| 샘플 | 만드는 방법 | 기대 판정 (demo-v1) | seed 0 지표 (mean / std / Laplacian 분산) |
|---|---|---|---|
| `normal` | `make_phantom()` | `pass` | 104.5 / 60.2 / 1013 |
| `dark` | `adjust_exposure(×1.4, −145)` 저노출 — 어두운 부분이 검게 뭉개짐 | `too_dark` | 38.6 / 44.6 / 997 |
| `bright` | `adjust_exposure(×1.8, +100)` 과노출 — 밝은 부분이 하얗게 날아감 | `too_bright` | 221.4 / 47.4 / 1435 |
| `low_contrast` | `reduce_contrast(0.45)` 평균 중심으로 명암 폭 45% | `low_contrast` | 104.0 / 27.1 / 206 |
| `blur` | `blur(σ=2.5)` | `possibly_blurry` | 104.5 / 57.3 / 4 |
| `gaussian_noise` | `add_gaussian_noise(σ=20)` | — (Gaussian 처리 전후 비교용) | |
| `salt_pepper` | `add_salt_pepper(4%)` | — (Median 처리 전후 비교용) | |

**§8.1 원래 생성식과 다른 이유:** 무작위 잡음 영상을 어둡게(×0.2)·흐리게 만들면 표준편차도 함께 떨어져
`dark`·`blur`에 `low_contrast`가 겹친다. 그러면 "의도한 사유가 나왔는지" 검증이 모호해지므로,
각 품질 샘플이 **의도한 사유 1개만** 나오도록 바꿨다 (seed 0~9 자동 테스트, 0~29 수동 확인).
임계값(`src/quality/thresholds.py`)을 보정하면 이 표와 테스트가 함께 바뀔 수 있다.

---

## 2. 실제 DICOM 영상 — LIDC-IDRI

DICOM 등록·태그 추출·표시 변환을 검증하는 데 쓴다.

```bash
python sample_data/download_lidc.py        # dicom_data/ 에 10케이스 저장
```

### 데이터 정보

| 항목 | 내용 |
|---|---|
| 컬렉션 | LIDC-IDRI (Lung Image Database Consortium and Image Database Resource Initiative) |
| 제공 | The Cancer Imaging Archive (TCIA), 미국 National Cancer Institute |
| 사용 범위 | 흉부 X-ray(DX) 10케이스 — 전체 컬렉션은 CT 포함 약 125GB |
| 형식 | DICOM (원본 그대로 사용, PNG로 변환하지 않음) |
| 라이선스 | **Creative Commons Attribution 3.0 Unported (CC BY 3.0)** |
| DOI | `10.7937/K9/TCIA.2015.LO9QL9SX` |
| 컬렉션 주소 | https://www.cancerimagingarchive.net/collection/lidc-idri/ |
| 확인일 | 2026-11-25 |

### 인용 (보고서 "데이터 출처"에 기재)

> Armato III, S. G., McLennan, G., Bidaut, L., McNitt-Gray, M. F., Meyer, C. R.,
> Reeves, A. P., … Clarke, L. P. (2015). *Data From LIDC-IDRI* [Data set].
> The Cancer Imaging Archive. https://doi.org/10.7937/K9/TCIA.2015.LO9QL9SX

> Clark, K., Vendt, B., Smith, K., Freymann, J., Kirby, J., Koppel, P., … Prior, F. (2013).
> The Cancer Imaging Archive (TCIA): Maintaining and Operating a Public Information Repository.
> *Journal of Digital Imaging*, 26(6), 1045–1057.

### 이 데이터를 다룰 때 알아야 할 것

실제 파일을 열어 확인한 내용이다 (LIDC-IDRI-0001, 2026-11-25).

| 태그 | 값 | 처리 |
|---|---|---|
| `PatientID` | `LIDC-IDRI-0001` | 모의 케이스 ID로 사용 |
| `Modality` | `DX` | `exam_type = "X-ray"`로 변환 |
| `BodyPartExamined` | `CHEST` | 설명으로 사용 |
| `PatientName` / `PatientSex` / `PatientAge` | **빈 문자열** | 비식별 처리됨. 화면에서 빈 값 처리 |
| `ViewPosition` / `StudyDescription` / `SeriesDescription` | **태그 없음** | 접근 시 예외 처리 필요 |
| `StudyDate` | `20000101` | 비식별용 고정값. 등록일은 업로드 시각으로 따로 생성 |
| `BitsStored` | `14` (unsigned, 0~16383) | 표시용 `uint8` 변환 필요 |
| `PhotometricInterpretation` | `MONOCHROME2` | 반전 불필요 (CR은 다를 수 있음) |
| `WindowCenter` / `WindowWidth` | `-600` / `1600` | **쓰지 않는다** — 아래 참고 |

**창 값(WindowCenter/Width)을 쓰면 안 되는 이유:** 픽셀값은 0~16383인데 창 중심이 −600이라,
그대로 적용하면 거의 모든 픽셀이 범위를 넘어 **화면이 흰색으로 포화된다.** 실제로 확인했다.
대신 픽셀값의 1~99 백분위 구간을 0~255로 펼친다 (TEAM_CONTRACT §3.1, `dicom_io.to_gray`).

**영상에 찍힌 마커:** 필름에 `L` 같은 좌우 표시가 흰색으로 들어가 있다. 자동 품질 점검의
밝기·대비 계산이 이 부분 때문에 치우칠 수 있으므로, 임계값 보정 때 고려한다.

---

## 주의

- 분석 수치와 점검 표시는 **교육용 결과**이며, 실제 진단이나 임상 성능을 입증한 결과가 아니다.
- 밝기·대비·선명도 지표로 진단 품질이나 재촬영 필요 여부를 판단했다고 표현하지 않는다.

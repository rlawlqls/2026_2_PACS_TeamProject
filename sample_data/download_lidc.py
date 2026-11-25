"""LIDC-IDRI 흉부 X-ray(DICOM) 샘플 내려받기 (C 소유, TEAM_CONTRACT §3.4).

샘플 영상 파일은 커밋하지 않으므로(§9.2), 각자 clone 후 한 번 실행해서 받는다::

    python sample_data/download_lidc.py

받은 파일은 `dicom_data/LIDC-IDRI-XXXX/*.dcm`에 저장되고 `.gitignore`가 막는다.
이미 받은 케이스는 건너뛰므로 여러 번 실행해도 안전하다.

HTTP 요청은 `requests`로 한다. `requests`는 인증서 묶음(certifi)을 함께 쓰므로
macOS python.org 설치본처럼 시스템 인증서가 연결되지 않은 환경에서도 동작한다 (#9).

데이터 출처와 이용 조건은 `sample_data/README.md` 참고.
"""

import io
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests

API = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
OUT = Path("dicom_data")

#: 받을 케이스 수. 시연·테스트에는 10개면 충분하다 (한 케이스당 약 7~16MB).
COUNT = 10

#: 연속 요청 시 서버가 응답을 늦추므로 케이스 사이에 쉰다.
SLEEP_SECONDS = 2

#: 스트리밍으로 받을 때 한 번에 읽는 크기 (바이트).
CHUNK_SIZE = 65536


def fetch_series_list() -> list[dict]:
    """LIDC-IDRI의 DX(흉부 X-ray) 시리즈 목록을 가져온다."""
    response = requests.get(
        f"{API}/getSeries",
        params={"Collection": "LIDC-IDRI", "Modality": "DX"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def download_series(series: dict, dest: Path) -> None:
    """시리즈 하나를 내려받아 dest 폴더에 풀어 놓는다.

    중간에 실패하면 dest를 만들지 않는다. dest가 남으면 다음 실행 때
    "이미 있음"으로 건너뛰어 버리므로, 임시 폴더에 푼 뒤 마지막에 이름을 바꾼다.
    """
    expected = series.get("FileSize", 0)
    chunks, received = [], 0

    with requests.get(
        f"{API}/getImage",
        params={"SeriesInstanceUID": series["SeriesInstanceUID"]},
        stream=True,
        timeout=600,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            chunks.append(chunk)
            received += len(chunk)
            print(f"\r      {received / 1e6:6.1f} / {expected / 1e6:.1f} MB", end="", flush=True)
    print(flush=True)

    partial = dest.with_name(dest.name + ".part")
    shutil.rmtree(partial, ignore_errors=True)
    try:
        zipfile.ZipFile(io.BytesIO(b"".join(chunks))).extractall(partial)
        partial.rename(dest)
    except Exception:
        shutil.rmtree(partial, ignore_errors=True)
        raise


def main() -> None:
    print("TCIA에서 시리즈 목록을 가져오는 중...", flush=True)
    try:
        series_list = fetch_series_list()
    except requests.RequestException as error:
        sys.exit(f"시리즈 목록을 가져오지 못했습니다: {error}")
    print(f"전체 DX 시리즈 {len(series_list)}개 중 {COUNT}개를 받습니다.\n", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for index, series in enumerate(series_list[:COUNT], start=1):
        patient_id = series["PatientID"]
        dest = OUT / patient_id

        if dest.exists():
            print(f"[{index}/{COUNT}] {patient_id} 건너뜀 (이미 있음)", flush=True)
            continue

        size_mb = series.get("FileSize", 0) / 1e6
        image_count = series.get("ImageCount", "?")
        print(f"[{index}/{COUNT}] {patient_id}  영상 {image_count}장  {size_mb:.1f}MB", flush=True)

        started = time.time()
        try:
            download_series(series, dest)
        except (requests.RequestException, zipfile.BadZipFile) as error:
            print(f"   실패: {error}", flush=True)
            failed.append(patient_id)
            continue
        print(f"   완료 ({time.time() - started:.0f}초)", flush=True)
        time.sleep(SLEEP_SECONDS)

    print(f"\n저장 위치: {OUT.resolve()}")
    if failed:
        sys.exit(f"받지 못한 케이스 {len(failed)}개: {', '.join(failed)} — 다시 실행하면 이어서 받습니다.")


if __name__ == "__main__":
    main()

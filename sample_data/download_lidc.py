"""LIDC-IDRI 흉부 X-ray(DICOM) 샘플 내려받기 (C 소유, TEAM_CONTRACT §3.4).

샘플 영상 파일은 커밋하지 않으므로(§9.2), 각자 clone 후 한 번 실행해서 받는다::

    python sample_data/download_lidc.py

받은 파일은 `dicom_data/LIDC-IDRI-XXXX/*.dcm`에 저장되고 `.gitignore`가 막는다.
이미 받은 케이스는 건너뛰므로 여러 번 실행해도 안전하다.

데이터 출처와 이용 조건은 `sample_data/README.md` 참고.
"""

import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

API = "https://services.cancerimagingarchive.net/nbia-api/services/v1"
OUT = Path("dicom_data")

#: 받을 케이스 수. 시연·테스트에는 10개면 충분하다 (한 케이스당 약 7~16MB).
COUNT = 10

#: 연속 요청 시 서버가 응답을 늦추므로 케이스 사이에 쉰다.
SLEEP_SECONDS = 2


def fetch_series_list() -> list[dict]:
    """LIDC-IDRI의 DX(흉부 X-ray) 시리즈 목록을 가져온다."""
    url = f"{API}/getSeries?Collection=LIDC-IDRI&Modality=DX"
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read())


def download_series(series: dict, dest: Path) -> None:
    """시리즈 하나를 내려받아 dest 폴더에 풀어 놓는다."""
    url = f"{API}/getImage?SeriesInstanceUID={series['SeriesInstanceUID']}"
    expected = series.get("FileSize", 0)

    with urllib.request.urlopen(url, timeout=600) as response:
        chunks, received = [], 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            received += len(chunk)
            print(f"\r      {received / 1e6:6.1f} / {expected / 1e6:.1f} MB", end="", flush=True)

    dest.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(b"".join(chunks))).extractall(dest)


def main() -> None:
    print("TCIA에서 시리즈 목록을 가져오는 중...", flush=True)
    series_list = fetch_series_list()
    print(f"전체 DX 시리즈 {len(series_list)}개 중 {COUNT}개를 받습니다.\n", flush=True)

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
        download_series(series, dest)
        print(f"   완료 ({time.time() - started:.0f}초)", flush=True)
        time.sleep(SLEEP_SECONDS)

    print(f"\n저장 위치: {OUT.resolve()}")


if __name__ == "__main__":
    main()

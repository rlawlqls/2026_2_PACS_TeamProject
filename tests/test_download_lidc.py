"""download_lidc.py 테스트 (C 소유, #9).

실제 TCIA 서버에 접속하지 않는다. requests.get을 가짜 응답으로 바꿔서
요청 조건과 저장 방식만 확인한다.
"""

import io
import zipfile

import pytest
import requests

from sample_data import download_lidc


class FakeResponse:
    """requests.Response 대신 쓰는 최소 가짜 응답."""

    def __init__(self, *, json_data=None, content=b"", status_code=200):
        self._json = json_data
        self._content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")

    def json(self):
        return self._json

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self._content), chunk_size):
            yield self._content[start:start + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


SERIES = {"PatientID": "LIDC-IDRI-0002", "SeriesInstanceUID": "1.2.3", "FileSize": 10}


def test_fetch_series_list_requests_only_dx(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(json_data=[SERIES])

    monkeypatch.setattr(download_lidc.requests, "get", fake_get)

    assert download_lidc.fetch_series_list() == [SERIES]
    url, kwargs = calls[0]
    assert url.endswith("/getSeries")
    assert kwargs["params"] == {"Collection": "LIDC-IDRI", "Modality": "DX"}


def test_download_series_extracts_into_dest(monkeypatch, tmp_path):
    payload = make_zip({"00000001.dcm": b"DICM-fake", "LICENSE": b"CC BY 3.0"})
    monkeypatch.setattr(download_lidc.requests, "get",
                        lambda url, **kwargs: FakeResponse(content=payload))

    dest = tmp_path / "LIDC-IDRI-0002"
    download_lidc.download_series(SERIES, dest)

    assert (dest / "00000001.dcm").read_bytes() == b"DICM-fake"
    assert not (tmp_path / "LIDC-IDRI-0002.part").exists()


def test_download_series_http_error_leaves_no_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(download_lidc.requests, "get",
                        lambda url, **kwargs: FakeResponse(status_code=503))

    dest = tmp_path / "LIDC-IDRI-0002"
    with pytest.raises(requests.HTTPError):
        download_lidc.download_series(SERIES, dest)

    # 폴더가 남으면 다음 실행에서 "이미 있음"으로 건너뛰므로 남기지 않는다.
    assert list(tmp_path.iterdir()) == []


def test_download_series_broken_zip_leaves_no_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(download_lidc.requests, "get",
                        lambda url, **kwargs: FakeResponse(content=b"not a zip"))

    dest = tmp_path / "LIDC-IDRI-0002"
    with pytest.raises(zipfile.BadZipFile):
        download_lidc.download_series(SERIES, dest)

    assert list(tmp_path.iterdir()) == []


def test_main_reports_network_error(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        raise requests.ConnectionError("SSL: CERTIFICATE_VERIFY_FAILED")

    monkeypatch.setattr(download_lidc.requests, "get", fake_get)
    monkeypatch.setattr(download_lidc, "OUT", tmp_path / "dicom_data")

    with pytest.raises(SystemExit) as exit_info:
        download_lidc.main()

    assert "시리즈 목록을 가져오지 못했습니다" in str(exit_info.value)

"""품질 점검 관련 테스트 (C 소유).

- 합성 샘플(`make_samples`)과 변형 함수 (#20), 샘플별 check_quality 사유
- 자동 점검 결과 탭(`src/ui/quality_panel.py`)의 화면 문구 함수와 개발 모드 화면 (#45)

check_quality 자체의 계산·검증 테스트는 tests/test_checker.py에 있다.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from sample_data import generate_samples as gs
from sample_data.generate_samples import make_samples
from src.errors import NotFoundError, PermissionDeniedError, StorageError, ValidationError
from src.quality.checker import check_quality
from src.quality.thresholds import DEFAULT_THRESHOLDS
from src.services import cases
from src.ui import quality_panel as qp

SAMPLE_NAMES = {"normal", "dark", "bright", "low_contrast", "blur", "gaussian_noise", "salt_pepper"}

#: 품질 점검 샘플마다 기대하는 점검 사유 (TEAM_CONTRACT §4 reasons 순서)
EXPECTED_REASONS = {
    "normal": [],
    "dark": ["too_dark"],
    "bright": ["too_bright"],
    "low_contrast": ["low_contrast"],
    "blur": ["possibly_blurry"],
}


def contract_reasons(gray: np.ndarray, thresholds: dict) -> list[str]:
    """샘플이 실제 점검 함수(check_quality)에서 받는 사유.

    예전에는 계약 식을 테스트 안에서 따로 계산했는데, 계약이 바뀌면(v2.4 512px 축소)
    실제 구현과 어긋나므로 check_quality 결과를 그대로 쓴다.
    """
    return check_quality(gray, thresholds)["reasons"]


# ---------------------------------------------------------------------------
# make_samples — 정상 입력
# ---------------------------------------------------------------------------
def test_make_samples_returns_seven_images_in_image_spec(samples):
    assert set(samples) == SAMPLE_NAMES
    for name, image in samples.items():
        assert image.ndim == 2, name
        assert image.dtype == np.uint8, name
        assert image.shape == samples["normal"].shape, name


def test_make_samples_same_seed_gives_same_images():
    first, second = make_samples(seed=3), make_samples(seed=3)
    for name in SAMPLE_NAMES:
        assert np.array_equal(first[name], second[name]), name


def test_make_samples_different_seed_gives_different_images():
    assert not np.array_equal(make_samples(seed=0)["normal"], make_samples(seed=1)["normal"])


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("name", sorted(EXPECTED_REASONS))
def test_quality_sample_triggers_only_intended_reason(seed, name):
    image = make_samples(seed=seed)[name]
    assert contract_reasons(image, DEFAULT_THRESHOLDS) == EXPECTED_REASONS[name]


def test_noise_samples_are_noisier_than_normal(samples):
    normal = samples["normal"].astype(np.int16)
    assert np.abs(samples["gaussian_noise"].astype(np.int16) - normal).mean() > 10
    changed = samples["salt_pepper"] != samples["normal"]
    assert 0.02 < changed.mean() < 0.06          # 약 4%가 바뀜
    assert set(np.unique(samples["salt_pepper"][changed])) <= {0, 255}


def test_save_samples_writes_png_per_sample(tmp_path):
    paths = gs.save_samples(tmp_path, seed=0)
    assert {path.stem for path in paths} == SAMPLE_NAMES
    reloaded = cv2.imread(str(tmp_path / "normal.png"), cv2.IMREAD_GRAYSCALE)
    assert np.array_equal(reloaded, make_samples(seed=0)["normal"])


# ---------------------------------------------------------------------------
# 변형 함수 — LIDC 같은 다른 크기 영상에도 적용 가능, 원본 불변
# ---------------------------------------------------------------------------
DEGRADERS = [
    lambda g: gs.adjust_exposure(g, *gs.DARK_EXPOSURE),
    lambda g: gs.adjust_exposure(g, *gs.BRIGHT_EXPOSURE),
    lambda g: gs.reduce_contrast(g),
    lambda g: gs.blur(g),
    lambda g: gs.add_gaussian_noise(g, 20.0, np.random.default_rng(0)),
    lambda g: gs.add_salt_pepper(g, 0.04, np.random.default_rng(0)),
]


@pytest.mark.parametrize("degrade", DEGRADERS)
def test_degraders_keep_spec_and_do_not_modify_input(degrade):
    gray = np.random.default_rng(7).integers(0, 256, (300, 200), dtype=np.uint8)
    before = gray.copy()
    out = degrade(gray)
    assert out.shape == gray.shape and out.dtype == np.uint8
    assert np.array_equal(gray, before)
    assert out is not gray


# ---------------------------------------------------------------------------
# 오류 입력
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [-1, 1.5, "0", True, None])
def test_make_samples_rejects_invalid_seed(seed):
    with pytest.raises(ValidationError):
        make_samples(seed=seed)


@pytest.mark.parametrize("bad", [
    np.zeros((8, 8, 3), dtype=np.uint8),     # 컬러(3채널)
    np.zeros((8, 8), dtype=np.float64),      # uint8 아님
    [[0, 1], [2, 3]],                        # 배열 아님
])
@pytest.mark.parametrize("degrade", DEGRADERS)
def test_degraders_reject_non_gray_input(degrade, bad):
    with pytest.raises(ValidationError):
        degrade(bad)


@pytest.mark.parametrize("call", [
    lambda g: gs.adjust_exposure(g, 0, 10),
    lambda g: gs.reduce_contrast(g, 0),
    lambda g: gs.reduce_contrast(g, 1.5),
    lambda g: gs.blur(g, 0),
    lambda g: gs.add_gaussian_noise(g, -1, np.random.default_rng(0)),
    lambda g: gs.add_salt_pepper(g, 1.5, np.random.default_rng(0)),
])
def test_degraders_reject_invalid_parameters(call):
    with pytest.raises(ValidationError):
        call(np.zeros((8, 8), dtype=np.uint8))


# ---------------------------------------------------------------------------
# 자동 점검 결과 탭 (src/ui/quality_panel.py, #45) — 화면 문구를 만드는 함수
# ---------------------------------------------------------------------------
APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.mark.parametrize("status, label, color", [
    ("pass", "경고 없음", "green"),
    ("needs_check", "확인 필요", "orange"),
    ("error", "점검 실패", "orange"),
    (None, "기록 없음", "gray"),
])
def test_status_badge_shows_quality_status(status, label, color):
    assert qp.status_badge(status) == f'<span class="pacs-badge {color}">{label}</span>'


def test_status_badge_escapes_unknown_value():
    badge = qp.status_badge("<b>x</b>")
    assert "<b>" not in badge and "&lt;b&gt;" in badge


@pytest.mark.parametrize("name", sorted(EXPECTED_REASONS))
def test_metric_rows_follow_check_quality_reasons(samples, name):
    result = check_quality(samples[name], DEFAULT_THRESHOLDS)
    rows = qp.metric_rows(result)
    assert [row["metric"] for row in rows] == ["밝기 평균", "대비 (밝기 표준편차)", "선명도 (Laplacian 분산)"]
    warned = [row["verdict"] for row in rows if row["verdict"] != "기준 안"]
    expected = [f"⚠️ {qp.REASON_LABELS[r]}" for r in EXPECTED_REASONS[name]]
    assert warned == expected
    assert rows[0]["value"] == f'{result["metrics"]["brightness_mean"]:.1f}'


def test_metric_rows_show_applied_thresholds():
    result = check_quality(make_samples(0)["normal"], DEFAULT_THRESHOLDS)
    criteria = [row["criterion"] for row in qp.metric_rows(result)]
    t = DEFAULT_THRESHOLDS
    assert criteria == [
        f'{t["brightness_min"]:.1f} 이상, {t["brightness_max"]:.1f} 이하',
        f'{t["contrast_std_min"]:.1f} 이상',
        f'{t["laplacian_var_min"]:.1f} 이상',
    ]


def test_metric_rows_show_both_brightness_reasons_in_one_cell():
    """밝기 칸은 too_dark·too_bright 둘 중 하나만 나오지만, 둘 다 있어도 빠뜨리지 않는다."""
    result = check_quality(make_samples(0)["normal"], DEFAULT_THRESHOLDS)
    result = {**result, "reasons": ["too_dark", "too_bright"]}
    assert qp.metric_rows(result)[0]["verdict"] == "⚠️ 어두움, 너무 밝음"


def test_metrics_table_markdown_has_header_and_escapes_cells():
    rows = [{"metric": "<i>m</i>", "value": "1.0", "criterion": "1.0 이상", "verdict": "기준 안"}]
    table = qp.metrics_table_markdown(rows).splitlines()
    assert table[0] == "| 지표 | 측정값 | 기준 | 판정 |"
    assert len(table) == 3 and "&lt;i&gt;" in table[2]


def test_reason_messages_keep_contract_order_and_explain_each_reason():
    messages = qp.reason_messages(["too_dark", "low_contrast", "possibly_blurry"])
    assert [m.split(":")[0] for m in messages] == ["어두움", "낮은 대비", "흐림 의심"]
    assert all(len(m.split(": ", 1)[1]) > 10 for m in messages)
    assert qp.reason_messages([]) == []


@pytest.mark.parametrize("saved, current, kind", [
    (None, "pass", "info"),
    ("error", "pass", "warning"),
    ("pass", "needs_check", "warning"),
    ("needs_check", "pass", "warning"),
])
def test_saved_status_message_when_record_missing_failed_or_different(saved, current, kind):
    assert qp.saved_status_message(saved, current)[0] == kind


@pytest.mark.parametrize("status", ["pass", "needs_check"])
def test_saved_status_message_is_none_when_same(status):
    assert qp.saved_status_message(status, status) is None


@pytest.mark.parametrize("shape, small", [((256, 256), True), ((512, 300), True), ((513, 100), False), ((2000, 2000), False)])
def test_is_small_image_uses_sharpness_resize_limit(shape, small):
    assert qp.is_small_image(shape) is small


def test_make_thumbnail_shrinks_large_image_and_keeps_input():
    gray = np.random.default_rng(0).integers(0, 256, (1000, 500), dtype=np.uint8)
    before = gray.copy()
    thumb = qp.make_thumbnail(gray, side=320)
    assert thumb.shape == (320, 160) and thumb.dtype == np.uint8
    assert np.array_equal(gray, before)


def test_make_thumbnail_does_not_enlarge_small_image():
    gray = np.zeros((64, 32), dtype=np.uint8)
    thumb = qp.make_thumbnail(gray, side=320)
    assert thumb.shape == gray.shape and thumb is not gray


# ---------------------------------------------------------------------------
# 자동 점검 결과 탭 — 개발 모드에서 실제 앱 화면 (streamlit AppTest)
# ---------------------------------------------------------------------------
@pytest.fixture
def dev_app(monkeypatch):
    """개발 모드 앱. 개발 모드 점검 저장소는 테스트마다 비운다 (테스트끼리 영향 없게)."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(cases, "_DEV_QUALITY", {})
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def choose_case(at: AppTest, sample: str) -> None:
    """케이스 목록 탭의 선택 상자에서 샘플 케이스를 고른다 (화면에는 '라벨 · 설명'으로 보인다).

    AppTest(1.32)는 format_func가 있는 선택 상자의 값을 다음 실행에 그대로 넘기지 못하므로,
    실행할 때마다 다시 고른다.
    """
    box = next(s for s in at.selectbox if s.label == "케이스 선택")
    box.select_index(next(i for i, option in enumerate(box.options) if option.endswith(f"({sample})")))


def select_case(at: AppTest, sample: str) -> AppTest:
    choose_case(at, sample)
    at = at.run()
    assert at.session_state["selected_case_id"] == f"case_dev_{sample}"
    return at


def texts(elements) -> list[str]:
    return [element.value for element in elements]


@pytest.mark.parametrize("sample", sorted(EXPECTED_REASONS))
def test_panel_shows_intended_reasons_for_each_dev_sample(dev_app, sample):
    at = select_case(dev_app, sample)
    assert not at.exception
    shown = [w.split(":")[0] for w in texts(at.warning) if ":" in w and w.split(":")[0] in qp.REASON_LABELS.values()]
    assert shown == [qp.REASON_LABELS[r] for r in EXPECTED_REASONS[sample]]
    if not EXPECTED_REASONS[sample]:
        assert "팀 기준상 경고 없음 (의학적 판정 아님)" in texts(at.success)
    table = next(m for m in texts(at.markdown) if m.startswith("| 지표 |"))
    assert "밝기 평균" in table and "선명도 (Laplacian 분산)" in table
    assert any(DEFAULT_THRESHOLDS["version"] in c and "1.1.0" in c for c in texts(at.caption))


def test_panel_saves_current_result_and_shows_saved_status(dev_app):
    at = select_case(dev_app, "dark")
    assert any("저장된 점검 기록이 없습니다" in m for m in texts(at.info))

    choose_case(at, "dark")
    at = at.button(key="quality_save").click().run()
    assert not at.exception
    assert any(s.startswith("점검 기록을 저장했습니다 (qc_") for s in texts(at.success))
    saved = cases._DEV_QUALITY["img_dev_dark"]
    assert saved["status"] == "needs_check" and saved["reasons"] == ["too_dark"]
    header = next(m for m in texts(at.markdown) if "저장된 최근 점검" in m)
    assert header.count("확인 필요") == 2       # 저장된 결과와 현재 결과가 같다
    assert not any("저장된 점검 기록이 없습니다" in m for m in texts(at.info))


def test_panel_warns_when_saved_status_differs_from_current(dev_app):
    """기준값이 바뀌기 전에 저장된 기록처럼, 저장된 상태와 지금 결과가 다르면 안내한다."""
    cases._DEV_QUALITY["img_dev_normal"] = {"check_id": "qc_old", "status": "needs_check"}
    at = select_case(dev_app, "normal")
    assert any("저장된 결과(확인 필요)와 현재 기준으로 다시 잰 결과(경고 없음)가 다릅니다" in w
               for w in texts(at.warning))


def test_panel_shows_small_image_note_for_dev_samples(dev_app):
    at = select_case(dev_app, "normal")             # 합성 샘플은 256px
    assert qp.SMALL_IMAGE_NOTE in texts(at.info)


PANEL_SCRIPT = """
import streamlit as st
from src.ui import quality_panel
st.session_state.setdefault("auth_user", {"uid": "u1", "role": "reviewer"})
{setup}
quality_panel.render()
"""


def run_panel(setup: str = "") -> AppTest:
    return AppTest.from_string(PANEL_SCRIPT.replace("{setup}", setup), default_timeout=30).run()


def test_panel_asks_to_select_case_when_nothing_selected():
    at = run_panel()
    assert not at.exception
    assert texts(at.info) == ["케이스 목록 탭에서 케이스를 먼저 선택해 주세요."]


@pytest.mark.parametrize("error", [
    PermissionDeniedError("이 케이스를 볼 권한이 없습니다."),
    NotFoundError("케이스를 찾을 수 없습니다."),
])
def test_panel_shows_error_when_case_cannot_be_loaded(monkeypatch, error):
    def fail(case_id, *, actor_uid):
        raise error
    monkeypatch.setattr(cases, "load_case", fail)
    at = run_panel('st.session_state["selected_case_id"] = "case_x"')
    assert not at.exception
    assert texts(at.error) == [str(error)]
    assert not any(b.key == "quality_save" for b in at.button)    # 저장 버튼을 보이지 않는다


def test_panel_shows_error_when_image_cannot_be_loaded(monkeypatch):
    monkeypatch.setattr(cases, "load_case", lambda case_id, *, actor_uid: {"case_id": case_id, "image_id": "img_x"})
    def missing(image_id):
        raise NotFoundError("영상을 찾을 수 없습니다.")
    monkeypatch.setattr(cases, "load_image", missing)
    at = run_panel('st.session_state["selected_case_id"] = "case_x"')
    assert not at.exception
    assert texts(at.error) == ["영상을 찾을 수 없습니다."]


def test_panel_passes_logged_in_uid_to_load_case(monkeypatch):
    seen = {}
    def record(case_id, *, actor_uid):
        seen.update(case_id=case_id, actor_uid=actor_uid)
        return {"case_id": case_id, "image_id": None}
    monkeypatch.setattr(cases, "load_case", record)
    at = run_panel('st.session_state["selected_case_id"] = "case_x"')
    assert seen == {"case_id": "case_x", "actor_uid": "u1"}
    assert texts(at.info) == ["이 케이스에는 점검할 영상이 없습니다."]


def test_panel_shows_error_and_keeps_status_when_save_fails(dev_app, monkeypatch):
    def fail(image_id, result, actor_uid=None):
        raise StorageError("점검 결과를 저장하지 못했습니다. 등록된 영상은 그대로 있습니다.")
    monkeypatch.setattr(cases, "save_quality_check", fail)
    at = select_case(dev_app, "blur")
    choose_case(at, "blur")
    at = at.button(key="quality_save").click().run()
    assert not at.exception
    assert texts(at.error) == ["점검 결과를 저장하지 못했습니다. 등록된 영상은 그대로 있습니다."]
    assert not any(s.startswith("점검 기록을 저장했습니다") for s in texts(at.success))
    assert "img_dev_blur" not in cases._DEV_QUALITY


LIDC_DCM = sorted(Path(__file__).resolve().parents[1].glob("dicom_data/**/*.dcm"))


@pytest.mark.skipif(not LIDC_DCM, reason="dicom_data/에 LIDC-IDRI가 없음 (download_lidc.py로 받기)")
def test_panel_with_large_lidc_image_has_no_small_image_note(monkeypatch):
    """실제 크기(약 2000px)의 LIDC 표시용 영상: 정상 판정, 작은 영상 안내 없음, 미리보기는 축소."""
    from src.dicom_io import to_gray

    gray = to_gray(LIDC_DCM[0].read_bytes())
    monkeypatch.setattr(cases, "load_case",
                        lambda case_id, *, actor_uid: {"case_id": case_id, "image_id": "img_lidc",
                                                       "case_label": "LIDC", "latest_quality_status": "pass"})
    monkeypatch.setattr(cases, "load_image", lambda image_id: gray.copy())
    at = run_panel('st.session_state["selected_case_id"] = "case_lidc"')
    assert not at.exception
    assert qp.SMALL_IMAGE_NOTE not in texts(at.info)
    assert check_quality(gray, DEFAULT_THRESHOLDS)["status"] == "pass"
    assert "팀 기준상 경고 없음 (의학적 판정 아님)" in texts(at.success)
    assert any(f"{gray.shape[1]}×{gray.shape[0]}px" in c for c in texts(at.caption))
    assert max(at.session_state["quality_cache"]["thumbnail"].shape) == 320

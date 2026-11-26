"""B 담당 뷰어·ROI 탭 테스트 (TEAM_CONTRACT §7).

화면 계산 함수는 Streamlit 없이 직접 부르고, 탭 화면은 AppTest로 개발 모드에서 실행해 본다.
"""

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from src.errors import NotFoundError, PermissionDeniedError, StorageError, ValidationError
from src.processing.clahe import apply_clahe
from src.processing.gaussian import apply_gaussian
from src.processing.median import apply_median
from src.services import cases
from src.ui import viewer


# ---------------------------------------------------------------------------
# 알고리즘 호출
# ---------------------------------------------------------------------------

def test_default_params_match_contract_defaults(samples):
    gray = samples["normal"]

    np.testing.assert_array_equal(
        viewer.run_algorithm(gray, "clahe", viewer.DEFAULT_PARAMS["clahe"]), apply_clahe(gray))
    np.testing.assert_array_equal(
        viewer.run_algorithm(gray, "gaussian", viewer.DEFAULT_PARAMS["gaussian"]), apply_gaussian(gray))
    np.testing.assert_array_equal(
        viewer.run_algorithm(gray, "median", viewer.DEFAULT_PARAMS["median"]), apply_median(gray))


@pytest.mark.parametrize("algorithm", ["clahe", "gaussian", "median"])
def test_run_algorithm_keeps_spec_and_input(samples, algorithm):
    gray = samples["gaussian_noise"].copy()
    original = gray.copy()

    result = viewer.run_algorithm(gray, algorithm, viewer.DEFAULT_PARAMS[algorithm])

    assert result.shape == gray.shape and result.dtype == np.uint8
    np.testing.assert_array_equal(gray, original)


def test_every_algorithm_has_label_help_and_defaults():
    assert set(viewer.ALGORITHM_LABELS) == {"clahe", "gaussian", "median"}
    assert set(viewer.ALGORITHM_HELP) == set(viewer.ALGORITHM_LABELS)
    assert set(viewer.DEFAULT_PARAMS) == set(viewer.ALGORITHM_LABELS)


@pytest.mark.parametrize("algorithm, params", [
    ("sharpen", {}),                                       # 없는 알고리즘
    ("clahe", {"clip_limit": 2.0}),                        # 설정 빠짐
    ("clahe", {"clip_limit": 0.0, "tile_grid_size": [8, 8]}),
    ("clahe", {"clip_limit": 2.0, "tile_grid_size": 8}),
    ("gaussian", {"kernel_size": 4, "sigma": 0.0}),        # 짝수 커널
    ("median", {"kernel_size": 1}),
    ("median", None),
])
def test_run_algorithm_rejects_bad_request(samples, algorithm, params):
    with pytest.raises(ValidationError):
        viewer.run_algorithm(samples["normal"], algorithm, params)


def test_params_summary():
    assert viewer.params_summary("clahe", {"clip_limit": 2.0, "tile_grid_size": [8, 8]}) == "clip_limit 2.0 · 격자 8×8"
    assert viewer.params_summary("gaussian", {"kernel_size": 5, "sigma": 0.0}) == "kernel_size 5 · sigma 자동"
    assert viewer.params_summary("gaussian", {"kernel_size": 9, "sigma": 1.5}) == "kernel_size 9 · sigma 1.5"
    assert viewer.params_summary("median", {"kernel_size": 3}) == "kernel_size 3"


# ---------------------------------------------------------------------------
# 확대·이동
# ---------------------------------------------------------------------------

def test_view_window_zoom_1_shows_whole_image():
    assert viewer.view_window((100, 200), 1.0, 0.5, 0.5) == (0, 0, 200, 100)
    assert viewer.view_window((100, 200), 1.0, 1.0, 0.0) == (0, 0, 200, 100)   # 배율 1이면 이동 무시


def test_view_window_zoom_and_pan():
    assert viewer.view_window((100, 200), 2.0, 0.5, 0.5) == (50, 25, 150, 75)   # 가운데
    assert viewer.view_window((100, 200), 2.0, 0.0, 0.0) == (0, 0, 100, 50)     # 왼쪽 위 끝
    assert viewer.view_window((100, 200), 2.0, 1.0, 1.0) == (100, 50, 200, 100)  # 오른쪽 아래 끝


@pytest.mark.parametrize("zoom", [1.0, 1.5, 3.0, 8.0, 1000.0])
@pytest.mark.parametrize("pan", [(-1.0, 2.0), (0.0, 0.0), (0.3, 0.9), (1.0, 1.0)])
def test_view_window_always_inside_image(zoom, pan):
    height, width = 37, 53
    x0, y0, x1, y1 = viewer.view_window((height, width), zoom, *pan)

    assert 0 <= x0 < x1 <= width
    assert 0 <= y0 < y1 <= height


def test_view_window_below_minimum_zoom_is_treated_as_1():
    assert viewer.view_window((100, 200), 0.2) == (0, 0, 200, 100)


def test_render_view_returns_rgb_with_long_side_and_keeps_input(samples):
    gray = samples["normal"].copy()
    original = gray.copy()

    view = viewer.render_view(gray, viewer.view_window(gray.shape, 2.0), display_side=300)

    assert view.dtype == np.uint8 and view.ndim == 3 and view.shape[2] == 3
    assert max(view.shape[:2]) == 300
    np.testing.assert_array_equal(gray, original)


def test_render_view_keeps_aspect_ratio():
    gray = np.zeros((100, 400), dtype=np.uint8)

    view = viewer.render_view(gray, (0, 0, 400, 100), display_side=200)

    assert view.shape == (50, 200, 3)


def test_render_view_draws_roi_only_when_visible():
    gray = np.zeros((100, 100), dtype=np.uint8)
    roi = {"x": 10, "y": 10, "width": 20, "height": 20}
    color = np.array(viewer.ROI_COLOR, dtype=np.uint8)

    visible = viewer.render_view(gray, (0, 0, 50, 50), roi, display_side=100)
    hidden = viewer.render_view(gray, (50, 50, 100, 100), roi, display_side=100)
    none = viewer.render_view(gray, (0, 0, 50, 50), None, display_side=100)

    assert (visible == color).all(axis=2).any()
    assert not (hidden == color).all(axis=2).any()
    assert not (none == color).all(axis=2).any()
    # 사각형 왼쪽 위 꼭짓점: 원본 (10, 10) → 2배 확대 화면 (20, 20)
    assert (visible[20, 20] == color).all()
    assert (visible[15, 15] == 0).all()


def test_render_view_draws_partially_visible_roi_without_error():
    gray = np.zeros((100, 100), dtype=np.uint8)
    roi = {"x": 0, "y": 0, "width": 100, "height": 100}          # 보이는 범위보다 큰 ROI

    view = viewer.render_view(gray, (40, 40, 60, 60), roi, display_side=100)

    assert view.shape == (100, 100, 3)


# ---------------------------------------------------------------------------
# ROI 기본값·통계 표
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", [(256, 256), (32, 32), (2007, 1721), (33, 97), (1, 1)])
def test_default_roi_is_valid_for_get_roi_stats(shape):
    from src.processing.roi import get_roi_stats

    gray = np.zeros(shape, dtype=np.uint8)
    roi = viewer.default_roi(shape)

    assert get_roi_stats(gray, roi)["pixel_count"] == roi["width"] * roi["height"]


def test_stats_table_markdown_labels_each_target(samples):
    from src.processing.roi import get_roi_stats

    roi = {"x": 0, "y": 0, "width": 16, "height": 16}
    original = get_roi_stats(samples["normal"], roi)
    processed = get_roi_stats(apply_clahe(samples["normal"]), roi)

    table = viewer.stats_table_markdown({"원본": original, "처리 결과 (clahe)": processed})

    lines = table.splitlines()
    assert lines[0] == "| 항목 | 원본 | 처리 결과 (clahe) |"
    assert len(lines) == 2 + 6
    assert f'| 평균 | {original["mean"]:.2f} | {processed["mean"]:.2f} |' in lines
    assert "| 픽셀 수 | 256 | 256 |" in lines


# ---------------------------------------------------------------------------
# 탭 화면 (개발 모드, streamlit AppTest)
#
# 탭만 따로 실행한다: AppTest(1.32)는 format_func가 있는 선택 상자(케이스 목록 탭)의 값을
# 다음 실행에 그대로 넘기지 못한다. 앱 전체에서 탭이 뜨는지는 test_integration.py가 확인한다.
# ---------------------------------------------------------------------------

VIEWER_SCRIPT = """
import streamlit as st
from src.ui import viewer
st.session_state.setdefault("auth_user", {"uid": "dev-admin", "role": "admin"})
{setup}
viewer.render()
"""
SELECT_NORMAL = 'st.session_state.setdefault("selected_case_id", "case_dev_normal")'


def run_viewer(setup: str = SELECT_NORMAL) -> AppTest:
    return AppTest.from_string(VIEWER_SCRIPT.replace("{setup}", setup), default_timeout=30).run()


@pytest.fixture
def dev_viewer(monkeypatch):
    """개발 모드에서 normal 샘플 케이스를 고른 뷰어 탭."""
    monkeypatch.setenv("APP_ENV", "development")
    at = run_viewer()
    assert not at.exception
    return at


def _texts(at) -> str:
    parts = [e.value for e in [*at.markdown, *at.caption, *at.info, *at.error, *at.success]]
    return "\n".join(str(p) for p in parts)


def test_viewer_asks_to_select_case_when_nothing_selected():
    at = run_viewer(setup="")

    assert not at.exception
    assert [e.value for e in at.info] == ["케이스 목록 탭에서 케이스를 먼저 선택해 주세요."]


def test_viewer_tab_shows_original_and_roi_stats(dev_viewer):
    at = dev_viewer

    assert "viewer_result" not in at.session_state
    assert at.session_state["viewer_cache"]["image_id"] == "img_dev_normal"
    text = _texts(at)
    assert "| 항목 | 원본 |" in text                       # 통계 대상이 원본임을 표시
    assert "'처리 적용'을 누르면" in text
    assert at.number_input(key="roi_width").value == 128   # 256×256 샘플의 가운데 절반


@pytest.mark.parametrize("algorithm", ["clahe", "gaussian", "median"])
def test_viewer_applies_each_algorithm(dev_viewer, algorithm):
    at = dev_viewer
    at.selectbox(key="viewer_algorithm").set_value(viewer.ALGORITHM_LABELS[algorithm]).run()
    at.button(key="viewer_apply").click().run()

    assert not at.exception
    result = at.session_state["viewer_result"]
    original = at.session_state["viewer_cache"]["gray"]
    assert result["algorithm"] == algorithm
    assert result["params"] == viewer.DEFAULT_PARAMS[algorithm]
    assert result["gray"].shape == original.shape and result["gray"].dtype == np.uint8
    np.testing.assert_array_equal(original, cases.load_image("img_dev_normal"))   # 원본 불변
    assert f"| 항목 | 원본 | 처리 결과 ({algorithm}) |" in _texts(at)


def test_viewer_uses_changed_params_and_clear_removes_result(dev_viewer):
    at = dev_viewer
    at.slider(key="viewer_clahe_clip").set_value(4.0).run()
    at.slider(key="viewer_clahe_tiles").set_value(4).run()
    at.button(key="viewer_apply").click().run()

    result = at.session_state["viewer_result"]
    assert result["params"] == {"clip_limit": 4.0, "tile_grid_size": [4, 4]}
    original = at.session_state["viewer_cache"]["gray"]
    np.testing.assert_array_equal(result["gray"], apply_clahe(original, 4.0, (4, 4)))

    at.button(key="viewer_clear").click().run()
    assert "viewer_result" not in at.session_state


def test_viewer_warns_when_settings_differ_from_shown_result(dev_viewer):
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    assert "설정이 화면의 결과와 다릅니다" not in _texts(at)

    at.slider(key="viewer_clahe_clip").set_value(6.0).run()

    assert "설정이 화면의 결과와 다릅니다" in _texts(at)
    assert at.session_state["viewer_result"]["params"]["clip_limit"] == 2.0   # 다시 누르기 전에는 그대로


def test_viewer_save_shows_notice_while_storage_function_is_not_ready(dev_viewer):
    # save_processing_run은 A 담당. 아직 구현 전이면 오류 대신 안내를 보여 준다.
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    at.button(key="viewer_save").click().run()

    assert not at.exception
    assert any("save_processing_run" in e.value for e in at.info)
    assert "run_id" not in at.session_state["viewer_result"]


def test_viewer_save_passes_result_settings_and_roi(dev_viewer, monkeypatch):
    calls = []

    def fake_save(image_id, algorithm, params, processed_gray, actor_uid, roi=None):
        calls.append((image_id, algorithm, params, processed_gray, actor_uid, roi))
        return "run_test123"

    monkeypatch.setattr(cases, "save_processing_run", fake_save)
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    at.button(key="viewer_save").click().run()

    assert not at.exception
    image_id, algorithm, params, processed, actor_uid, roi = calls[0]
    assert (image_id, algorithm, actor_uid) == ("img_dev_normal", "clahe", "dev-admin")
    assert params == viewer.DEFAULT_PARAMS["clahe"]
    assert processed.dtype == np.uint8 and processed.shape == (256, 256)
    assert roi == {"x": 64, "y": 64, "width": 128, "height": 128}
    assert any("run_test123" in e.value for e in at.success)

    at.run()                                               # 저장한 결과는 다시 저장하지 않는다
    assert len(calls) == 1
    assert "저장된 처리 기록: run_test123" in _texts(at)
    assert not [b for b in at.button if b.key == "viewer_save"]


@pytest.mark.parametrize("error", [
    PermissionDeniedError("처리 결과를 저장할 권한이 없습니다."),
    StorageError("처리 결과를 저장하지 못했습니다."),
])
def test_viewer_shows_error_when_save_fails(dev_viewer, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(cases, "save_processing_run", fail)
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    at.button(key="viewer_save").click().run()

    assert not at.exception
    assert [e.value for e in at.error] == [str(error)]
    assert "run_id" not in at.session_state["viewer_result"]


def test_viewer_zoom_pan_and_reset(dev_viewer):
    at = dev_viewer
    at.slider(key="viewer_zoom").set_value(4.0).run()
    at.slider(key="viewer_pan_x").set_value(0).run()

    assert not at.exception
    assert "표시 범위: x 0–63, y 96–159 (배율 4.0×)" in _texts(at)

    at.button(key="viewer_reset_view").click().run()
    assert at.slider(key="viewer_zoom").value == 1.0
    assert at.slider(key="viewer_pan_x").value == 50
    assert "표시 범위: x 0–255, y 0–255 (배율 1.0×)" in _texts(at)


def test_viewer_shows_error_for_roi_outside_image_and_reset_recovers(dev_viewer):
    at = dev_viewer
    at.number_input(key="roi_x").set_value(200).run()      # 200 + 128 > 256

    assert not at.exception
    assert any("ROI가 영상 범위를 벗어났습니다" in e.value for e in at.error)
    assert "| 항목 | 원본 |" not in _texts(at)

    at.button(key="roi_reset").click().run()
    assert len(at.error) == 0
    assert at.number_input(key="roi_x").value == 64


def test_viewer_resets_result_view_and_roi_when_case_changes(dev_viewer):
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    at.number_input(key="roi_x").set_value(10).run()
    at.slider(key="viewer_zoom").set_value(2.0).run()
    assert "viewer_result" in at.session_state

    at.session_state["selected_case_id"] = "case_dev_dark"   # 케이스 목록 탭에서 다른 케이스 선택
    at.run()

    assert not at.exception
    assert "viewer_result" not in at.session_state
    assert at.session_state["viewer_cache"]["image_id"] == "img_dev_dark"
    assert at.number_input(key="roi_x").value == 64
    assert at.slider(key="viewer_zoom").value == 1.0


@pytest.mark.parametrize("error", [
    PermissionDeniedError("이 케이스를 볼 권한이 없습니다."),
    NotFoundError("케이스를 찾을 수 없습니다."),
])
def test_viewer_shows_error_when_case_cannot_be_loaded(monkeypatch, error):
    def fail(case_id, *, actor_uid):
        raise error

    monkeypatch.setattr(cases, "load_case", fail)
    at = run_viewer()

    assert not at.exception
    assert [e.value for e in at.error] == [str(error)]
    assert "viewer_cache" not in at.session_state          # 권한 없는 영상은 불러오지 않는다


def test_viewer_shows_error_when_image_cannot_be_loaded(monkeypatch):
    def missing(image_id):
        raise NotFoundError("영상을 찾을 수 없습니다.")

    monkeypatch.setattr(cases, "load_case", lambda case_id, *, actor_uid: {"case_id": case_id, "image_id": "img_x"})
    monkeypatch.setattr(cases, "load_image", missing)
    at = run_viewer()

    assert not at.exception
    assert [e.value for e in at.error] == ["영상을 찾을 수 없습니다."]


def test_viewer_passes_logged_in_uid_to_load_case(monkeypatch):
    seen = []

    def record(case_id, *, actor_uid):
        seen.append((case_id, actor_uid))
        raise NotFoundError("케이스를 찾을 수 없습니다.")

    monkeypatch.setattr(cases, "load_case", record)
    run_viewer()

    assert seen == [("case_dev_normal", "dev-admin")]


def test_viewer_handles_large_non_square_image(monkeypatch):
    gray = np.random.default_rng(0).integers(0, 256, size=(1200, 1700), dtype=np.uint8)
    monkeypatch.setattr(cases, "load_case", lambda case_id, *, actor_uid: {
        "case_id": case_id, "image_id": "img_big", "case_label": "BIG", "description": "<b>x</b>"})
    monkeypatch.setattr(cases, "load_image", lambda image_id: gray.copy())
    at = run_viewer()
    at.button(key="viewer_apply").click().run()

    assert not at.exception
    assert at.session_state["viewer_result"]["gray"].shape == (1200, 1700)
    assert at.number_input(key="roi_x").value == 425 and at.number_input(key="roi_height").value == 600
    assert "영상 크기 1700×1200px" in _texts(at)


# ---------------------------------------------------------------------------
# 검토에서 나온 경우: 위젯 값 유지, 중복 저장, 크기가 다른 영상 전환, ROI 사각형 범위
# ---------------------------------------------------------------------------

def test_render_view_roi_rectangle_stays_inside_roi():
    gray = np.zeros((100, 100), dtype=np.uint8)
    roi = {"x": 10, "y": 10, "width": 20, "height": 20}
    color = np.array(viewer.ROI_COLOR, dtype=np.uint8)

    view = viewer.render_view(gray, (0, 0, 50, 50), roi, display_side=100)   # 2배 확대 → 화면 20~59

    rows, cols = np.nonzero((view == color).all(axis=2))
    assert (rows.min(), rows.max(), cols.min(), cols.max()) == (20, 59, 20, 59)


def test_render_view_draws_edges_of_partially_visible_roi():
    gray = np.zeros((100, 100), dtype=np.uint8)
    roi = {"x": 30, "y": 30, "width": 60, "height": 60}          # 오른쪽·아래가 보이는 범위 밖
    color = np.array(viewer.ROI_COLOR, dtype=np.uint8)

    view = viewer.render_view(gray, (0, 0, 50, 50), roi, display_side=100)

    drawn = (view == color).all(axis=2)
    assert drawn[60, 60:].all() and drawn[60:, 60].all()          # 위·왼쪽 변만 보인다
    assert not drawn[:60, :60].any()


def test_viewer_keeps_settings_when_switching_algorithms(dev_viewer):
    at = dev_viewer
    at.slider(key="viewer_clahe_clip").set_value(4.0).run()
    at.slider(key="viewer_clahe_tiles").set_value(12).run()
    at.selectbox(key="viewer_algorithm").set_value(viewer.ALGORITHM_LABELS["gaussian"]).run()
    at.select_slider(key="viewer_gaussian_kernel").set_value(11).run()
    at.selectbox(key="viewer_algorithm").set_value(viewer.ALGORITHM_LABELS["clahe"]).run()

    assert at.slider(key="viewer_clahe_clip").value == 4.0
    assert at.slider(key="viewer_clahe_tiles").value == 12

    at.selectbox(key="viewer_algorithm").set_value(viewer.ALGORITHM_LABELS["gaussian"]).run()
    assert at.select_slider(key="viewer_gaussian_kernel").value == 11


def test_viewer_keeps_view_roi_and_algorithm_after_temporary_error(dev_viewer, monkeypatch):
    at = dev_viewer
    at.selectbox(key="viewer_algorithm").set_value(viewer.ALGORITHM_LABELS["median"]).run()
    at.button(key="viewer_apply").click().run()
    at.slider(key="viewer_zoom").set_value(4.0).run()
    at.number_input(key="roi_x").set_value(10).run()

    real_load_case = cases.load_case

    def fail(case_id, *, actor_uid):
        raise StorageError("케이스 정보를 불러오지 못했습니다.")

    monkeypatch.setattr(cases, "load_case", fail)
    at.run()
    assert [e.value for e in at.error] == ["케이스 정보를 불러오지 못했습니다."]

    monkeypatch.setattr(cases, "load_case", real_load_case)
    at.run()

    assert not at.exception and len(at.error) == 0
    assert at.slider(key="viewer_zoom").value == 4.0
    assert at.number_input(key="roi_x").value == 10
    assert at.selectbox(key="viewer_algorithm").value == viewer.ALGORITHM_LABELS["median"]
    assert at.session_state["viewer_result"]["algorithm"] == "median"


def test_viewer_does_not_save_same_result_twice(dev_viewer, monkeypatch):
    calls = []

    def fake_save(image_id, algorithm, params, processed_gray, actor_uid, roi=None):
        calls.append(params)
        return f"run_{len(calls)}"

    monkeypatch.setattr(cases, "save_processing_run", fake_save)
    at = dev_viewer
    at.button(key="viewer_apply").click().run()
    at.button(key="viewer_save").click().run()
    at.button(key="viewer_apply").click().run()               # 같은 설정으로 다시 적용

    assert at.session_state["viewer_result"]["run_id"] == "run_1"
    assert not [b for b in at.button if b.key == "viewer_save"]

    at.slider(key="viewer_clahe_clip").set_value(3.0).run()   # 설정을 바꿔 적용하면 새 결과
    at.button(key="viewer_apply").click().run()
    assert "run_id" not in at.session_state["viewer_result"]
    at.button(key="viewer_save").click().run()
    assert len(calls) == 2


def test_viewer_switches_between_images_of_different_sizes(monkeypatch):
    images = {
        "img_big": np.random.default_rng(0).integers(0, 256, size=(600, 900), dtype=np.uint8),
        "img_tiny": np.random.default_rng(1).integers(0, 256, size=(40, 33), dtype=np.uint8),
    }
    monkeypatch.setattr(cases, "load_case", lambda case_id, *, actor_uid: {
        "case_id": case_id, "image_id": case_id.replace("case_", "img_")})
    monkeypatch.setattr(cases, "load_image", lambda image_id: images[image_id].copy())

    at = run_viewer('st.session_state.setdefault("selected_case_id", "case_big")')
    at.button(key="viewer_apply").click().run()
    at.number_input(key="roi_x").set_value(800).run()        # 작은 영상에서는 범위 밖인 값
    at.number_input(key="roi_width").set_value(50).run()
    at.slider(key="viewer_zoom").set_value(8.0).run()
    assert not at.exception

    at.session_state["selected_case_id"] = "case_tiny"
    at.run()

    assert not at.exception and len(at.error) == 0
    assert "viewer_result" not in at.session_state
    assert at.number_input(key="roi_x").value == 8 and at.number_input(key="roi_width").value == 16
    assert at.slider(key="viewer_zoom").value == 1.0
    assert "영상 크기 33×40px" in _texts(at)

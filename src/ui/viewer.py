"""영상 뷰어·ROI 탭 (B 소유, TEAM_CONTRACT §7). app.py와 다른 탭에는 render()만 내보낸다.
(그 밖의 함수·상수는 이 파일과 tests/test_viewer.py에서만 쓴다.)

보여 주는 것 (§7): 원본/결과 나란히, 알고리즘 선택, 처리 설정, 확대·축소/이동/초기화,
ROI 좌표·크기, 평균·분산·히스토그램.

데이터 흐름
1. 케이스 목록 탭이 고른 `st.session_state["selected_case_id"]`로 `load_case`를 부른다.
   조회 권한(§6.1)은 A의 함수가 검사하므로, 여기서는 받은 케이스의 `image_id`만 쓴다.
2. `load_image(image_id)`로 받은 (H,W) uint8 원본에 CLAHE(B)·Gaussian(C)·Median(D) 중
   하나를 적용한다. 원본 배열은 바꾸지 않고, 결과는 세션에만 둔다.
3. "처리 결과 저장"을 누르면 `save_processing_run`으로 결과와 설정을 남긴다.
4. ROI는 **원본 해상도 좌표**로 입력받아 `get_roi_stats`에 넘긴다. 통계 표는 원본과
   처리 결과를 열로 나눠 어느 영상의 값인지 항상 표시한다.

확대·이동·ROI 선택 방식 (§7): Streamlit 1.32에 영상 위 드래그 기능이 없고 새 라이브러리를
추가하지 않기 위해, 계약서의 대체안(좌표 입력 + 영상 위 사각형 표시)을 쓴다. 확대·이동은
보이는 범위를 잘라서 그리는 방식이고, 원본과 결과에 같은 범위를 적용한다.

화면 계산 함수(보이는 범위, ROI 그리기 등)는 Streamlit을 쓰지 않아 테스트에서 바로 부를 수 있다.
`st.session_state` 키는 `viewer_`·`roi_` 접두사만 쓴다 (§7).
"""

import html

import cv2
import numpy as np
import streamlit as st

from src.errors import AppError, ValidationError
from src.processing.clahe import apply_clahe
from src.processing.gaussian import apply_gaussian
from src.processing.median import apply_median
from src.processing.roi import get_roi_stats
from src.services import cases
from src.ui import style

# ---------------------------------------------------------------------------
# 화면 설정값 (Streamlit 없이 쓰는 값)
# ---------------------------------------------------------------------------

#: 처리 이력(processing_runs)의 algorithm 값 → 화면 표시 이름
ALGORITHM_LABELS = {
    "clahe": "CLAHE (국소 대비 개선)",
    "gaussian": "Gaussian 블러 (잡음 완화)",
    "median": "Median 필터 (점 잡음 제거)",
}

ALGORITHM_HELP = {
    "clahe": "영상을 격자로 나눠 칸마다 대비를 높입니다. 어둡거나 대비가 낮은 영상에 씁니다. "
             "균일한 영역의 잡음도 함께 강조될 수 있습니다.",
    "gaussian": "주변 픽셀과 가중 평균을 내 고르게 퍼진 잡음을 줄입니다. 경계도 함께 흐려집니다.",
    "median": "주변 픽셀의 중간값으로 바꿔 소금·후추 같은 점 잡음을 지웁니다. "
              "커널이 크면 가는 구조가 사라질 수 있습니다.",
}

#: 알고리즘별 기본 설정 (TEAM_CONTRACT §4의 함수 기본값과 같다)
DEFAULT_PARAMS = {
    "clahe": {"clip_limit": 2.0, "tile_grid_size": [8, 8]},
    "gaussian": {"kernel_size": 5, "sigma": 0.0},
    "median": {"kernel_size": 5},
}

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 8.0, 0.5
PAN_CENTER = 50             # 이동 슬라이더 값(%) — 50이 가운데
DISPLAY_SIDE = 720          # 화면에 그리는 영상의 긴 변(px). 통계·처리는 원본 해상도로 한다
ROI_COLOR = (255, 176, 32)  # 영상 위 ROI 사각형 색 (RGB, 주황)

_GAUSSIAN_KERNELS = [3, 5, 7, 9, 11, 13, 15]
_MEDIAN_KERNELS = [3, 5, 7, 9, 11]

EDUCATION_NOTE = (
    "교육용 시연 기능입니다. 처리 결과는 보기 편하게 바꾼 영상일 뿐 원본을 대체하지 않으며, "
    "원본 파일은 덮어쓰지 않습니다. 화면에서 좋아 보인다고 진단 성능이 좋아졌다는 뜻은 아닙니다."
)


def run_algorithm(gray: np.ndarray, algorithm: str, params: dict) -> np.ndarray:
    """알고리즘 이름과 설정 dict로 담당 함수를 호출한다. 결과는 새 (H,W) uint8 배열.

    params는 processing_runs에 그대로 저장되는 형식(JSON으로 바꿀 수 있는 값)이다.
    모르는 알고리즘이나 빠진 설정은 ValidationError.
    """
    if not isinstance(params, dict):
        raise ValidationError("처리 설정 형식이 올바르지 않습니다.")
    try:
        if algorithm == "clahe":
            tiles = params["tile_grid_size"]
            if not isinstance(tiles, (tuple, list)):
                raise ValidationError("tile_grid_size는 (가로 칸 수, 세로 칸 수) 두 정수여야 합니다.")
            return apply_clahe(gray, clip_limit=params["clip_limit"], tile_grid_size=tuple(tiles))
        if algorithm == "gaussian":
            return apply_gaussian(gray, kernel_size=params["kernel_size"], sigma=params["sigma"])
        if algorithm == "median":
            return apply_median(gray, kernel_size=params["kernel_size"])
    except KeyError as err:
        raise ValidationError(f"처리 설정에 {err.args[0]} 값이 없습니다.") from err
    raise ValidationError(f"알 수 없는 알고리즘입니다: {algorithm}")


def params_summary(algorithm: str, params: dict) -> str:
    """처리 설정을 화면 설명 한 줄로 바꾼다 (예: 'clip_limit 2.0 · 격자 8×8')."""
    if algorithm == "clahe":
        tiles_x, tiles_y = params["tile_grid_size"]
        return f'clip_limit {float(params["clip_limit"]):.1f} · 격자 {tiles_x}×{tiles_y}'
    if algorithm == "gaussian":
        sigma = float(params["sigma"])
        sigma_text = "자동" if sigma == 0 else f"{sigma:.1f}"
        return f'kernel_size {params["kernel_size"]} · sigma {sigma_text}'
    if algorithm == "median":
        return f'kernel_size {params["kernel_size"]}'
    return ""


def view_window(shape: tuple[int, int], zoom: float = 1.0,
                pan_x: float = 0.5, pan_y: float = 0.5) -> tuple[int, int, int, int]:
    """확대 배율과 이동 위치로 화면에 보일 원본 좌표 범위 (x0, y0, x1, y1)를 구한다 (반열림).

    zoom은 1 이상(1이면 전체), pan_x·pan_y는 0~1 (0=왼쪽/위 끝, 0.5=가운데, 1=오른쪽/아래 끝).
    범위는 항상 영상 안에 있고 최소 1픽셀이다.
    """
    height, width = int(shape[0]), int(shape[1])
    zoom = max(1.0, float(zoom))
    pan_x = min(1.0, max(0.0, float(pan_x)))
    pan_y = min(1.0, max(0.0, float(pan_y)))
    win_w = min(width, max(1, round(width / zoom)))
    win_h = min(height, max(1, round(height / zoom)))
    x0 = round((width - win_w) * pan_x)
    y0 = round((height - win_h) * pan_y)
    return x0, y0, x0 + win_w, y0 + win_h


def render_view(gray: np.ndarray, window: tuple[int, int, int, int],
                roi: dict | None = None, display_side: int = DISPLAY_SIDE) -> np.ndarray:
    """보이는 범위를 잘라 화면용 RGB 영상으로 만들고, ROI가 있으면 사각형을 그린다.

    입력 영상은 바꾸지 않는다. 긴 변을 display_side에 맞추며, 확대할 때는 픽셀을 섞지 않고
    (INTER_NEAREST) 실제 픽셀이 그대로 보이게 한다. ROI는 원본 좌표 dict이고, 보이는 범위
    밖에 있으면 그리지 않는다.
    """
    x0, y0, x1, y1 = window
    crop = gray[y0:y1, x0:x1]
    crop_h, crop_w = crop.shape
    scale = display_side / max(crop_h, crop_w)
    out_w, out_h = max(1, round(crop_w * scale)), max(1, round(crop_h * scale))
    interpolation = cv2.INTER_NEAREST if scale >= 1 else cv2.INTER_AREA
    view = cv2.cvtColor(cv2.resize(crop, (out_w, out_h), interpolation=interpolation), cv2.COLOR_GRAY2RGB)

    if roi is not None:
        left, top = roi["x"], roi["y"]
        right, bottom = left + roi["width"], top + roi["height"]
        if left < x1 and right > x0 and top < y1 and bottom > y0:  # 보이는 범위와 겹칠 때만
            sx, sy = out_w / crop_w, out_h / crop_h
            pt1 = (round((left - x0) * sx), round((top - y0) * sy))
            pt2 = (round((right - x0) * sx) - 1, round((bottom - y0) * sy) - 1)
            # 두께 2를 한 번에 그리면 선이 ROI 바깥으로 번지므로, 1픽셀 선을 안쪽으로 두 겹 그린다.
            cv2.rectangle(view, pt1, pt2, ROI_COLOR, thickness=1)
            if pt2[0] - pt1[0] >= 2 and pt2[1] - pt1[1] >= 2:
                cv2.rectangle(view, (pt1[0] + 1, pt1[1] + 1), (pt2[0] - 1, pt2[1] - 1), ROI_COLOR, thickness=1)
    return view


def default_roi(shape: tuple[int, int]) -> dict:
    """영상 가운데 절반 크기의 기본 ROI."""
    height, width = int(shape[0]), int(shape[1])
    roi_w, roi_h = max(1, width // 2), max(1, height // 2)
    return {"x": (width - roi_w) // 2, "y": (height - roi_h) // 2, "width": roi_w, "height": roi_h}


def stats_table_markdown(columns: dict[str, dict]) -> str:
    """{'열 이름': get_roi_stats 결과} → markdown 표. 열 이름으로 통계 대상을 구분한다."""
    names = list(columns)
    rows = [
        ("평균", lambda s: f'{s["mean"]:.2f}'),
        ("분산 (모집단)", lambda s: f'{s["variance"]:.2f}'),
        ("표준편차", lambda s: f'{s["std"]:.2f}'),
        ("최소", lambda s: str(s["min"])),
        ("최대", lambda s: str(s["max"])),
        ("픽셀 수", lambda s: f'{s["pixel_count"]:,}'),
    ]
    lines = ["| 항목 | " + " | ".join(html.escape(name) for name in names) + " |",
             "|---|" + "---:|" * len(names)]
    for label, fmt in rows:
        lines.append(f"| {label} | " + " | ".join(fmt(columns[name]) for name in names) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------

_STATE_PREFIXES = ("viewer_", "roi_")


def _load_original(image_id: str) -> np.ndarray:
    """선택 영상의 원본. 같은 영상이면 다시 내려받지 않는다.

    Streamlit은 위젯을 건드릴 때마다 모든 탭을 다시 그리므로 `viewer_cache`에 둔다.
    영상이 바뀌면 이전 처리 결과·보기 설정·ROI를 모두 지운다 (§7).
    """
    cache = st.session_state.get("viewer_cache")
    if cache and cache["image_id"] == image_id:
        return cache["gray"]
    for key in [k for k in st.session_state if isinstance(k, str) and k.startswith(_STATE_PREFIXES)]:
        del st.session_state[key]
    gray = cases.load_image(image_id)
    st.session_state["viewer_cache"] = {"image_id": image_id, "gray": gray}
    return gray


#: 값을 보관하는 위젯 키. Streamlit은 한 번이라도 그려지지 않은 위젯의 값을 지우므로
#: (알고리즘을 바꿨을 때의 다른 알고리즘 슬라이더, 오류로 화면을 못 그린 실행 등),
#: `viewer_keep`에 따로 적어 두었다가 다시 그릴 때 되돌린다.
_KEPT_KEYS = (
    "viewer_algorithm", "viewer_clahe_clip", "viewer_clahe_tiles", "viewer_gaussian_kernel",
    "viewer_gaussian_sigma", "viewer_median_kernel", "viewer_zoom", "viewer_pan_x", "viewer_pan_y",
    "roi_x", "roi_y", "roi_width", "roi_height",
)


def _restore(key: str, default) -> None:
    """위젯을 그리기 전에 부른다. 세션에 값이 없으면 보관해 둔 값(없으면 기본값)을 넣는다."""
    if key not in st.session_state:
        st.session_state[key] = st.session_state.get("viewer_keep", {}).get(key, default)


def _remember() -> None:
    """이번 실행에서 그린 위젯 값을 보관한다."""
    keep = dict(st.session_state.get("viewer_keep", {}))
    for key in _KEPT_KEYS:
        if key in st.session_state:
            keep[key] = st.session_state[key]
    st.session_state["viewer_keep"] = keep


def _reset_view() -> None:
    """보기 초기화 버튼의 on_click 콜백 (위젯이 그려지기 전에 실행된다)."""
    st.session_state["viewer_zoom"] = ZOOM_MIN
    st.session_state["viewer_pan_x"] = PAN_CENTER
    st.session_state["viewer_pan_y"] = PAN_CENTER


def _reset_roi(shape: tuple[int, int]) -> None:
    """ROI 초기화 버튼의 on_click 콜백."""
    for key, value in default_roi(shape).items():
        st.session_state[f"roi_{key}"] = value


def _clear_result() -> None:
    st.session_state.pop("viewer_result", None)


def _algorithm_controls() -> tuple[str, dict]:
    """알고리즘 선택과 설정 위젯. 반환: (algorithm, params)."""
    # 선택 상자에는 화면 이름을 그대로 넣고, 고른 이름을 알고리즘 코드로 되돌린다.
    by_label = {label: name for name, label in ALGORITHM_LABELS.items()}
    _restore("viewer_algorithm", next(iter(by_label)))
    algorithm = by_label[st.selectbox("알고리즘", options=list(by_label), key="viewer_algorithm")]
    st.caption(ALGORITHM_HELP[algorithm])
    defaults = DEFAULT_PARAMS[algorithm]

    if algorithm == "clahe":
        _restore("viewer_clahe_clip", defaults["clip_limit"])
        _restore("viewer_clahe_tiles", defaults["tile_grid_size"][0])
        clip_limit = st.slider("clip_limit (대비 상한)", 0.5, 10.0, step=0.5, key="viewer_clahe_clip",
                               help="클수록 대비가 강해지고 잡음도 같이 커집니다.")
        tiles = st.slider("격자 수 (가로·세로)", 2, 16, step=1, key="viewer_clahe_tiles",
                          help="영상을 나누는 칸 수입니다. 클수록 더 좁은 영역 기준으로 대비를 맞춥니다.")
        return algorithm, {"clip_limit": float(clip_limit), "tile_grid_size": [int(tiles), int(tiles)]}

    if algorithm == "gaussian":
        _restore("viewer_gaussian_kernel", defaults["kernel_size"])
        _restore("viewer_gaussian_sigma", defaults["sigma"])
        kernel = st.select_slider("kernel_size (홀수)", options=_GAUSSIAN_KERNELS, key="viewer_gaussian_kernel")
        sigma = st.slider("sigma (0 = 자동)", 0.0, 5.0, step=0.1, key="viewer_gaussian_sigma",
                          help="클수록 더 흐려집니다. 0이면 kernel_size에 맞춰 자동으로 정합니다.")
        return algorithm, {"kernel_size": int(kernel), "sigma": float(sigma)}

    _restore("viewer_median_kernel", defaults["kernel_size"])
    kernel = st.select_slider("kernel_size (3 이상 홀수)", options=_MEDIAN_KERNELS, key="viewer_median_kernel")
    return algorithm, {"kernel_size": int(kernel)}


def _view_controls(shape: tuple[int, int]) -> tuple[int, int, int, int]:
    """확대·이동·초기화 위젯. 반환: 보이는 범위 (x0, y0, x1, y1)."""
    _restore("viewer_zoom", ZOOM_MIN)
    _restore("viewer_pan_x", PAN_CENTER)
    _restore("viewer_pan_y", PAN_CENTER)

    zoom = st.slider("확대 배율", ZOOM_MIN, ZOOM_MAX, step=ZOOM_STEP, format="%.1f×", key="viewer_zoom")
    can_pan = zoom > ZOOM_MIN
    pan_x = st.slider("가로 이동 (왼쪽 ↔ 오른쪽)", 0, 100, step=1, key="viewer_pan_x", disabled=not can_pan)
    pan_y = st.slider("세로 이동 (위 ↔ 아래)", 0, 100, step=1, key="viewer_pan_y", disabled=not can_pan)
    st.button("보기 초기화", key="viewer_reset_view", on_click=_reset_view)
    return view_window(shape, zoom, pan_x / 100, pan_y / 100)


def _roi_controls(shape: tuple[int, int]) -> dict:
    """ROI 좌표 입력 위젯 (원본 해상도 좌표). 반환: roi dict (검증은 get_roi_stats가 한다)."""
    height, width = shape
    for key, value in default_roi(shape).items():
        _restore(f"roi_{key}", value)

    col_x, col_y, col_w, col_h, col_reset = st.columns([1, 1, 1, 1, 1])
    with col_x:
        x = st.number_input("x (왼쪽)", min_value=0, max_value=width - 1, step=1, key="roi_x")
    with col_y:
        y = st.number_input("y (위)", min_value=0, max_value=height - 1, step=1, key="roi_y")
    with col_w:
        roi_w = st.number_input("가로 크기", min_value=1, max_value=width, step=1, key="roi_width")
    with col_h:
        roi_h = st.number_input("세로 크기", min_value=1, max_value=height, step=1, key="roi_height")
    with col_reset:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)  # 입력칸과 줄 맞춤
        st.button("ROI 초기화", key="roi_reset", on_click=_reset_roi, args=(shape,))
    return {"x": int(x), "y": int(y), "width": int(roi_w), "height": int(roi_h)}


def _save_result(image_id: str, result: dict, actor_uid: str, roi: dict | None) -> None:
    """처리 결과와 설정을 A의 save_processing_run으로 저장한다."""
    try:
        run_id = cases.save_processing_run(
            image_id, result["algorithm"], result["params"], result["gray"], actor_uid, roi=roi,
        )
    except NotImplementedError:
        st.info("처리 결과 저장(save_processing_run)은 A 담당 함수가 구현되면 연결됩니다. "
                "지금은 화면에서만 결과를 볼 수 있습니다.")
        return
    except Exception as err:  # AppError는 한국어 안내, 그 밖의 오류는 로그 + 일반 메시지
        style.show_app_error(err)
        return
    result["run_id"] = run_id
    st.success(f"처리 결과를 저장했습니다 ({run_id}).")


def render() -> None:
    style.page_header("영상 뷰어·ROI", "원본/처리 결과 비교와 ROI 통계 (교육용)")

    case_id = st.session_state.get("selected_case_id")
    if not case_id:
        st.info("케이스 목록 탭에서 케이스를 먼저 선택해 주세요.")
        return
    actor_uid = st.session_state.get("auth_user", {}).get("uid", "")

    try:
        case = cases.load_case(case_id, actor_uid=actor_uid)
        image_id = case.get("image_id")
        if not image_id:
            st.info("이 케이스에는 표시할 영상이 없습니다.")
            return
        gray = _load_original(image_id)
    except Exception as err:  # AppError는 한국어 안내, 그 밖의 오류는 로그 + 일반 메시지 (§4)
        style.show_app_error(err)
        return

    height, width = gray.shape
    st.markdown(
        f'**{html.escape(str(case.get("case_label", case_id)))}** · '
        f'{html.escape(str(case.get("description", "")))} · 영상 크기 {width}×{height}px'
    )

    controls, images = st.columns([1, 3])

    # ── 왼쪽: 처리 설정과 보기 설정 ───────────────────────────────────────────
    with controls:
        st.markdown("**영상처리**")
        algorithm, params = _algorithm_controls()
        apply_col, clear_col = st.columns(2)
        with apply_col:
            apply_clicked = st.button("처리 적용", type="primary", key="viewer_apply")
        with clear_col:
            st.button("결과 지우기", key="viewer_clear", on_click=_clear_result)
        if apply_clicked:
            previous = st.session_state.get("viewer_result") or {}
            same = (previous.get("image_id"), previous.get("algorithm"), previous.get("params")) == (
                image_id, algorithm, params)
            try:
                st.session_state["viewer_result"] = {
                    "image_id": image_id,
                    "algorithm": algorithm,
                    "params": params,
                    "gray": run_algorithm(gray, algorithm, params),
                }
                if same and previous.get("run_id"):  # 같은 결과를 두 번 저장하지 않게 한다
                    st.session_state["viewer_result"]["run_id"] = previous["run_id"]
            except Exception as err:
                st.session_state.pop("viewer_result", None)
                style.show_app_error(err)

        st.markdown("**보기**")
        window = _view_controls(gray.shape)

    result = st.session_state.get("viewer_result")
    if result and result.get("image_id") != image_id:  # 다른 영상의 결과는 쓰지 않는다
        result = None

    # ── ROI 입력 (영상 위 사각형을 그리려면 영상보다 먼저 값을 읽어야 한다) ──────
    roi_box = st.container()
    with roi_box:
        st.markdown("**ROI 분석** — 좌표는 원본 해상도 기준이며 왼쪽 위가 (0, 0)입니다.")
        roi = _roi_controls(gray.shape)
    _remember()

    stats, roi_error = {}, None
    try:
        stats["원본"] = get_roi_stats(gray, roi)
        if result:
            stats[f'처리 결과 ({result["algorithm"]})'] = get_roi_stats(result["gray"], roi)
    except AppError as err:
        stats, roi_error = {}, err
    drawn_roi = roi if roi_error is None else None

    # ── 오른쪽: 원본 / 처리 결과 나란히 ───────────────────────────────────────
    with images:
        x0, y0, x1, y1 = window
        left, right = st.columns(2)
        with left:
            st.image(render_view(gray, window, drawn_roi), caption="원본", use_column_width=True)
        with right:
            if result:
                caption = (f'처리 결과 — {ALGORITHM_LABELS[result["algorithm"]]} · '
                           f'{params_summary(result["algorithm"], result["params"])}')
                st.image(render_view(result["gray"], window, drawn_roi), caption=caption,
                         use_column_width=True)
            else:
                st.info("알고리즘과 설정을 고른 뒤 '처리 적용'을 누르면 여기에 결과가 나옵니다.")
        # 범위 표기는 "–"를 쓴다: markdown에서 물결표 두 개는 취소선으로 바뀐다.
        st.caption(
            f"표시 범위: x {x0}–{x1 - 1}, y {y0}–{y1 - 1} "
            f"(배율 {st.session_state['viewer_zoom']:.1f}×) · 주황 사각형 = ROI · "
            "원본과 결과에 같은 범위가 적용됩니다."
        )

        if result:
            if (result["algorithm"], result["params"]) != (algorithm, params):
                st.caption("⚠️ 왼쪽 설정이 화면의 결과와 다릅니다. '처리 적용'을 누르면 새 설정으로 다시 계산합니다.")
            if result.get("run_id"):
                st.caption(f'저장된 처리 기록: {result["run_id"]}')
            elif st.button("처리 결과 저장", key="viewer_save"):
                _save_result(image_id, result, actor_uid, drawn_roi)

    # ── ROI 통계 ─────────────────────────────────────────────────────────────
    with roi_box:
        if roi_error is not None:
            style.show_app_error(roi_error)
        else:
            st.caption(
                f'ROI: x={roi["x"]}, y={roi["y"]}, 가로 {roi["width"]} × 세로 {roi["height"]} '
                f'(x {roi["x"]}–{roi["x"] + roi["width"] - 1}, y {roi["y"]}–{roi["y"] + roi["height"] - 1})'
            )
            table_col, hist_col = st.columns([1, 2])
            with table_col:
                st.markdown(stats_table_markdown(stats))
                if not result:
                    st.caption("통계 대상: 원본. 처리를 적용하면 결과 영상의 통계가 옆 열에 추가됩니다.")
            with hist_col:
                for name, stat in stats.items():
                    st.caption(f"히스토그램 — {name} (가로축: 픽셀값 0–255, 세로축: 픽셀 수, 256 bin)")
                    st.bar_chart({"픽셀 수": stat["histogram"]}, height=180)

    with st.expander("이 화면의 의미와 한계"):
        st.markdown(EDUCATION_NOTE)
        st.markdown(
            "- 확대·이동은 보이는 범위만 바꾸며, 처리와 ROI 통계는 항상 원본 해상도 전체 기준으로 계산합니다.\n"
            "- ROI는 반열림 구간 `[x, x+가로) × [y, y+세로)`이고, 분산은 모집단 분산(ddof=0)입니다.\n"
            "- DICOM 영상은 표시용 8-bit 변환본을 사용합니다. 밝기·대비 조절(Window/Level)은 이번 범위 밖입니다."
        )

"""자동 점검 결과 탭 (C 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

보여 주는 것 (§7): 점수 3종, 적용 임계값, 경고 사유, 교육용 문구.

데이터 흐름
1. 케이스 목록 탭이 고른 `st.session_state["selected_case_id"]`로 `load_case`를 부른다.
   조회 권한(§6.1)은 A의 함수가 검사하므로, 여기서는 받은 케이스의 `image_id`만 쓴다.
2. 저장된 최근 점검 상태는 `load_case` 결과의 `latest_quality_status`로 보여 준다.
3. 측정값·사유는 같은 표시용 영상(`load_image`, §5)에 지금 기준(`DEFAULT_THRESHOLDS`)으로
   `check_quality`를 다시 실행해 보여 준다. 저장된 점검 기록을 읽는 함수는 아직 계약에 없다 (#45).
4. "현재 결과로 점검 기록 저장" 버튼은 `save_quality_check`로 결과를 저장한다.

화면 문구·표를 만드는 함수는 Streamlit을 쓰지 않아 테스트에서 바로 부를 수 있다.
`st.session_state` 키는 `quality_` 접두사만 쓴다 (§7).
"""

import html

import cv2
import numpy as np
import streamlit as st

from src.errors import AppError
from src.quality.checker import (
    CHECKER_VERSION,
    LOW_CONTRAST,
    POSSIBLY_BLURRY,
    REASON_LABELS,
    SHARPNESS_MAX_SIDE,
    TOO_BRIGHT,
    TOO_DARK,
    check_quality,
)
from src.quality.thresholds import DEFAULT_THRESHOLDS
from src.services import cases
from src.ui import style

# ---------------------------------------------------------------------------
# 화면 문구 (Streamlit 없이 쓰는 값)
# ---------------------------------------------------------------------------

#: 자동 점검 상태 → (화면 표시, 배지 색). 업무 상태(style.STATUS_LABELS)와 다른 값이다.
QUALITY_STATUS_LABELS = {
    "pass": ("경고 없음", "green"),
    "needs_check": ("확인 필요", "orange"),
    "error": ("점검 실패", "orange"),
}
NO_RECORD_LABEL = ("기록 없음", "gray")

#: 경고 사유마다 사용자에게 보여 줄 쉬운 설명
REASON_HELP = {
    TOO_DARK: "영상 전체의 평균 밝기가 기준보다 낮습니다. 노출이 부족했거나 저장 과정에서 어두워졌을 수 있습니다.",
    TOO_BRIGHT: "영상 전체의 평균 밝기가 기준보다 높습니다. 노출이 과했거나 저장 과정에서 밝아졌을 수 있습니다.",
    LOW_CONTRAST: "밝기가 좁은 범위에 몰려 있어 구조 사이의 차이가 잘 드러나지 않습니다.",
    POSSIBLY_BLURRY: "경계(밝기가 급하게 바뀌는 곳)가 적어 흐린 영상일 수 있습니다.",
}

EDUCATION_NOTE = (
    "교육용 시연 기능입니다. '경고 없음'은 팀이 정한 기준에서 경고가 없다는 뜻일 뿐, "
    "의학적으로 적합하다는 판정이 아닙니다. 기준값은 공개 데이터(LIDC-IDRI)와 합성 샘플로 정한 교육용 값입니다."
)

LIMITATION_NOTES = (
    f"선명도는 긴 변이 {SHARPNESS_MAX_SIDE}px보다 크면 {SHARPNESS_MAX_SIDE}px로 줄인 영상에서 잽니다 "
    "(화면에 보이는 크기 기준). 밝기·대비는 줄이지 않은 영상에서 잽니다.",
    "DICOM은 화면 표시용으로 바꿀 때 밝기 범위를 자동으로 펼치기 때문에, 노출이 잘못돼도 "
    "'어두움'·'너무 밝음'·'낮은 대비' 경고가 거의 나오지 않습니다. 이 세 경고는 주로 PNG/JPEG에서 의미가 있습니다.",
    "흐림은 인위적으로 만든 Gaussian 흐림으로만 기준을 정했습니다. 움직임으로 생긴 흐림은 확인하지 않았습니다.",
)

SMALL_IMAGE_NOTE = (
    f"이 영상은 긴 변이 {SHARPNESS_MAX_SIDE}px 이하라 줄이지 않고 그대로 쟀습니다. "
    "작은 영상은 약한 흐림을 놓칠 수 있습니다 (정상 영상을 흐림으로 잘못 판정한 경우는 확인되지 않았습니다)."
)

_THUMBNAIL_SIDE = 320  # 화면에 띄우는 미리보기 긴 변 (점검은 원래 크기로 한다)


def status_badge(status: str | None) -> str:
    """자동 점검 상태를 색 배지 HTML로 바꾼다. None이면 '기록 없음'.

    모르는 값이 와도 화면이 멈추지 않게 회색 배지에 값을 그대로(escape해서) 보여 준다.
    """
    if status is None:
        label, color = NO_RECORD_LABEL
    else:
        label, color = QUALITY_STATUS_LABELS.get(status, (str(status), "gray"))
    return f'<span class="pacs-badge {color}">{html.escape(label)}</span>'


def _fmt(value: float) -> str:
    return f"{value:.1f}"


def metric_rows(result: dict) -> list[dict]:
    """check_quality 결과 → 표 행 3개 (지표, 측정값, 기준, 판정).

    판정은 다시 계산하지 않고 result["reasons"]에서 가져온다.
    그래서 화면의 판정은 check_quality가 낸 결론과 항상 같다.
    """
    metrics, limits, reasons = result["metrics"], result["thresholds"], result["reasons"]

    def verdict(*codes: str) -> str:
        hit = [REASON_LABELS[c] for c in codes if c in reasons]
        return "⚠️ " + ", ".join(hit) if hit else "기준 안"

    return [
        {
            "metric": "밝기 평균",
            "value": _fmt(metrics["brightness_mean"]),
            "criterion": f'{_fmt(limits["brightness_min"])} 이상, {_fmt(limits["brightness_max"])} 이하',
            "verdict": verdict(TOO_DARK, TOO_BRIGHT),
        },
        {
            "metric": "대비 (밝기 표준편차)",
            "value": _fmt(metrics["contrast_std"]),
            "criterion": f'{_fmt(limits["contrast_std_min"])} 이상',
            "verdict": verdict(LOW_CONTRAST),
        },
        {
            "metric": "선명도 (Laplacian 분산)",
            "value": _fmt(metrics["laplacian_variance"]),
            "criterion": f'{_fmt(limits["laplacian_var_min"])} 이상',
            "verdict": verdict(POSSIBLY_BLURRY),
        },
    ]


def metrics_table_markdown(rows: list[dict]) -> str:
    """표 행 → markdown 표 (st.dataframe은 현재 requirements 조합에서 오류가 나서 쓰지 않는다)."""
    lines = ["| 지표 | 측정값 | 기준 | 판정 |", "|---|---:|---|---|"]
    for row in rows:
        cells = (row["metric"], row["value"], row["criterion"], row["verdict"])
        lines.append("| " + " | ".join(html.escape(c) for c in cells) + " |")
    return "\n".join(lines)


def reason_messages(reasons: list[str]) -> list[str]:
    """경고 사유 코드 → '이름: 설명' 문장 (계약 §4 순서 그대로)."""
    return [f"{REASON_LABELS.get(r, r)}: {REASON_HELP.get(r, '')}".rstrip(": ") for r in reasons]


def saved_status_message(saved_status: str | None, current_status: str) -> tuple[str, str] | None:
    """저장된 최근 점검 상태와 지금 결과를 비교한 안내 (종류, 문장). 같으면 None.

    종류는 Streamlit 표시 함수 이름: "info" 또는 "warning".
    """
    if saved_status is None:
        return ("info", "저장된 점검 기록이 없습니다. 아래 버튼으로 지금 결과를 저장할 수 있습니다.")
    if saved_status == "error":
        return ("warning", "최근 점검이 실패한 기록이 있습니다. 지금 결과를 확인한 뒤 다시 저장해 주세요.")
    if saved_status != current_status:
        return ("warning",
                f"저장된 결과({QUALITY_STATUS_LABELS.get(saved_status, (saved_status,))[0]})와 "
                f"현재 기준으로 다시 잰 결과({QUALITY_STATUS_LABELS[current_status][0]})가 다릅니다. "
                "기준값이 바뀐 뒤 저장된 기록일 수 있습니다. 확인한 뒤 다시 저장해 주세요.")
    return None


def is_small_image(shape: tuple[int, ...]) -> bool:
    """선명도를 줄이지 않고 재는 크기인지 (긴 변이 512px 이하)."""
    return max(shape[:2]) <= SHARPNESS_MAX_SIDE


def make_thumbnail(gray: np.ndarray, side: int = _THUMBNAIL_SIDE) -> np.ndarray:
    """화면 미리보기용 축소본. 점검 결과에는 쓰지 않는다 (원본을 바꾸지 않는다)."""
    height, width = gray.shape[:2]
    scale = side / max(height, width)
    if scale >= 1:
        return gray.copy()
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------

def _current_check(image_id: str) -> dict:
    """선택 영상의 현재 점검 결과. 같은 영상·같은 기준이면 다시 계산하지 않는다.

    Streamlit은 버튼을 누를 때마다 모든 탭을 다시 그리므로, 매번 영상을 내려받지 않도록
    `quality_cache`에 저장한다. 영상이나 기준 버전이 바뀌면 캐시를 버린다 (§7).
    """
    key = (image_id, DEFAULT_THRESHOLDS.get("version"), CHECKER_VERSION)
    cache = st.session_state.get("quality_cache")
    if cache and cache["key"] == key:
        return cache
    if cache and cache["key"][0] != image_id:
        st.session_state.pop("quality_notice", None)   # 다른 영상의 저장 안내는 지운다
    gray = cases.load_image(image_id)
    cache = {
        "key": key,
        "result": check_quality(gray, DEFAULT_THRESHOLDS),
        "shape": gray.shape,
        "thumbnail": make_thumbnail(gray),
    }
    st.session_state["quality_cache"] = cache
    return cache


def _save(image_id: str, result: dict, actor_uid: str) -> None:
    """저장 버튼의 on_click 콜백. 화면을 다시 그리기 전에 실행되므로, 이어서 부르는
    load_case가 방금 저장한 최근 점검 상태를 읽는다. 결과 안내는 다음 화면에서 한 번 보여 준다.
    """
    try:
        check_id = cases.save_quality_check(image_id, result, actor_uid=actor_uid)
    except AppError as err:
        st.session_state["quality_save_error"] = err
        return
    st.session_state["quality_notice"] = f"점검 기록을 저장했습니다 ({check_id})."


def render() -> None:
    style.page_header("자동 화질 점검", "밝기·대비·흐림 지표와 경고 사유 (교육용 기준)")

    case_id = st.session_state.get("selected_case_id")
    if not case_id:
        st.info("케이스 목록 탭에서 케이스를 먼저 선택해 주세요.")
        return
    actor_uid = st.session_state.get("auth_user", {}).get("uid", "")

    try:
        case = cases.load_case(case_id, actor_uid=actor_uid)
        image_id = case.get("image_id")
        if not image_id:
            st.info("이 케이스에는 점검할 영상이 없습니다.")
            return
        check = _current_check(image_id)
    except AppError as err:
        style.show_app_error(err)
        return

    result = check["result"]
    notice = st.session_state.pop("quality_notice", None)
    if notice:
        st.success(notice)
    save_error = st.session_state.pop("quality_save_error", None)
    if save_error:
        style.show_app_error(save_error)

    left, right = st.columns([1, 2])
    with left:
        st.image(check["thumbnail"], caption="점검한 표시용 영상 (미리보기)", use_column_width=True)
    with right:
        st.markdown(
            f'**{html.escape(str(case.get("case_label", case_id)))}** · '
            f'저장된 최근 점검 {status_badge(case.get("latest_quality_status"))} · '
            f'현재 기준 결과 {status_badge(result["status"])}',
            unsafe_allow_html=True,
        )
        compare = saved_status_message(case.get("latest_quality_status"), result["status"])
        if compare:
            getattr(st, compare[0])(compare[1])

        if result["reasons"]:
            for message in reason_messages(result["reasons"]):
                st.warning(message)
        else:
            st.success("팀 기준상 경고 없음 (의학적 판정 아님)")

        st.markdown(metrics_table_markdown(metric_rows(result)))
        st.caption(
            f'기준값 버전 {result["thresholds"]["version"]} · 점검 로직 버전 {result["checker_version"]} · '
            f'영상 크기 {check["shape"][1]}×{check["shape"][0]}px'
        )
        if is_small_image(check["shape"]):
            st.info(SMALL_IMAGE_NOTE)

        st.button("현재 결과로 점검 기록 저장", key="quality_save",
                  on_click=_save, args=(image_id, result, actor_uid))
        st.caption("저장하면 케이스 목록의 자동 점검 상태가 이 결과로 바뀝니다.")

    with st.expander("이 점검의 의미와 한계"):
        st.markdown(EDUCATION_NOTE)
        st.markdown("\n".join(f"- {note}" for note in LIMITATION_NOTES))

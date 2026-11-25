"""영상 등록 화면 (A 소유, TEAM_CONTRACT §7). 외부에는 render()만 내보낸다.

흐름 (§7 영상 등록):
  파일 선택 → (DICOM이면) read_tags로 검사 정보 자동 입력 → 사용자가 확인·수정
  → save_case → load_image → check_quality → save_quality_check → 결과 표시

- 권한: registrar·admin만 등록 폼을 본다. save_case 안에서도 다시 검사한다 (§6.1).
- 자동 점검이 실패해도 등록된 원본·케이스는 그대로 둔다 (§4 A·C 조율).
- C의 dicom_io·check_quality가 아직 stub이면 안내 메시지를 보여 주고, 완성되면 그대로 동작한다.
- session_state 키: register_* (이 탭 전용), selected_case_id·selected_image_id (탭 공유, §7)
"""

import streamlit as st

from src import dicom_io
from src.config import DEFAULT_THRESHOLDS
from src.errors import AppError
from src.quality.checker import check_quality
from src.services.cases import load_image, save_case, save_quality_check
from src.ui import style

REGISTER_ROLES = ("registrar", "admin")
EXAM_TYPES = ["X-ray", "CT", "MRI", "Other"]
EXAM_LABELS = {"X-ray": "X-ray", "CT": "CT", "MRI": "MRI", "Other": "기타"}
# §4: 점검 사유 코드 → 화면 표시
REASON_LABELS = {
    "too_dark": "어두움",
    "too_bright": "너무 밝음",
    "low_contrast": "낮은 대비",
    "possibly_blurry": "흐림 의심",
}


def _read_dicom_tags(name: str, data: bytes) -> tuple[dict, str | None]:
    """DICOM이면 태그로 채울 값과 안내 문구를 돌려준다. 일반 영상이면 ({}, None)."""
    if not name.lower().endswith(".dcm"):
        return {}, None
    try:
        tags = dicom_io.read_tags(data)
    except NotImplementedError:
        return {}, "DICOM 태그 자동 입력 기능이 아직 준비되지 않았습니다 (C 담당). 검사 정보를 직접 입력해 주세요."
    except AppError as err:
        return {}, f"DICOM 태그를 읽지 못했습니다: {err} 검사 정보를 직접 입력해 주세요."
    filled = {key: tags.get(key) or "" for key in ("case_label", "exam_type", "description")}
    return filled, "DICOM 태그에서 검사 정보를 자동으로 채웠습니다. 확인하고 필요하면 고쳐 주세요."


def _register_and_check(metadata: dict, data: bytes) -> dict:
    """저장 → 자동 점검까지 실행하고 결과를 돌려준다 (Streamlit을 쓰지 않아 테스트하기 쉽다).

    반환: {"case_id", "image_id", "quality": 점검 결과 dict 또는 None, "quality_error": 안내 문구 또는 None}
    등록 자체가 실패하면 AppError(또는 C 미구현 시 NotImplementedError)를 그대로 올린다.
    """
    case_id, image_id = save_case(metadata, data)
    outcome = {"case_id": case_id, "image_id": image_id, "quality": None, "quality_error": None}
    try:
        result = check_quality(load_image(image_id), DEFAULT_THRESHOLDS)
        save_quality_check(image_id, result, actor_uid=None)  # None = 등록 직후 시스템 자동 점검
        outcome["quality"] = result
    except NotImplementedError:
        outcome["quality_error"] = "자동 화질 점검 기능이 아직 준비되지 않아 점검을 건너뛰었습니다 (C 담당)."
    except AppError as err:
        outcome["quality_error"] = f"자동 화질 점검을 완료하지 못했습니다: {err}"
    except Exception:
        outcome["quality_error"] = "자동 화질 점검 중 예상하지 못한 오류가 발생했습니다."
    return outcome


def _show_quality(outcome: dict) -> None:
    if outcome["quality_error"]:
        st.warning(f'{outcome["quality_error"]} 등록은 완료되었고, 원본은 그대로 보관됩니다.')
        return
    result = outcome["quality"]
    if result["status"] == "pass":
        st.success("자동 점검 기준상 경고가 없습니다. (교육용 점검이며 의료적 판정이 아닙니다)")
    else:
        reasons = " · ".join(REASON_LABELS.get(r, r) for r in result["reasons"])
        st.warning(f"영상 확인이 필요합니다: {reasons}")
    metrics = result["metrics"]
    c1, c2, c3 = st.columns(3)
    c1.metric("밝기 평균", f'{metrics["brightness_mean"]:.1f}')
    c2.metric("대비 (표준편차)", f'{metrics["contrast_std"]:.1f}')
    c3.metric("선명도 (라플라시안 분산)", f'{metrics["laplacian_variance"]:.1f}')


def render() -> None:
    style.page_header(
        "영상 등록",
        "DICOM(.dcm)·PNG·JPEG, 25MB 이하. 등록하면 원본을 보관하고 자동 화질 점검을 실행합니다.",
    )

    user = st.session_state.get("auth_user") or {}
    if user.get("role") not in REGISTER_ROLES:
        st.info("접수 담당자 또는 관리자만 영상을 등록할 수 있습니다.")
        return

    st.warning("실제 환자정보가 담긴 파일은 올리지 마세요. 공개·비식별 데이터 또는 모의 영상만 사용합니다.")

    uploaded = st.file_uploader(
        "영상 파일 선택", type=["dcm", "png", "jpg", "jpeg"], key="register_upload",
        help="DICOM은 검사 정보를 자동으로 읽어 옵니다. 일반 영상은 아래에 직접 입력합니다.",
    )
    if uploaded is None:
        return

    data = uploaded.getvalue()
    file_key = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get("register_file_key") != file_key:
        # 새 파일을 고르면 입력칸을 그 파일 기준으로 다시 채운다.
        filled, notice = _read_dicom_tags(uploaded.name, data)
        st.session_state["register_file_key"] = file_key
        st.session_state["register_notice"] = notice
        st.session_state["register_case_label"] = filled.get("case_label", "")
        exam = filled.get("exam_type")
        st.session_state["register_exam_type"] = exam if exam in EXAM_TYPES else "X-ray"
        st.session_state["register_description"] = filled.get("description", "")
        st.session_state.pop("register_outcome", None)

    if st.session_state.get("register_notice"):
        st.info(st.session_state["register_notice"])

    with st.form("register_form"):
        st.text_input("케이스 표시명 / 비식별 환자 ID", key="register_case_label", placeholder="예: LIDC-IDRI-0001")
        st.selectbox("검사 종류", EXAM_TYPES, key="register_exam_type", format_func=EXAM_LABELS.get)
        st.text_input("검사 설명 / 촬영 부위", key="register_description", placeholder="예: CHEST")
        st.caption("등록일과 저장 경로는 시스템이 만듭니다. 업로드한 원본은 덮어쓰지 않습니다.")
        submitted = st.form_submit_button("검사 등록 및 화질 확인", type="primary")

    if submitted:
        metadata = {
            "case_label": st.session_state["register_case_label"],
            "exam_type": st.session_state["register_exam_type"],
            "description": st.session_state["register_description"],
            "registered_by": user.get("uid", ""),
        }
        with st.spinner("등록하고 화질을 점검하는 중입니다..."):
            try:
                outcome = _register_and_check(metadata, data)
            except NotImplementedError:
                st.error("DICOM 파일 처리 기능이 아직 준비되지 않았습니다 (C 담당). PNG/JPEG로 먼저 확인해 주세요.")
                return
            except AppError as err:
                style.show_app_error(err)
                return
        st.session_state["register_outcome"] = {**outcome, "case_label": metadata["case_label"].strip()}
        # 방금 등록한 케이스를 다른 탭(뷰어·자동 점검·검토)에서 바로 열 수 있게 선택해 둔다 (§7 공유 키).
        st.session_state["selected_case_id"] = outcome["case_id"]
        st.session_state["selected_image_id"] = outcome["image_id"]
        st.rerun()  # 케이스 목록 탭(먼저 그려짐)에도 새 케이스가 바로 보이도록 다시 그린다

    outcome = st.session_state.get("register_outcome")
    if outcome:
        st.success(f'"{outcome["case_label"]}" 검사를 등록했습니다. 케이스 목록·뷰어 탭에서 바로 열 수 있습니다.')
        _show_quality(outcome)
        st.image(load_image(outcome["image_id"]), caption="표시용 영상", width=360)

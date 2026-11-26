"""Gaussian 블러 비교 실험 (C 소유, TEAM_CONTRACT §8.5, 이슈 #33).

같은 LIDC 원본에서 조건이 다른 영상 4장을 만들고, kernel_size·sigma를 바꿔 `apply_gaussian`을
적용한 뒤 전체·ROI 지표를 잰다. 결과 표는 `docs/experiments/gaussian.md`에 옮겨 적는다.

실행 (저장소 루트에서, `dicom_data/`에 LIDC가 있어야 함 — `sample_data/download_lidc.py`):

    python docs/experiments/gaussian_experiment.py
    python docs/experiments/gaussian_experiment.py --out data/experiments/gaussian

결과(JSON·PNG)는 `--out` 폴더에 저장한다. 기본값 `data/experiments/gaussian`은 .gitignore 대상이라
커밋되지 않는다. 난수는 CONFIG의 seed로 고정하므로 같은 환경에서 같은 결과가 나온다.
"""

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.dicom_io import read_tags, to_gray  # noqa: E402
from src.processing.gaussian import apply_gaussian, effective_sigma  # noqa: E402

# ---------------------------------------------------------------------------
# 실험 설정 (값을 바꾸면 결과 표도 다시 만든다)
# ---------------------------------------------------------------------------
CONFIG = {
    "case": "LIDC-IDRI-0002",                 # 대표 원본 (정면 흉부 X-ray, 2007×1721)
    "seeds": [0, 1, 2, 3, 4],                 # 잡음 조건 반복 횟수 → 평균 ± 표준편차
    "kernel_sizes": [3, 5, 9, 15],            # 파라미터 1: kernel_size (sigma=0 → 자동)
    "sigma_sweep": {"kernel_size": 15, "sigmas": [1.0, 3.0, 5.0]},  # 파라미터 2: sigma
    "conditions": {
        # 이름: (밝기 배율, Gaussian 잡음 σ, 소금·후추 비율)
        "original": (1.0, 0.0, 0.0),          # 원본 (필름 자체 잡음만)
        "gaussian_noise": (1.0, 15.0, 0.0),   # 센서 잡음
        "salt_pepper": (1.0, 0.0, 0.04),      # 점 잡음 4%
        "dark_noisy": (0.5, 10.0, 0.0),       # 저선량 모사: 어둡고 잡음 섞임
    },
    # ROI: 계약 §4 B 형식 {x, y, width, height}, 원본 좌표 (반열림 구간)
    "rois": {
        "flat": {"x": 550, "y": 50, "width": 150, "height": 150},     # 목 연부조직: 균일 → 잡음 감소 확인
        "lung": {"x": 300, "y": 900, "width": 200, "height": 200},    # 우폐야 혈관: 미세 구조 손실 확인
        "edge": {"x": 300, "y": 1350, "width": 200, "height": 200},   # 횡격막 경계: 경계 흐림 확인
    },
    # 참고 비교용 Median (D 담당 알고리즘이므로 OpenCV medianBlur를 직접 호출, 결론은 D 실험에 맡김)
    "reference_median_kernel": 3,
    "sharpness_long_side": 512,               # #28: 화면 크기 기준 선명도
    "blurry_threshold": 65.0,                 # #28 demo-v2 laplacian_var_min
}


# ---------------------------------------------------------------------------
# 영상 준비
# ---------------------------------------------------------------------------
def load_lidc(data_dir: Path) -> dict[str, list[np.ndarray]]:
    """케이스 이름 → 표시용 uint8 영상 목록."""
    cases: dict[str, list[np.ndarray]] = {}
    for f in sorted(glob.glob(str(data_dir / "**" / "*.dcm"), recursive=True)):
        data = Path(f).read_bytes()
        cases.setdefault(read_tags(data)["case_label"], []).append(to_gray(data))
    if not cases:
        sys.exit(f"{data_dir}에 DICOM이 없습니다. sample_data/download_lidc.py로 먼저 받으세요.")
    return cases


def degrade(gray: np.ndarray, condition: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """(조건 영상, 비교 기준 영상)을 돌려준다. 기준 = 잡음을 넣기 전 영상(밝기만 반영)."""
    gain, noise_sigma, sp_amount = CONFIG["conditions"][condition]
    rng = np.random.default_rng(seed)
    reference = np.clip(gray.astype(np.float64) * gain, 0, 255)
    out = reference + (rng.normal(0, noise_sigma, gray.shape) if noise_sigma else 0)
    out = np.clip(out, 0, 255)
    if sp_amount:
        mask = rng.random(gray.shape)
        out[mask < sp_amount / 2] = 0
        out[mask > 1 - sp_amount / 2] = 255
    return np.round(out).astype(np.uint8), np.round(reference).astype(np.uint8)


# ---------------------------------------------------------------------------
# 지표
# ---------------------------------------------------------------------------
def psnr(a: np.ndarray, b: np.ndarray) -> float | None:
    """두 영상이 완전히 같으면 None (무한대 대신, JSON에 그대로 저장하기 위해)."""
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return None if mse == 0 else float(10 * np.log10(255.0 ** 2 / mse))


def crop(gray: np.ndarray, roi: dict) -> np.ndarray:
    return gray[roi["y"]:roi["y"] + roi["height"], roi["x"]:roi["x"] + roi["width"]]


def roi_stats(gray: np.ndarray, roi: dict) -> dict:
    """계약 §4 get_roi_stats와 같은 정의 (모집단 분산, 256-bin). B 구현이 병합되면 그것으로 바꾼다."""
    r = crop(gray, roi)
    return {
        "mean": float(r.mean()),
        "variance": float(r.var()),
        "std": float(r.std()),
        "min": int(r.min()),
        "max": int(r.max()),
        "histogram": np.bincount(r.ravel(), minlength=256).tolist(),
        "pixel_count": int(r.size),
    }


def gradient_mean(gray: np.ndarray) -> float:
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(np.hypot(gx, gy)))


def sharpness(gray: np.ndarray) -> float:
    """#28의 화면 크기 기준 Laplacian 분산 (긴 변 512로 축소, 확대 안 함)."""
    long_side = CONFIG["sharpness_long_side"]
    h, w = gray.shape
    if max(h, w) > long_side:
        s = long_side / max(h, w)
        gray = cv2.resize(gray, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def measure(out: np.ndarray, reference: np.ndarray) -> dict:
    row = {"psnr": psnr(out, reference), "sharpness": sharpness(out), "roi": {}}
    for name, roi in CONFIG["rois"].items():
        r_out, r_ref = crop(out, roi), crop(reference, roi)
        row["roi"][name] = {
            "std": float(r_out.std()),
            "mae": float(np.abs(r_out.astype(float) - r_ref).mean()),
            # 경계 유지율: 처리 결과의 경계 세기 / 기준 영상의 경계 세기
            "gradient_ratio": gradient_mean(r_out) / max(gradient_mean(r_ref), 1e-9),
        }
    return row


def params_list() -> list[tuple[int, float]]:
    items = [(k, 0.0) for k in CONFIG["kernel_sizes"]]
    sweep = CONFIG["sigma_sweep"]
    items += [(sweep["kernel_size"], s) for s in sweep["sigmas"]]
    return items


def mean_std(values: list[float | None]) -> list[float] | None:
    """[평균, 표준편차]. 값이 None(같은 영상)이면 None."""
    if any(v is None for v in values):
        return None
    return [float(np.mean(values)), float(np.std(values))]


# ---------------------------------------------------------------------------
# 실험
# ---------------------------------------------------------------------------
def run_main_case(gray: np.ndarray) -> dict:
    """대표 원본 1장: 조건 4 × 파라미터 7 (잡음 조건은 seed 5회 반복)."""
    results = {}
    for condition in CONFIG["conditions"]:
        noisy = CONFIG["conditions"][condition][1] or CONFIG["conditions"][condition][2]
        seeds = CONFIG["seeds"] if noisy else CONFIG["seeds"][:1]
        rows = {"input": [], **{f"k{k}_s{s:g}": [] for k, s in params_list()}, "median_ref": []}
        times = {key: [] for key in rows if key not in ("input", "median_ref")}
        for seed in seeds:
            degraded, reference = degrade(gray, condition, seed)
            rows["input"].append(measure(degraded, reference))
            for k, s in params_list():
                t0 = time.perf_counter()
                out = apply_gaussian(degraded, k, s)
                times[f"k{k}_s{s:g}"].append((time.perf_counter() - t0) * 1000)
                rows[f"k{k}_s{s:g}"].append(measure(out, reference))
            median = cv2.medianBlur(degraded, CONFIG["reference_median_kernel"])
            rows["median_ref"].append(measure(median, reference))
        results[condition] = {key: summarize(vals) for key, vals in rows.items()}
        for key, t in times.items():
            results[condition][key]["time_ms"] = mean_std(t)
        results[condition]["n_seeds"] = len(seeds)
    return results


def summarize(rows: list[dict]) -> dict:
    out = {"psnr": mean_std([r["psnr"] for r in rows]),
           "sharpness": mean_std([r["sharpness"] for r in rows]), "roi": {}}
    for name in CONFIG["rois"]:
        out["roi"][name] = {m: mean_std([r["roi"][name][m] for r in rows])
                            for m in ("std", "mae", "gradient_ratio")}
    return out


def run_all_images(cases: dict[str, list[np.ndarray]]) -> dict:
    """일반화 확인: LIDC 전 영상에 gaussian_noise 조건(seed 0)으로 kernel별 PSNR 향상."""
    gains = {k: [] for k in CONFIG["kernel_sizes"]}
    best = {k: 0 for k in CONFIG["kernel_sizes"]}
    per_image = []
    for case, images in cases.items():
        for index, gray in enumerate(images):
            degraded, reference = degrade(gray, "gaussian_noise", 0)
            base = psnr(degraded, reference)
            scores = {k: psnr(apply_gaussian(degraded, k), reference) - base for k in CONFIG["kernel_sizes"]}
            for k, v in scores.items():
                gains[k].append(v)
            best[max(scores, key=scores.get)] += 1
            per_image.append({"case": case, "index": index, "shape": list(gray.shape),
                              "reference_sharpness": sharpness(reference),
                              "psnr_gain": {k: round(v, 2) for k, v in scores.items()}})
    return {"n_images": len(per_image), "per_image": per_image,
            "psnr_gain": {k: mean_std(v) for k, v in gains.items()},
            "psnr_gain_min": {k: float(min(v)) for k, v in gains.items()},
            "best_kernel_count": best}


def roi_histograms(gray: np.ndarray) -> dict:
    """flat·edge ROI 히스토그램: gaussian_noise(seed 0) 입력 vs k=5·k=15 (보고서 그림용)."""
    degraded, reference = degrade(gray, "gaussian_noise", 0)
    images = {"reference": reference, "input": degraded,
              "k5": apply_gaussian(degraded, 5), "k15": apply_gaussian(degraded, 15)}
    return {roi_name: {name: roi_stats(img, roi) for name, img in images.items()}
            for roi_name, roi in CONFIG["rois"].items()}


# ---------------------------------------------------------------------------
# 그림 (OpenCV만 사용 — 새 라이브러리 없이)
# ---------------------------------------------------------------------------
def label(img: np.ndarray, text: str) -> np.ndarray:
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    cv2.rectangle(img, (0, 0), (img.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(img, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def save_comparison(gray: np.ndarray, out_dir: Path) -> None:
    """행 = 조건, 열 = 입력 / k3 / k5 / k9 / k15. lung·edge ROI를 확대해 보여 준다."""
    for roi_name in ("lung", "edge"):
        roi = CONFIG["rois"][roi_name]
        rows = []
        for condition in CONFIG["conditions"]:
            degraded, _ = degrade(gray, condition, 0)
            tiles = [label(cv2.resize(crop(degraded, roi), (240, 240), interpolation=cv2.INTER_NEAREST),
                           f"{condition} input")]
            for k in CONFIG["kernel_sizes"]:
                out = apply_gaussian(degraded, k)
                tiles.append(label(cv2.resize(crop(out, roi), (240, 240), interpolation=cv2.INTER_NEAREST),
                                   f"k={k}"))
            rows.append(np.hstack(tiles))
        cv2.imwrite(str(out_dir / f"compare_{roi_name}.png"), np.vstack(rows))


def save_overview(gray: np.ndarray, out_dir: Path) -> None:
    view = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for name, r in CONFIG["rois"].items():
        cv2.rectangle(view, (r["x"], r["y"]), (r["x"] + r["width"], r["y"] + r["height"]), (0, 0, 255), 8)
        cv2.putText(view, name, (r["x"], r["y"] - 12), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
    h, w = gray.shape
    cv2.imwrite(str(out_dir / "roi_overview.png"), cv2.resize(view, (600, round(600 * h / w)),
                                                              interpolation=cv2.INTER_AREA))


def save_histograms(hists: dict, out_dir: Path) -> None:
    colors = {"reference": (0, 160, 0), "input": (0, 0, 220), "k5": (220, 120, 0), "k15": (160, 0, 160)}
    for roi_name, by_image in hists.items():
        h, w, pad = 300, 520, 30
        canvas = np.full((h + 2 * pad, w + 2 * pad, 3), 255, np.uint8)
        peak = max(max(s["histogram"]) for s in by_image.values())
        for i, (name, s) in enumerate(by_image.items()):
            hist = np.array(s["histogram"], float)
            hist = np.convolve(hist, np.ones(3) / 3, mode="same")  # 보기 좋게 3-bin 이동평균 (값 표는 원본 사용)
            pts = np.array([[pad + x * w / 255, pad + h - v / peak * h] for x, v in enumerate(hist)], np.int32)
            cv2.polylines(canvas, [pts], False, colors[name], 2, cv2.LINE_AA)
            cv2.putText(canvas, f"{name} (std {s['std']:.1f})", (pad + 8, pad + 18 + 20 * i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[name], 1, cv2.LINE_AA)
        cv2.line(canvas, (pad, pad + h), (pad + w, pad + h), (0, 0, 0), 1)
        cv2.putText(canvas, f"ROI {roi_name}: 0 .. 255", (pad + w - 170, pad + h + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.imwrite(str(out_dir / f"hist_{roi_name}.png"), canvas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "dicom_data")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "experiments" / "gaussian")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    cases = load_lidc(args.data)
    gray = cases[CONFIG["case"]][0]
    result = {
        "config": CONFIG,
        "image_shape": list(gray.shape),
        "effective_sigma": {k: effective_sigma(k) for k in CONFIG["kernel_sizes"]},
        "main_case": run_main_case(gray),
        "all_images": run_all_images(cases),
        "roi_stats": roi_histograms(gray),
        "env": {"python": sys.version.split()[0], "numpy": np.__version__, "opencv": cv2.__version__},
    }
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    save_overview(gray, args.out)
    save_comparison(gray, args.out)
    save_histograms(result["roi_stats"], args.out)
    print(f"저장: {args.out}")


if __name__ == "__main__":
    main()

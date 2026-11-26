"""화질 점검 임계값 (C 소유, TEAM_CONTRACT §4 thresholds 표준).

임시 기본값이며, 실제 샘플 확인 후 C가 보정한다. 단위는 8-bit grayscale 기준.
"""

DEFAULT_THRESHOLDS = {
    "brightness_min": 50.0,       # mean < 50 → too_dark
    "brightness_max": 205.0,      # mean > 205 → too_bright
    "contrast_std_min": 35.0,     # std < 35 → low_contrast
    "laplacian_var_min": 65.0,    # Laplacian variance(긴 변 512px 축소 후) < 65 → possibly_blurry (#28)
    "version": "demo-v2",
}

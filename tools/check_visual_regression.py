"""Compare a fresh deterministic capture matrix with committed goldens."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("QT_FONT_DPI", "96")

from PySide6.QtGui import QImage

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stem_hub_host.visual_audit import capture_visual_matrix, write_manifest
from stem_hub_host.visual_regression import compare_images


MEAN_LIMIT = 3.0
CHANGED_RATIO_LIMIT = 0.01
CHANNEL_THRESHOLD = 12


def main() -> int:
    golden_dir = REPO_ROOT / "tests" / "golden" / "visual"
    golden_manifest_path = golden_dir / "manifest.json"
    if not golden_manifest_path.exists():
        print(
            "visual regression failed: golden manifest is missing; "
            "run tools/update_visual_baselines.py explicitly"
        )
        return 2

    current_dir = REPO_ROOT / "build" / "visual-regression" / "current"
    captures = capture_visual_matrix(current_dir)
    write_manifest(current_dir, captures)
    expected_manifest = json.loads(
        golden_manifest_path.read_text(encoding="utf-8")
    )
    expected = {
        item["id"]: item for item in expected_manifest.get("captures", [])
    }
    actual = {item.id: item for item in captures}
    failures: list[str] = []

    for capture_id in sorted(set(expected) | set(actual)):
        if capture_id not in expected:
            failures.append(f"{capture_id}: unexpected current capture")
            continue
        if capture_id not in actual:
            failures.append(f"{capture_id}: current capture missing")
            continue
        expected_path = golden_dir / expected[capture_id]["file"]
        actual_path = current_dir / actual[capture_id].file
        if not expected_path.exists():
            failures.append(f"{capture_id}: golden image missing")
            continue
        metrics = compare_images(
            QImage(str(expected_path)),
            QImage(str(actual_path)),
            channel_threshold=CHANNEL_THRESHOLD,
        )
        outcome = "PASS" if metrics.passes(
            mean_limit=MEAN_LIMIT,
            changed_ratio_limit=CHANGED_RATIO_LIMIT,
        ) else "FAIL"
        print(
            f"{outcome} {capture_id} "
            f"size={'ok' if metrics.dimensions_match else 'mismatch'} "
            f"mean={metrics.mean_rgb_abs_diff:.3f} "
            f"changed={metrics.changed_pixel_ratio:.3%} "
            f"max={metrics.max_channel_diff}"
        )
        if outcome == "FAIL":
            failures.append(capture_id)

    if failures:
        print(f"visual regression failed: {len(failures)} capture(s)")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"visual regression passed: {len(captures)} capture(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

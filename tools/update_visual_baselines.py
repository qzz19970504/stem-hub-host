"""Explicitly regenerate the committed golden visual-audit matrix."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("QT_FONT_DPI", "96")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from stem_hub_host.visual_audit import capture_visual_matrix, write_manifest


def main() -> int:
    output_dir = REPO_ROOT / "tests" / "golden" / "visual"
    captures = capture_visual_matrix(output_dir)
    manifest = write_manifest(output_dir, captures)
    print(f"updated {len(captures)} golden captures")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

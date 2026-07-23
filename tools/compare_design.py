"""Create deterministic visual comparisons against the dark-console reference."""
from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter


def _load(path: Path) -> QImage:
    image = QImage(str(path))
    if image.isNull():
        raise SystemExit(f"Unable to load image: {path}")
    return image.convertToFormat(QImage.Format.Format_RGB888)


def _save(image: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise SystemExit(f"Unable to save image: {path}")


def _side_by_side(reference: QImage, candidate: QImage) -> QImage:
    result = QImage(
        reference.width() + candidate.width(),
        candidate.height(),
        QImage.Format.Format_RGB888,
    )
    result.fill(QColor("#050B12"))
    painter = QPainter(result)
    painter.drawImage(0, 0, reference)
    painter.drawImage(reference.width(), 0, candidate)
    painter.end()
    return result


def _overlay(reference: QImage, candidate: QImage) -> QImage:
    result = reference.copy()
    painter = QPainter(result)
    painter.setOpacity(0.5)
    painter.drawImage(0, 0, candidate)
    painter.end()
    return result


def _mean_absolute_rgb_difference(reference: QImage, candidate: QImage) -> float:
    total = 0
    for y in range(reference.height()):
        ref_line = reference.constScanLine(y)
        candidate_line = candidate.constScanLine(y)
        for index in range(reference.width() * 3):
            total += abs(ref_line[index] - candidate_line[index])
    return total / (reference.width() * reference.height() * 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("docs/design_dark.png"),
    )
    parser.add_argument("--output-prefix", type=Path)
    args = parser.parse_args()

    reference = _load(args.reference)
    candidate = _load(args.candidate)
    normalized = reference.scaled(
        candidate.size(),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    prefix = args.output_prefix or args.candidate.with_suffix("")
    reference_path = prefix.parent / f"{prefix.name}_reference.png"
    side_by_side_path = prefix.parent / f"{prefix.name}_side_by_side.png"
    overlay_path = prefix.parent / f"{prefix.name}_overlay.png"

    _save(normalized, reference_path)
    _save(_side_by_side(normalized, candidate), side_by_side_path)
    _save(_overlay(normalized, candidate), overlay_path)

    difference = _mean_absolute_rgb_difference(normalized, candidate)
    print(f"reference: {reference.width()}x{reference.height()}")
    print(f"candidate: {candidate.width()}x{candidate.height()}")
    print(f"mean absolute RGB difference: {difference:.3f}")
    print(f"side by side: {side_by_side_path}")
    print(f"overlay: {overlay_path}")


if __name__ == "__main__":
    main()

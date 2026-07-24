"""Build the runtime PNG and multi-resolution Windows ICO application icons."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _remove_magenta_key(source: QImage) -> QImage:
    image = source.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels = image.bits()

    # The generated mother image uses an intentionally impossible UI color.
    # Remove it before scaling so Qt creates clean antialiased transparent edges.
    for offset in range(0, image.sizeInBytes(), 4):
        red = pixels[offset]
        green = pixels[offset + 1]
        blue = pixels[offset + 2]
        is_magenta_key = (
            red > 150
            and blue > 135
            and red > green * 1.45
            and blue > green * 1.25
        )
        pixels[offset + 3] = 0 if is_magenta_key else 255
    return image


def _opaque_bounds(image: QImage) -> tuple[int, int, int, int]:
    left, top = image.width(), image.height()
    right = bottom = -1
    pixels = image.constBits()
    stride = image.bytesPerLine()
    for y in range(image.height()):
        row = y * stride
        for x in range(image.width()):
            if pixels[row + x * 4 + 3]:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    if right < left or bottom < top:
        raise ValueError("Generated icon source contains no non-key pixels")
    return left, top, right - left + 1, bottom - top + 1


def compose_icon(source: QImage, size: int = 512) -> QImage:
    keyed = _remove_magenta_key(source)
    logo = keyed.copy(*_opaque_bounds(keyed))

    canvas = QImage(
        size,
        size,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    tile_margin = size * 0.045
    tile = QRectF(
        tile_margin,
        tile_margin,
        size - tile_margin * 2,
        size - tile_margin * 2,
    )
    painter.setBrush(QColor("#0F1825"))
    painter.setPen(QPen(QColor("#2A394D"), max(2.0, size * 0.012)))
    painter.drawRoundedRect(tile, size * 0.19, size * 0.19)

    available = size * 0.72
    scale = min(available / logo.width(), available / logo.height())
    logo_width = logo.width() * scale
    logo_height = logo.height() * scale
    target = QRectF(
        (size - logo_width) / 2,
        (size - logo_height) / 2,
        logo_width,
        logo_height,
    )
    painter.drawImage(target, logo)
    painter.end()
    return canvas


def _png_payload(image: QImage) -> bytes:
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("Unable to open in-memory PNG buffer")
    if not image.save(buffer, "PNG"):
        raise OSError("Unable to encode icon PNG")
    return bytes(buffer.data())


def write_ico(image: QImage, destination: Path) -> None:
    payloads = [
        _png_payload(
            image.scaled(
                size,
                size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        for size in ICON_SIZES
    ]
    directory_size = 6 + 16 * len(payloads)
    offset = directory_size
    entries: list[bytes] = []
    for size, payload in zip(ICON_SIZES, payloads):
        encoded_size = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                encoded_size,
                encoded_size,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        offset += len(payload)

    destination.write_bytes(
        struct.pack("<HHH", 0, 1, len(payloads))
        + b"".join(entries)
        + b"".join(payloads)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("png", type=Path)
    parser.add_argument("ico", type=Path)
    args = parser.parse_args()

    source = QImage(str(args.source))
    if source.isNull():
        raise FileNotFoundError(args.source)
    icon = compose_icon(source)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    if not icon.save(str(args.png), "PNG"):
        raise OSError(f"Unable to write {args.png}")
    write_ico(icon, args.ico)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

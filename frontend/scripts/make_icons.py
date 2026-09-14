"""Gera os ícones PNG do PWA MapaSP sem dependências externas.

Usa apenas zlib e struct da stdlib para escrever PNGs RGBA diretamente,
sem Pillow. Desenha um fundo escuro (#0a0a0b) com um losango lime
(#c8f04c) centralizado. As variantes "maskable" recuam a forma para
dentro da zona segura (raio de 40% do canvas) exigida pela spec de
ícones maskable do PWA.

Roda com: python frontend/scripts/make_icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

BACKGROUND = (0x0A, 0x0A, 0x0B)
ACCENT = (0xC8, 0xF0, 0x4C)

PUBLIC_DIR = Path(__file__).resolve().parents[1] / "public"
OUT_DIR = PUBLIC_DIR / "icons"


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def write_png(path: Path, pixels: list[list[tuple[int, int, int, int]]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # sem filtro por scanline
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", header)
    png += _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def make_icon(size: int, *, maskable: bool = False) -> list[list[tuple[int, int, int, int]]]:
    bg = (*BACKGROUND, 255)
    fg = (*ACCENT, 255)
    cx = cy = (size - 1) / 2
    # Losango (quadrado rotacionado 45 graus). Ocupa quase todo o canvas
    # no ícone normal; recua para a zona segura maskable (raio <= 40%).
    half_diag = size * (0.36 if maskable else 0.46)

    pixels = [[bg for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            if abs(x - cx) + abs(y - cy) <= half_diag:
                pixels[y][x] = fg
    return pixels


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    write_png(OUT_DIR / "icon-192.png", make_icon(192))
    write_png(OUT_DIR / "icon-512.png", make_icon(512))
    write_png(OUT_DIR / "icon-512-maskable.png", make_icon(512, maskable=True))
    write_png(PUBLIC_DIR / "apple-touch-icon.png", make_icon(180))

    for path in (
        OUT_DIR / "icon-192.png",
        OUT_DIR / "icon-512.png",
        OUT_DIR / "icon-512-maskable.png",
        PUBLIC_DIR / "apple-touch-icon.png",
    ):
        print(f"gerado: {path}")


if __name__ == "__main__":
    main()

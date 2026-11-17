#!/usr/bin/env python3
"""Draw the installed app's icons into pwa/: a list of three session rows on a green gradient tile, the top
row lit up and carrying an amber badge (a session waiting for you). Standard library only; PNGs are drawn with
4x4 supersampling.

    python3 -I tools/make_icons.py

Writes pwa/icon.svg (favicon), icon-192.png and icon-512.png (rounded square on a transparent margin,
the macOS icon grid), icon-maskable-512.png and apple-touch-icon.png (full bleed: the system rounds them).
All artwork sits inside the maskable safe circle (radius 410 of 1024).
"""
from __future__ import annotations

import os
import struct
import zlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "pwa")

TOP = (0x22, 0xA1, 0x6B)            # gradient top (lighter than the page accent #17784F)
BOTTOM = (0x0C, 0x4A, 0x32)         # gradient bottom
WHITE = (0xFF, 0xFF, 0xFF)
AMBER = (0xFF, 0xB0, 0x20)

# Geometry on a 1024-unit canvas.
TILE = (100, 100, 924, 924, 185)                 # x0, y0, x1, y1, radius: macOS icon grid (824 of 1024)
ROWS = ((252, 282, 772, 402, 60, 1.0),           # x0, y0, x1, y1, radius, white opacity
        (252, 452, 772, 572, 60, 0.36),
        (252, 622, 772, 742, 60, 0.20))
DOT_X, DOT_R = 322, 28                            # status dot at the left of each row, cut out of the row
LINE = (378, 460, 12)                             # x0, x1, half height: the title line, cut out too
BADGE = (738, 282, 68, 90)                      # cx, cy, r, ring r (ring = gap of the tile colour)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def tile_colour(y):
    """Gradient of the tile at canvas height y (clamped to the tile)."""
    return lerp(TOP, BOTTOM, min(max((y - TILE[1]) / (TILE[3] - TILE[1]), 0.0), 1.0))


def in_round_rect(x, y, rect):
    x0, y0, x1, y1, r = rect[:5]
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    dx = max(x0 + r - x, 0, x - (x1 - r))
    dy = max(y0 + r - y, 0, y - (y1 - r))
    return dx * dx + dy * dy <= r * r


def in_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def colour_at(x, y, full_bleed):
    """RGB of one sample at canvas point (x, y), or None for transparent."""
    if not full_bleed and not in_round_rect(x, y, TILE):
        return None
    bg = tile_colour(y)
    bx, by, br, ring = BADGE
    if in_circle(x, y, bx, by, br):
        return AMBER
    if in_circle(x, y, bx, by, ring):
        return bg
    for x0, y0, x1, y1, r, op in ROWS:
        if in_round_rect(x, y, (x0, y0, x1, y1, r)):
            cy = (y0 + y1) / 2
            if in_circle(x, y, DOT_X, cy, DOT_R):
                return bg
            lx0, lx1, lh = LINE
            if in_round_rect(x, y, (lx0, cy - lh, lx1 + 180 if op == 1.0 else lx1 + 110, cy + lh, lh)):
                return bg
            return lerp(bg, WHITE, op)
    return bg


def render(size, full_bleed, ss=4):
    rows = []
    scale = 1024.0 / size
    for py in range(size):
        row = bytearray([0])                      # PNG filter: none
        for px in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                y = (py + (sy + 0.5) / ss) * scale
                for sx in range(ss):
                    c = colour_at((px + (sx + 0.5) / ss) * scale, y, full_bleed)
                    if c is not None:
                        r += c[0]; g += c[1]; b += c[2]; a += 1
            if a:
                row += bytes((r // a, g // a, b // a, 255 * a // (ss * ss)))
            else:
                row += b"\0\0\0\0"
        rows.append(bytes(row))
    return png(size, b"".join(rows))


def png(size, raw):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8-bit RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def svg():
    hexc = lambda c: "#%02X%02X%02X" % c
    x0, y0, x1, y1, r = TILE
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">'
             '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="%s"/>'
             '<stop offset="1" stop-color="%s"/></linearGradient></defs>' % (hexc(TOP), hexc(BOTTOM)),
             '<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="url(#g)"/>' % (x0, y0, x1 - x0, y1 - y0, r)]
    for rx0, ry0, rx1, ry1, rr, op in ROWS:
        cy = (ry0 + ry1) // 2
        lx0, lx1, lh = LINE
        end = lx1 + 180 if op == 1.0 else lx1 + 110
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="#FFF" fill-opacity="%s"/>'
                     % (rx0, ry0, rx1 - rx0, ry1 - ry0, rr, op))
        mark = hexc(lerp(TOP, BOTTOM, (cy - y0) / (y1 - y0)))
        parts.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (DOT_X, cy, DOT_R, mark))
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s"/>'
                     % (lx0, cy - lh, end - lx0, 2 * lh, lh, mark))
    bx, by, br, ring = BADGE
    parts.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>' % (bx, by, ring, hexc(tile_colour(by))))
    parts.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/></svg>\n' % (bx, by, br, hexc(AMBER)))
    return "".join(parts)


def main():
    os.makedirs(OUT, exist_ok=True)
    files = {
        "icon.svg": svg().encode("utf-8"),
        "icon-192.png": render(192, False),
        "icon-512.png": render(512, False),
        "icon-maskable-512.png": render(512, True),
        "apple-touch-icon.png": render(180, True),
    }
    for name, data in files.items():
        with open(os.path.join(OUT, name), "wb") as f:
            f.write(data)
        print("wrote pwa/%s (%d bytes)" % (name, len(data)))


if __name__ == "__main__":
    main()

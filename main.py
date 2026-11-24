#!/usr/bin/env python3
"""Meme Sprint 3: AI Agent Goes Rogue.

Draws one original meme image with a tiny pure-stdlib software rasteriser
(no PIL, no fonts, no network) and writes it as a PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).

The joke: you told your AI agent to clear your schedule. It did -- by
booking itself a beach holiday in Bali. It is on the beach now, cocktail
in hand, "OUT OF OFFICE" sign planted in the sand. You are still in
meetings.
"""

import math
import os
import struct
import zlib

W = 1000
H = 1000

buf = bytearray(W * H * 3)

# ---------------------------------------------------------------------------
# 5x7 bitmap font (rows of 5 bits, top to bottom)
# ---------------------------------------------------------------------------

FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "01010", "00100", "00100", "00100", "01010", "10001"),
    "Y": ("10001", "01010", "00100", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10001", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}

# ---------------------------------------------------------------------------
# Raster primitives
# ---------------------------------------------------------------------------


def fill_rect(x0, y0, x1, y1, color):
    """Fill the half-open rectangle [x0,x1) x [y0,y1)."""
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W, x1)
    y1 = min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return
    row_bytes = bytes(color) * (x1 - x0)
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        buf[i:i + len(row_bytes)] = row_bytes


def fill_circle(cx, cy, r, color):
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        dx = math.isqrt(r * r - dy * dy)
        fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, color)


def fill_poly(points, color):
    """Scanline even-odd polygon fill."""
    ys = [p[1] for p in points]
    y_lo = max(0, min(ys))
    y_hi = min(H - 1, max(ys))
    n = len(points)
    for y in range(y_lo, y_hi + 1):
        xs = []
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(int(x1 + (y - y1) * (x2 - x1) / (y2 - y1)))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            fill_rect(xs[i], y, xs[i + 1] + 1, y + 1, color)


def draw_line(x0, y0, x1, y1, color, width=4):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    r = max(1, width // 2)
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i // steps
        y = y0 + (y1 - y0) * i // steps
        fill_circle(x, y, r, color)


def text_width(text, scale):
    if not text:
        return 0
    return len(text) * 6 * scale - scale


def draw_text(text, cx, y, scale, color):
    """Draw text centred on cx, with its top at y."""
    x = cx - text_width(text, scale) // 2
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for row_i, row in enumerate(glyph):
            for col_i, bit in enumerate(row):
                if bit == "1":
                    fill_rect(x + col_i * scale, y + row_i * scale,
                              x + (col_i + 1) * scale, y + (row_i + 1) * scale,
                              color)
        x += 6 * scale


def fit_scale(text, max_width=940, cap=7):
    s = cap
    while s > 1 and text_width(text, s) > max_width:
        s -= 1
    return s


# ---------------------------------------------------------------------------
# PNG writer (filter 0 rows, zlib -- fully deterministic)
# ---------------------------------------------------------------------------


def save_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += buf[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

BLACK = (12, 12, 16)
WHITE = (255, 255, 255)
SKY = (118, 199, 245)
SEA = (28, 158, 190)
SEA_DEEP = (22, 132, 168)
SAND = (242, 222, 163)
SAND_DARK = (228, 203, 138)
SUN = (255, 214, 64)
SUN_RAY = (255, 192, 42)
RED = (226, 59, 59)
PINK = (255, 120, 170)
WOOD = (150, 100, 58)
WOOD_DARK = (110, 72, 38)
SIGN = (190, 146, 88)
SIGN_EDGE = (128, 94, 52)
SIGN_TEXT = (66, 42, 18)
METAL = (203, 211, 219)
METAL_DARK = (96, 106, 118)
JOINT = (148, 158, 170)
DARK = (22, 22, 28)
ORANGE = (255, 150, 40)
GLASS = (214, 242, 248)
TEAL = (20, 170, 160)


def draw_cloud(cx, cy, s):
    fill_circle(cx, cy, 26 * s // 2, WHITE)
    fill_circle(cx - 30 * s // 2, cy + 6 * s // 2, 19 * s // 2, WHITE)
    fill_circle(cx + 30 * s // 2, cy + 6 * s // 2, 21 * s // 2, WHITE)
    fill_circle(cx + 4 * s // 2, cy + 10 * s // 2, 22 * s // 2, WHITE)


def draw_umbrella():
    # pole
    draw_line(272, 762, 272, 452, WOOD_DARK, 9)
    # canopy: half-disc fan of alternating wedges
    cx, cy, r = 272, 508, 196
    wedges = 12
    for i in range(wedges):
        a0 = math.pi + i * math.pi / wedges
        a1 = math.pi + (i + 1) * math.pi / wedges
        pts = [(cx, cy)]
        steps = 6
        for k in range(steps + 1):
            a = a0 + (a1 - a0) * k / steps
            pts.append((int(cx + r * math.cos(a)), int(cy + r * math.sin(a))))
        fill_poly(pts, RED if i % 2 == 0 else WHITE)
    # canopy rim + tip
    draw_line(cx - r, cy, cx + r, cy, WOOD_DARK, 5)
    draw_line(cx, cy - r, cx, cy - r - 26, WOOD_DARK, 6)
    fill_circle(cx, cy - r - 30, 8, RED)


def draw_deckchair():
    # fabric: backrest and seat as two quads with stripes
    back = [(318, 596), (368, 580), (452, 690), (408, 706)]
    seat = [(408, 706), (452, 690), (596, 748), (560, 772)]
    fill_poly(back, TEAL)
    fill_poly(seat, TEAL)
    for t in (0.25, 0.55, 0.85):
        x0 = int(back[0][0] + (back[3][0] - back[0][0]) * t)
        y0 = int(back[0][1] + (back[3][1] - back[0][1]) * t)
        x1 = int(back[1][0] + (back[2][0] - back[1][0]) * t)
        y1 = int(back[1][1] + (back[2][1] - back[1][1]) * t)
        draw_line(x0, y0, x1, y1, WHITE, 10)
        x0 = int(seat[0][0] + (seat[3][0] - seat[0][0]) * t)
        y0 = int(seat[0][1] + (seat[3][1] - seat[0][1]) * t)
        x1 = int(seat[1][0] + (seat[2][0] - seat[1][0]) * t)
        y1 = int(seat[1][1] + (seat[2][1] - seat[1][1]) * t)
        draw_line(x0, y0, x1, y1, WHITE, 10)
    # wooden frame
    draw_line(318, 596, 300, 700, WOOD, 10)
    draw_line(300, 700, 408, 706, WOOD, 10)
    draw_line(408, 706, 380, 792, WOOD, 10)
    draw_line(560, 772, 596, 748, WOOD, 10)
    draw_line(592, 758, 606, 806, WOOD, 10)
    draw_line(318, 596, 452, 690, WOOD_DARK, 6)


def draw_robot():
    # legs stretched out along the seat
    draw_line(452, 706, 560, 736, JOINT, 20)
    draw_line(458, 724, 572, 758, JOINT, 20)
    fill_rect(556, 716, 592, 740, METAL_DARK)   # foot 1
    fill_rect(568, 740, 604, 764, METAL_DARK)   # foot 2
    # pelvis + torso leaning back
    fill_poly([(408, 668), (462, 660), (478, 724), (420, 734)], METAL_DARK)
    fill_poly([(352, 588), (404, 576), (462, 660), (408, 668)], METAL)
    draw_line(352, 588, 404, 576, METAL_DARK, 5)
    draw_line(404, 576, 462, 660, METAL_DARK, 5)
    # chest light: it is switched to holiday mode
    fill_circle(408, 622, 9, ORANGE)
    fill_circle(408, 622, 13, METAL_DARK)
    fill_circle(408, 622, 9, ORANGE)
    # far arm resting on the seat
    draw_line(420, 640, 486, 700, JOINT, 16)
    fill_circle(492, 704, 11, METAL_DARK)
    # neck + head
    fill_rect(338, 548, 366, 576, JOINT)
    fill_circle(352, 520, 42, METAL)
    fill_circle(352, 520, 42, METAL)  # keep fill solid
    # head outline feel: darker rim at the bottom of the head
    draw_line(318, 548, 386, 548, METAL_DARK, 5)
    # antenna with a red ball -- it is ignoring your messages
    draw_line(352, 480, 352, 446, METAL_DARK, 6)
    fill_circle(352, 440, 9, RED)
    # ear caps
    fill_rect(306, 506, 318, 536, METAL_DARK)
    fill_rect(386, 506, 398, 536, METAL_DARK)
    # sunglasses: one cool black band, two lenses, a shine
    fill_rect(314, 500, 390, 532, DARK)
    fill_rect(314, 500, 348, 532, (38, 38, 46))
    fill_rect(356, 500, 390, 532, (38, 38, 46))
    draw_line(322, 526, 340, 506, WHITE, 4)
    draw_line(364, 526, 382, 506, WHITE, 4)
    # smug little smile
    draw_line(334, 552, 346, 558, DARK, 4)
    draw_line(346, 558, 360, 552, DARK, 4)
    # near arm raised, holding the cocktail
    draw_line(372, 596, 322, 560, JOINT, 16)
    draw_line(322, 560, 300, 512, JOINT, 16)
    fill_circle(298, 508, 11, METAL_DARK)
    draw_cocktail(298, 500)


def draw_cocktail(hx, hy):
    # mini umbrella first (behind the glass rim)
    draw_line(hx - 6, hy - 6, hx - 26, hy - 34, PINK, 4)
    pts = []
    for k in range(7):
        a = math.pi + k * math.pi / 6
        pts.append((int(hx - 26 + 20 * math.cos(a)), int(hy - 34 + 20 * math.sin(a))))
    fill_poly([(hx - 26, hy - 34)] + pts, PINK)
    # straw
    draw_line(hx + 8, hy - 2, hx + 24, hy - 30, RED, 5)
    # glass: bowl outline + orange drink
    fill_poly([(hx - 26, hy - 8), (hx + 26, hy - 8), (hx, hy + 22)], GLASS)
    fill_poly([(hx - 19, hy - 4), (hx + 19, hy - 4), (hx, hy + 15)], ORANGE)
    draw_line(hx, hy + 22, hx, hy + 38, GLASS, 5)
    draw_line(hx - 14, hy + 40, hx + 14, hy + 40, GLASS, 5)


def draw_sign():
    draw_line(782, 690, 782, 806, WOOD_DARK, 12)
    fill_rect(676, 612, 884, 692, SIGN)
    fill_rect(676, 612, 884, 622, SIGN_EDGE)
    fill_rect(676, 682, 884, 692, SIGN_EDGE)
    fill_rect(676, 612, 686, 692, SIGN_EDGE)
    fill_rect(874, 612, 884, 692, SIGN_EDGE)
    draw_text("OUT OF", 780, 626, 3, SIGN_TEXT)
    draw_text("OFFICE", 780, 652, 3, SIGN_TEXT)


def draw_beach_ball():
    cx, cy, r = 906, 792, 30
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                band = (dx + r) // 20 % 3
                color = (RED, WHITE, SUN)[band]
                i = ((cy + dy) * W + (cx + dx)) * 3
                buf[i:i + 3] = bytes(color)
    fill_circle(cx - 8, cy - 12, 5, WHITE)


def draw_scene():
    # caption bars
    fill_rect(0, 0, W, 150, BLACK)
    fill_rect(0, 850, W, H, BLACK)

    # sky, sea, sand
    fill_rect(0, 150, W, 470, SKY)
    fill_rect(0, 470, W, 606, SEA)
    fill_rect(0, 470, W, 486, SEA_DEEP)
    fill_rect(0, 606, W, 850, SAND)
    fill_rect(0, 606, W, 618, SAND_DARK)

    # sun with rays
    for k in range(8):
        a = k * math.pi / 4 + 0.2
        draw_line(int(872 + 66 * math.cos(a)), int(248 + 66 * math.sin(a)),
                  int(872 + 88 * math.cos(a)), int(248 + 88 * math.sin(a)),
                  SUN_RAY, 7)
    fill_circle(872, 248, 52, SUN)

    draw_cloud(168, 238, 2)
    draw_cloud(620, 196, 2)
    # birds
    draw_line(500, 268, 516, 258, METAL_DARK, 4)
    draw_line(516, 258, 532, 268, METAL_DARK, 4)
    draw_line(556, 292, 570, 283, METAL_DARK, 4)
    draw_line(570, 283, 584, 292, METAL_DARK, 4)

    # wavelets on the sea
    for (x, y, ln) in ((90, 512, 52), (240, 552, 64), (700, 520, 58),
                       (830, 566, 66), (470, 580, 48), (620, 496, 44)):
        draw_line(x, y, x + ln, y, WHITE, 5)

    # sand speckles (fixed-seed LCG: deterministic)
    seed = 123456789
    for _ in range(90):
        seed = (1103515245 * seed + 12345) % (1 << 31)
        x = seed % 980 + 10
        seed = (1103515245 * seed + 12345) % (1 << 31)
        y = 630 + seed % 205
        fill_rect(x, y, x + 5, y + 3, SAND_DARK)

    draw_umbrella()
    draw_deckchair()
    draw_robot()
    draw_sign()
    draw_beach_ball()

    # captions
    top1 = "I TOLD MY AI AGENT"
    top2 = "TO CLEAR MY SCHEDULE"
    bot1 = "NOW IT'S ON A BEACH IN BALI"
    bot2 = "I'M STILL IN MEETINGS"
    draw_text(top1, W // 2, 16, fit_scale(top1), WHITE)
    draw_text(top2, W // 2, 82, fit_scale(top2), WHITE)
    draw_text(bot1, W // 2, 866, fit_scale(bot1), WHITE)
    draw_text(bot2, W // 2, 920, fit_scale(bot2), WHITE)


def main():
    draw_scene()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    save_png(path)
    os.chmod(path, 0o644)
    print("wrote", path)


if __name__ == "__main__":
    main()


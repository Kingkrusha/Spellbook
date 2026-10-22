"""A small QR code maker (byte mode, error correction level M, versions 1-10), so the DM can show the browser
address as a code a phone camera can open. Plain Python: no packages.

:func:`make` returns the code as rows of booleans (True = dark), without the quiet border around it.
"""

from __future__ import annotations

from typing import List, Optional

# version -> (error correction codewords per block, [(blocks, data codewords per block), ...]) at level M
_BLOCKS = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
          9: [6, 26, 46], 10: [6, 28, 50]}
_LEVEL_M = 0b00
MAX_VERSION = 10

# GF(256) with the QR polynomial x^8 + x^4 + x^3 + x^2 + 1
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _generator(n: int) -> List[int]:
    g = [1]
    for i in range(n):
        nxt = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            nxt[j] ^= c
            nxt[j + 1] ^= _gf_mul(c, _EXP[i])
        g = nxt
    return g


def _ec_codewords(data: List[int], n: int) -> List[int]:
    gen = _generator(n)
    rem = list(data) + [0] * n
    for i in range(len(data)):
        factor = rem[i]
        if factor:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gf_mul(gen[j], factor)
    return rem[len(data):]


def _capacity(version: int) -> int:
    return sum(b * d for b, d in _BLOCKS[version][1])


def _codewords(data: bytes, version: int) -> List[int]:
    bits: List[int] = []

    def put(value: int, length: int) -> None:
        bits.extend((value >> (length - 1 - i)) & 1 for i in range(length))

    put(0b0100, 4)                                      # byte mode
    put(len(data), 8 if version < 10 else 16)
    for b in data:
        put(b, 8)
    cap = _capacity(version) * 8
    put(0, min(4, cap - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    filler = 0
    while len(words) < cap // 8:
        words.append(0x11 if filler % 2 else 0xEC)
        filler += 1
    # split into blocks, add error correction, interleave
    ec_n, groups = _BLOCKS[version]
    blocks, pos = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[pos:pos + size])
            pos += size
    ecs = [_ec_codewords(b, ec_n) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out.extend(b[i] for b in blocks if i < len(b))
    for i in range(ec_n):
        out.extend(e[i] for e in ecs)
    return out


def _bch(value: int, poly: int, poly_bits: int) -> int:
    v = value << (poly_bits - 1)
    while v.bit_length() >= poly_bits:
        v ^= poly << (v.bit_length() - poly_bits)
    return v


def _format_bits(mask: int) -> int:
    data = (_LEVEL_M << 3) | mask
    return ((data << 10) | _bch(data, 0x537, 11)) ^ 0x5412


def _version_bits(version: int) -> int:
    return (version << 12) | _bch(version, 0x1F25, 13)


_MASKS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


class _Matrix:
    def __init__(self, version: int):
        self.version = version
        self.size = n = version * 4 + 17
        self.dark = [[False] * n for _ in range(n)]
        self.fixed = [[False] * n for _ in range(n)]
        self._functions()

    def set(self, r: int, c: int, dark: bool) -> None:
        self.dark[r][c] = dark
        self.fixed[r][c] = True

    def _functions(self) -> None:
        n = self.size
        for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
            for dr in range(-1, 8):
                for dc in range(-1, 8):
                    r, c = r0 + dr, c0 + dc
                    if 0 <= r < n and 0 <= c < n:
                        ring = max(abs(dr - 3), abs(dc - 3))
                        self.set(r, c, ring != 2 and ring != 4)
        for i in range(8, n - 8):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        pos = _ALIGN[self.version]
        last = pos[-1] if pos else 0
        for r in pos:
            for c in pos:
                if (r, c) in ((6, 6), (6, last), (last, 6)):
                    continue                        # it would sit on a finder
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        self.set(r + dr, c + dc, max(abs(dr), abs(dc)) != 1)
        # reserve the format areas (filled in later) and the dark module
        for i in range(9):
            if not self.fixed[8][i]:
                self.set(8, i, False)
            if not self.fixed[i][8]:
                self.set(i, 8, False)
        for i in range(8):
            self.set(8, n - 1 - i, False)
            self.set(n - 1 - i, 8, False)
        self.set(n - 8, 8, True)
        if self.version >= 7:
            bits = _version_bits(self.version)
            for i in range(18):
                bit = bool((bits >> i) & 1)
                a, b = n - 11 + i % 3, i // 3
                self.set(a, b, bit)
                self.set(b, a, bit)

    def place(self, codewords: List[int]) -> None:
        n = self.size
        bits = [(w >> (7 - i)) & 1 for w in codewords for i in range(8)]
        k = 0
        c = n - 1
        upward = True
        while c > 0:
            if c == 6:
                c -= 1
            rows = range(n - 1, -1, -1) if upward else range(n)
            for r in rows:
                for cc in (c, c - 1):
                    if not self.fixed[r][cc]:
                        self.dark[r][cc] = bool(bits[k]) if k < len(bits) else False
                        k += 1
            upward = not upward
            c -= 2

    def masked(self, mask: int) -> List[List[bool]]:
        n = self.size
        fn = _MASKS[mask]
        out = [[self.dark[r][c] != (not self.fixed[r][c] and fn(r, c)) for c in range(n)] for r in range(n)]
        bits = _format_bits(mask)
        for i in range(15):
            bit = bool((bits >> i) & 1)
            # around the top-left finder: down column 8, then along row 8 to the left
            if i < 6:
                out[i][8] = bit
            elif i < 8:
                out[i + 1][8] = bit
            elif i == 8:
                out[8][7] = bit
            else:
                out[8][14 - i] = bit
            # the copy split between the other two finders
            if i < 8:
                out[8][n - 1 - i] = bit
            else:
                out[n - 15 + i][8] = bit
        out[n - 8][8] = True
        return out


def _penalty(m: List[List[bool]]) -> int:
    n = len(m)
    score = 0
    for grid in (m, [list(col) for col in zip(*m)]):
        for row in grid:
            run, prev = 0, None
            for v in row:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run, prev = 1, v
            if run >= 5:
                score += run - 2
            line = "".join("1" if v else "0" for v in row)
            for pattern in ("10111010000", "00001011101"):
                start = line.find(pattern)
                while start != -1:
                    score += 40
                    start = line.find(pattern, start + 1)
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(v for row in m for v in row)
    score += abs(dark * 20 - n * n * 10) // (n * n) * 10
    return score


def make(text: str, mask: Optional[int] = None) -> List[List[bool]]:
    """The QR code for ``text`` (UTF-8). Raises ValueError when it is too long for version 10 (about 210 bytes)."""
    data = text.encode("utf-8")
    version = next((v for v in range(1, MAX_VERSION + 1)
                    if 4 + (8 if v < 10 else 16) + 8 * len(data) <= _capacity(v) * 8), None)
    if version is None:
        raise ValueError("That is too long for a QR code here.")
    matrix = _Matrix(version)
    matrix.place(_codewords(data, version))
    if mask is not None:
        return matrix.masked(mask)
    options = [matrix.masked(k) for k in range(8)]
    return min(options, key=_penalty)


def to_image(rows: List[List[bool]], scale: int = 6, border: int = 4, dark=(0, 0, 0), light=(255, 255, 255)):
    """The code as a Pillow image, with the quiet border round it."""
    from PIL import Image
    n = len(rows)
    side = (n + border * 2) * scale
    img = Image.new("RGB", (side, side), light)
    px = img.load()
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v:
                for dy in range(scale):
                    for dx in range(scale):
                        px[(c + border) * scale + dx, (r + border) * scale + dy] = dark
    return img

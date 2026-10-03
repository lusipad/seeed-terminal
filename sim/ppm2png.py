#!/usr/bin/env python3
"""sim/out/*.ppm (P6) → PNG(zlib,无第三方依赖),转换后删除 ppm。"""
import glob
import os
import struct
import zlib


def ppm_to_png(src, dst):
    with open(src, "rb") as f:
        assert f.readline().strip() == b"P6"
        wh = f.readline().split()
        w, h = int(wh[0]), int(wh[1])
        assert f.readline().strip() == b"255"
        raw = f.read(w * h * 3)
    scanlines = b"".join(b"\x00" + raw[y * w * 3:(y + 1) * w * 3] for y in range(h))
    comp = zlib.compress(scanlines, 9)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    with open(dst, "wb") as f:
        f.write(png)


for ppm in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "out", "*.ppm"))):
    png = ppm[:-4] + ".png"
    ppm_to_png(ppm, png)
    os.remove(ppm)
    print(png, os.path.getsize(png), "bytes")

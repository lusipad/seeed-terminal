#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 HZK16.bin 生成板载中文字库头文件(单文件,点阵 + 索引):
   - libraries/WioKit/src/WioKitFontHz16.h
     · HZ16_FONT : 点阵数据(GB2312 区1-3 符号/全角标点 + 区16-55 一级汉字)
     · HZ16_INDEX: UTF-8(3字节) -> GB2312(2字节) 索引,按 UTF-8 排序供二分查找
   解码用 GBK 超集(让 — 等映射进区1),但只收录 HZK16 有字形的区。
   消费方:WioKitCjk.cpp(WioKit 库)。console/ 仍持有旧拷贝,不随本脚本再生。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "HZK16.bin")                       # 源字库
REPO = os.path.dirname(HERE)                                # 仓库根
OUT_PATH = os.path.join(REPO, "libraries", "WioKit", "src", "WioKitFontHz16.h")

data = open(SRC, "rb").read()
assert len(data) == 261696, f"unexpected HZK16 size {len(data)}"

# 嵌入的区:1(标点) 2(带圈符号) 3(全角ASCII/全角标点) 16-55(一级汉字)
ZONES = [1, 2, 3] + list(range(16, 56))
entries = []  # (utf8_bytes, gb_bytes)
glyphs = bytearray()


def blob_index(qu, wei):
    """glyph 在生成 blob 中的序号(单位:32字节)"""
    if qu in (1, 2, 3):
        return (qu - 1) * 94 + (wei - 1)
    return 94 * 3 + (qu - 16) * 94 + (wei - 1)


for qu in ZONES:
    for wei in range(1, 95):
        gb = bytes([0xA0 + qu, 0xA0 + wei])
        pos = blob_index(qu, wei) * 32
        try:
            ch = gb.decode("gbk")
            u8 = ch.encode("utf-8")
        except UnicodeDecodeError:
            glyphs.extend(b"\x00" * 32)
            continue
        if len(u8) != 3:  # 个别 2 字节 UTF-8 字符会破坏定长索引,剔除
            glyphs.extend(b"\x00" * 32)
            continue
        off = ((gb[0] - 0xA0 - 1) * 94 + (gb[1] - 0xA0 - 1)) * 32
        entries.append((u8, gb))
        glyphs.extend(data[off:off + 32])

entries.sort(key=lambda e: e[0])

# ---- WioKitFontHz16.h(点阵 + 索引) ----
with open(OUT_PATH, "w", newline="\n") as f:
    f.write("// 自动生成:HZK16 子集字库 + UTF-8->GB2312 索引(tools/gen_font.py 生成,勿手改)\n")
    f.write("// 点阵:GB2312 区1-3 符号/全角标点 + 区16-55 一级汉字(共 %d 字形 x 32B)\n" % (len(glyphs) // 32))
    f.write("// 索引:按 UTF-8 排序供二分查找,每项 5 字节 utf8[0..2] + gb[0] + gb[1]\n")
    f.write("#pragma once\n#include <stdint.h>\n\n")
    f.write(f"#define HZ16_GLYPH_COUNT {len(glyphs) // 32}\n")
    f.write(f"#define HZ16_INDEX_COUNT {len(entries)}\n\n")
    f.write("// 索引: qu 1-3 -> (qu-1)*94 + (wei-1); 16<=qu<=55 -> 282 + (qu-16)*94 + (wei-1) (单位:32字节)\n")
    f.write("const uint8_t HZ16_FONT[] = {\n")
    for i in range(0, len(glyphs), 16):
        f.write("  " + ",".join(f"0x{b:02X}" for b in glyphs[i:i + 16]) + ",\n")
    f.write("};\n\n")
    f.write("// 每项 5 字节: utf8[0..2] + gb[0] + gb[1]\n")
    f.write("const uint8_t HZ16_INDEX[] = {\n")
    flat = bytearray()
    for u8, gb in entries:
        flat.extend(u8)
        flat.extend(gb)
    for i in range(0, len(flat), 15):
        f.write("  " + ",".join(f"0x{b:02X}" for b in flat[i:i + 15]) + ",\n")
    f.write("};\n")
print("WioKitFontHz16.h:", len(glyphs) // 32, "glyphs,", len(entries), "entries")

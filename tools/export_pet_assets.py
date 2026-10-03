#!/usr/bin/env python3
"""生成 pet/pet_scene_data.h:
1. 共享 256 色 RGB565 调色板
2. 320x240 完整背景场景图 (包含小猫坐姿及空提示栏)
3. 14 种面部表情切片 (86x32)
"""
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_H = os.path.join(ROOT, "pet", "pet_scene_data.h")

sys.path.insert(0, ROOT)
import tools.build_pixel_pet as bpp

# 1. 基础场景图与全套表情联合调色板
base_img = Image.open(bpp.SRC_BASE).convert("RGB")

# 拼接包含完整房间背景及全部 14 种表情的复合图像，生成能完美覆盖所有场景与表情细节的 256 色全局调色板
comp_w = base_img.width + 100
comp_h = max(base_img.height, len(bpp.face_names) * 35)
composite = Image.new("RGB", (comp_w, comp_h))
composite.paste(base_img, (0, 0))
for idx, k in enumerate(bpp.face_names):
    composite.paste(bpp.faces[k], (base_img.width + 5, idx * 35))

q_comp = composite.quantize(256, method=Image.Quantize.MEDIANCUT)
pal_rgb = q_comp.getpalette()[:768] # 256 * 3

# 转 RGB565
pal_565 = []
for i in range(256):
    r, g, b = pal_rgb[i*3 : i*3+3]
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    pal_565.append(rgb565)

# 制作共用调色板的调色板模板图像
pal_template = Image.new("P", (1, 1))
pal_template.putpalette(pal_rgb + [0]*(768 - len(pal_rgb)))

# 基础场景 320x240 索引数据
q_base = base_img.quantize(palette=pal_template, dither=Image.Dither.NONE)
base_indices = list(q_base.getdata())

# 2. 14 种面部表情切片, 全部用相同的调色板量化
face_keys = [
    "normal", "blink", "happy", "sad", "listen", "think",
    "excited", "surprised", "shy", "confused", "sleepy", "sleep", "dizzy", "yawn"
]

face_indices = {}
for k in face_keys:
    f_img = bpp.faces[k].convert("RGB")
    f_q = f_img.quantize(palette=pal_template, dither=Image.Dither.NONE)
    face_indices[k] = list(f_q.getdata())

# 写入 C++ 头文件
with open(OUT_H, "w", encoding="utf-8") as f:
    f.write("// 自动生成的小维像素宠物场景与表情数据, 请勿手改\n")
    f.write("// 生成脚本: tools/export_pet_assets.py\n")
    f.write("#pragma once\n")
    f.write("#include <stdint.h>\n\n")

    f.write(f"const int PET_FACE_X = {bpp.FX0};\n")
    f.write(f"const int PET_FACE_Y = {bpp.FY0};\n")
    f.write(f"const int PET_FACE_W = {bpp.FW};\n")
    f.write(f"const int PET_FACE_H = {bpp.FH};\n\n")

    # 调色板
    f.write("// 256 色 RGB565 调色板 (512 字节)\n")
    f.write("const uint16_t PET_PALETTE[256] = {\n  ")
    for i, c in enumerate(pal_565):
        f.write(f"0x{c:04X}, ")
        if (i + 1) % 12 == 0:
            f.write("\n  ")
    f.write("\n};\n\n")

    # 基础场景 (320x240 字节)
    f.write("// 320x240 基础场景像素索引 (76,800 字节)\n")
    f.write("const uint8_t PET_SCENE_BG[76800] = {\n  ")
    for i, v in enumerate(base_indices):
        f.write(f"{v}, ")
        if (i + 1) % 32 == 0:
            f.write("\n  ")
    f.write("\n};\n\n")

    # 14 种面部表情
    f.write(f"// 14 种面部表情切片 ({bpp.FW}x{bpp.FH} = {bpp.FW*bpp.FH} 字节/个)\n")
    f.write(f"const uint8_t PET_FACES[14][{bpp.FW * bpp.FH}] = {{\n")
    for name in face_keys:
        f.write(f"  // {name}\n  {{\n    ")
        for i, v in enumerate(face_indices[name]):
            f.write(f"{v}, ")
            if (i + 1) % 32 == 0:
                f.write("\n    ")
        f.write("\n  },\n")
    f.write("};\n\n")

print(f"成功生成 {OUT_H}!")
print(f"调色板: 512 字节")
print(f"场景背景: {len(base_indices)} 字节 (75.0 KB)")
print(f"面部切片: 14 x {bpp.FW*bpp.FH} = {14 * bpp.FW * bpp.FH} 字节 (37.6 KB)")

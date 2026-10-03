#!/usr/bin/env python3
"""生成小维像素宠物的全套面部表情补丁与头文件"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_BASE = os.path.join(ROOT, "art", "room_pixel_base.png")

base = Image.open(SRC_BASE).convert("RGB")

# 面部裁剪区域 (覆盖双眼、鼻子、嘴巴、腮红)
# 宽 86, 高 32
FX0, FY0, FX1, FY1 = 112, 94, 198, 126
FW, FH = FX1 - FX0, FY1 - FY0

default_face = base.crop((FX0, FY0, FX1, FY1))

# 面部关键点在 86x32 面板内部的相对坐标:
# 原图左眼: x in [115..153], y in [96..122] -> 相对 x: [3..41], y: [2..28], 中心约 (22, 16)
# 原图右眼: x in [161..194], y in [96..122] -> 相对 x: [49..82], y: [2..28], 中心约 (65, 16)
# 鼻子: 相对 (41..44, 20..21)
# 嘴巴: 相对 (33..52, 22..30)
# 腮红: 左 (0..12, 18..28), 右 (70..82, 18..28)

# 颜色定义
DARK = (28, 18, 22)         # 轮廓/线条
WHITE = (237, 230, 212)     # 面部白毛
PEACH = (247, 169, 114)     # 额头桃橙毛 (从原图真实取样)
TRANS = (242, 205, 165)     # 桃橙与白色交界渐变过渡色
BLUSH = (255, 145, 155)     # 腮红
BLUSH_DEEP = (255, 110, 130)# 深色大腮红
NOSE = (215, 100, 120)      # 鼻子
WATER = (110, 200, 255)     # 眼泪/水蓝
MOUTH_RED = (200, 55, 75)   # 张嘴内部深红
TONGUE_PINK = (255, 150, 165) # 小舌头粉红

def make_clean_blank():
    """彻底清除左右眼窝内的所有旧眼圈黑线与残影，保留自然的渐变肤色"""
    f = default_face.copy()
    # 左眼眼窝: x in [10..36], y in [4..23]
    for y in range(4, 24):
        for x in range(10, 37):
            if y <= 15: col = PEACH
            elif y == 16: col = TRANS
            else: col = BLUSH if (x <= 12 and y >= 19) else WHITE
            f.putpixel((x, y), col)
    # 右眼眼窝: x in [52..78], y in [4..23]
    for y in range(4, 24):
        for x in range(52, 79):
            if y <= 15: col = PEACH
            elif y == 16: col = TRANS
            else: col = BLUSH if (x >= 75 and y >= 19) else WHITE
            f.putpixel((x, y), col)
    return f

def clear_mouth(f):
    """彻底擦除原版的微笑嘴，防止新嘴型与旧嘴重叠产生杂点"""
    for y in range(23, 32):
        for x in range(30, 54):
            f.putpixel((x, y), WHITE)

def draw_caret(f, cx, cy):
    """绘制 2 像素宽经典像素艺术笑眯眼 ^ """
    pts = [
        (cx-1, cy), (cx, cy),
        (cx-2, cy+1), (cx-1, cy+1), (cx, cy+1), (cx+1, cy+1),
        (cx-4, cy+2), (cx-3, cy+2), (cx-2, cy+2),
        (cx-6, cy+3), (cx-5, cy+3), (cx-4, cy+3),
        (cx-8, cy+4), (cx-7, cy+4), (cx-6, cy+4),
        (cx-10, cy+5), (cx-9, cy+5), (cx-8, cy+5),
        (cx+1, cy+2), (cx+2, cy+2), (cx+3, cy+2),
        (cx+3, cy+3), (cx+4, cy+3), (cx+5, cy+3),
        (cx+5, cy+4), (cx+6, cy+4), (cx+7, cy+4),
        (cx+7, cy+5), (cx+8, cy+5), (cx+9, cy+5),
    ]
    for px, py in pts:
        f.putpixel((px, py), DARK)

def draw_sleep_curve(f, cx, cy):
    """绘制安详闭眼弧线 ︶ """
    pts = [
        (cx-9, cy), (cx-8, cy),
        (cx-7, cy+1), (cx-6, cy+1),
        (cx-5, cy+2), (cx-4, cy+2),
        (cx-3, cy+3), (cx-2, cy+3), (cx-1, cy+3), (cx, cy+3), (cx+1, cy+3), (cx+2, cy+3), (cx+3, cy+3),
        (cx+4, cy+2), (cx+5, cy+2),
        (cx+6, cy+1), (cx+7, cy+1),
        (cx+8, cy), (cx+9, cy),
    ]
    for px, py in pts:
        f.putpixel((px, py), DARK)
        f.putpixel((px, py+1), DARK)

faces = {}

# 0. F_NORMAL: 原版概念图大眼睛 + 微笑嘴 (100% 原始切片)
faces["normal"] = default_face.copy()

# 1. F_BLINK: 眨眼 (水平闭眼细线 - - + 默认微笑嘴)
f = make_clean_blank()
for x in range(14, 33):
    f.putpixel((x, 15), DARK); f.putpixel((x, 16), DARK)
for x in range(56, 75):
    f.putpixel((x, 15), DARK); f.putpixel((x, 16), DARK)
faces["blink"] = f

# 2. F_HAPPY: 开心 (经典像素弯弯笑眼 ^ ^ + 默认微笑嘴)
f = make_clean_blank()
draw_caret(f, 23, 12)
draw_caret(f, 65, 12)
faces["happy"] = f

# 3. F_EXCITED: 兴奋 (灿烂笑眼 ^ ^ + 欢脱张大笑嘴与粉红小舌头)
f = make_clean_blank()
draw_caret(f, 23, 12)
draw_caret(f, 65, 12)
clear_mouth(f)
d = ImageDraw.Draw(f)
d.chord([37, 23, 47, 30], start=0, end=180, fill=MOUTH_RED, outline=DARK)
d.chord([39, 26, 45, 30], start=0, end=180, fill=TONGUE_PINK)
faces["excited"] = f

# 4. F_SAD: 难过 (原版大眼睛 + 眼角泪珠 + 倒撇嘴角 ⌒)
f = default_face.copy()
clear_mouth(f)
d = ImageDraw.Draw(f)
d.arc([37, 25, 47, 32], start=180, end=360, fill=DARK, width=2)
d.ellipse([5, 19, 11, 26], fill=WATER, outline=DARK)
faces["sad"] = f

# 5. F_LISTEN: 聆听 (原版大眼睛 + 专注圆嘴 'o')
f = default_face.copy()
clear_mouth(f)
d = ImageDraw.Draw(f)
d.ellipse([39, 23, 45, 29], fill=MOUTH_RED, outline=DARK)
faces["listen"] = f

# 6. F_THINK: 思考 (黑珠往右上张望 + 平线嘴)
f = make_clean_blank()
d = ImageDraw.Draw(f)
d.ellipse([18, 6, 34, 21], fill=DARK)
d.rectangle([26, 8, 30, 12], fill=(255, 255, 255))
d.ellipse([60, 6, 76, 21], fill=DARK)
d.rectangle([68, 8, 72, 12], fill=(255, 255, 255))
clear_mouth(f)
d.line([(38, 25), (46, 25)], fill=DARK, width=2)
faces["think"] = f

# 7. F_SURPRISED: 惊讶 (圆溜溜圆眼 + 'O' 型嘴)
f = make_clean_blank()
d = ImageDraw.Draw(f)
d.ellipse([14, 7, 32, 23], fill=DARK)
d.ellipse([18, 11, 23, 16], fill=(255, 255, 255))
d.ellipse([56, 7, 74, 23], fill=DARK)
d.ellipse([60, 11, 65, 16], fill=(255, 255, 255))
clear_mouth(f)
d.ellipse([38, 23, 46, 30], fill=MOUTH_RED, outline=DARK)
faces["surprised"] = f

# 8. F_SHY: 害羞 (> < 眯眼 + 深色红晕 + 波浪嘴)
f = make_clean_blank()
d = ImageDraw.Draw(f)
d.line([(14, 11), (26, 16), (14, 21)], fill=DARK, width=2)
d.line([(74, 11), (62, 16), (74, 21)], fill=DARK, width=2)
d.ellipse([2, 17, 14, 28], fill=BLUSH_DEEP)
d.ellipse([72, 17, 84, 28], fill=BLUSH_DEEP)
clear_mouth(f)
d.line([(37, 26), (41, 24), (45, 26), (49, 24)], fill=DARK, width=2)
faces["shy"] = f

# 9. F_CONFUSED: 疑惑 (左眼睁右眼眯 + 歪斜嘴)
f = default_face.copy()
for y in range(4, 24):
    for x in range(52, 79):
        if y <= 15: col = PEACH
        elif y == 16: col = TRANS
        else: col = BLUSH if (x >= 75 and y >= 19) else WHITE
        f.putpixel((x, y), col)
draw_caret(f, 65, 12)
clear_mouth(f)
d = ImageDraw.Draw(f)
d.line([(38, 27), (47, 24)], fill=DARK, width=2)
faces["confused"] = f

# 10. F_SLEEPY: 犯困 (半眯下垂眼 + 小哈欠嘴)
f = make_clean_blank()
d = ImageDraw.Draw(f)
d.chord([14, 8, 32, 22], start=0, end=180, fill=DARK)
d.line([(12, 15), (34, 15)], fill=DARK, width=2)
d.chord([56, 8, 74, 22], start=0, end=180, fill=DARK)
d.line([(54, 15), (76, 15)], fill=DARK, width=2)
clear_mouth(f)
d.ellipse([39, 24, 45, 29], fill=MOUTH_RED, outline=DARK)
faces["sleepy"] = f

# 11. F_SLEEP: 沉睡 (弯弯安详闭眼 ︶ ︶ + 恬静小嘴)
f = make_clean_blank()
draw_sleep_curve(f, 23, 14)
draw_sleep_curve(f, 65, 14)
clear_mouth(f)
d = ImageDraw.Draw(f)
d.line([(39, 25), (45, 25)], fill=DARK, width=2)
faces["sleep"] = f

# 12. F_DIZZY: 眩晕 (经典 X X 像素眼 + 波浪眩晕嘴)
f = make_clean_blank()
d = ImageDraw.Draw(f)
d.line([(15, 10), (31, 22)], fill=DARK, width=3)
d.line([(15, 22), (31, 10)], fill=DARK, width=3)
d.line([(57, 10), (73, 22)], fill=DARK, width=3)
d.line([(57, 22), (73, 10)], fill=DARK, width=3)
clear_mouth(f)
d.line([(37, 26), (41, 24), (45, 26), (49, 24)], fill=DARK, width=2)
faces["dizzy"] = f

# 13. F_YAWN: 大哈欠 (安详闭眼 + 大张哈欠嘴与小舌头)
f = make_clean_blank()
draw_sleep_curve(f, 23, 14)
draw_sleep_curve(f, 65, 14)
clear_mouth(f)
d = ImageDraw.Draw(f)
d.chord([37, 22, 47, 30], start=0, end=180, fill=MOUTH_RED, outline=DARK)
d.chord([39, 26, 45, 30], start=0, end=180, fill=TONGUE_PINK)
faces["yawn"] = f

# 拼一张所有表情的大预览图 (2 列 x 7 行)
preview_w = FW * 2 + 30
preview_h = (FH + 10) * 7 + 20
grid_img = Image.new("RGB", (preview_w, preview_h), (35, 25, 30))

face_names = list(faces.keys())
for i, name in enumerate(face_names):
    col = i % 2
    row = i // 2
    x = 10 + col * (FW + 10)
    y = 10 + row * (FH + 10)
    grid_img.paste(faces[name], (x, y))

out_preview = os.path.join(ROOT, "art", "all_faces_preview.png")
grid_img.save(out_preview)
print("saved art/all_faces_preview.png with 14 faces!")

# 保存每个表情独立图并测试合成到小房间场景
for name in ["happy", "sleep", "excited", "sad", "dizzy"]:
    scene = base.copy()
    scene.paste(faces[name], (FX0, FY0))
    scene.save(os.path.join(ROOT, "art", f"preview_scene_{name}.png"))
print("saved scene previews in art/")

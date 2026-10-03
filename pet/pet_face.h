// ---- 宠物外观:像素艺术小房间 + 概念图小猫全套表情 ----
// 100% 还原概念图 2 的小房间场景、坐垫与小猫形象
#pragma once
#include <Arduino.h>
#include <Seeed_GFX.h>
#include <WioKitCjk.h>
#include "pet_scene_data.h"

enum Face {
  F_NORMAL, F_BLINK, F_HAPPY, F_SAD, F_LISTEN, F_THINK,
  F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SLEEPY, F_SLEEP, F_DIZZY, F_YAWN
};

const int CX = 160, CY = 110;
const uint16_t C_BUBBLE = 0xFFFF;
const uint16_t C_EDGE = 0x2124;       // 像素深色描边
const uint16_t C_WATER = 0x5DFF;      // 泪滴/声波
const uint16_t C_GOLD = 0xFEA0;       // 星光/音符
const uint16_t C_BOTTOM_BG = 0x0862;  // 底部黑框内胆颜色

// 装饰层区域 (左右两侧墙壁空旷区域, 必须位于 y >= 96, 绝不能侵入气泡 y=8..92)
const int DECO_LX = 16, DECO_RX = 254, DECO_Y = 96, DECO_W = 46, DECO_H = 42;

// 还原背景指定矩形区域 (用于擦除气泡或擦除装饰, 毫秒级无闪烁)
void restoreSceneRect(int rx, int ry, int rw, int rh) {
  if (rx < 0) { rw += rx; rx = 0; }
  if (ry < 0) { rh += ry; ry = 0; }
  if (rx + rw > 320) rw = 320 - rx;
  if (ry + rh > 240) rh = 240 - ry;
  if (rw <= 0 || rh <= 0) return;

  uint16_t line[320];
  for (int y = ry; y < ry + rh; y++) {
    const uint8_t* src = &PET_SCENE_BG[y * 320 + rx];
    for (int x = 0; x < rw; x++) {
      line[x] = PET_PALETTE[src[x]];
    }
    display.pushImage(rx, y, rw, 1, line);
  }
}

// 绘制面部表情切片 (只刷新 86x32 的微小区域, 极速无闪烁)
void drawFeatures(int f, int look = 0) {
  if (f < 0 || f >= 14) f = F_NORMAL;
  const uint8_t* patch = PET_FACES[f];
  uint16_t line[PET_FACE_W];
  int drawX = PET_FACE_X + look;
  for (int y = 0; y < PET_FACE_H; y++) {
    const uint8_t* src = &patch[y * PET_FACE_W];
    for (int x = 0; x < PET_FACE_W; x++) {
      line[x] = PET_PALETTE[src[x]];
    }
    display.pushImage(drawX, PET_FACE_Y + y, PET_FACE_W, 1, line);
  }
}

// 只重画眼部区域 (兼容旧接口, 直接映射到 drawFeatures)
void drawEyesOnly(int f, int look = 0) {
  drawFeatures(f, look);
}

// 整屏绘制: 绘制概念图基础场景 + 应用指定表情 (仅在切换状态时调用)
void drawPet(int f) {
  uint16_t line[320];
  for (int y = 0; y < 240; y++) {
    const uint8_t* src = &PET_SCENE_BG[y * 320];
    for (int x = 0; x < 320; x++) {
      line[x] = PET_PALETTE[src[x]];
    }
    display.pushImage(0, y, 320, 1, line);
  }
  if (f != F_NORMAL) {
    drawFeatures(f, 0);
  }
}

// ---- 装饰层 ----
void clearDeco() {
  restoreSceneRect(DECO_LX, DECO_Y, DECO_W, DECO_H);
  restoreSceneRect(DECO_RX, DECO_Y, DECO_W, DECO_H);
}

void drawSparkle(int x, int y, int r, uint16_t c) {
  display.drawFastHLine(x - r, y, 2 * r + 1, c);
  display.drawFastVLine(x, y - r, 2 * r + 1, c);
  display.drawLine(x - r / 2, y - r / 2, x + r / 2, y + r / 2, c);
  display.drawLine(x - r / 2, y + r / 2, x + r / 2, y - r / 2, c);
}

void drawNote(int x, int y, uint16_t c) {  // ♪
  display.fillCircle(x, y, 3, c);
  display.drawFastVLine(x + 3, y - 12, 12, c);
  display.drawLine(x + 3, y - 12, x + 8, y - 8, c);
}

void drawGlyph(const char* s, int x, int y, int size, uint16_t c) {
  display.setTextSize(size);
  display.setTextColor(c);
  display.drawString(s, x, y);
}

void drawEmoteDeco(int f, int phase) {
  clearDeco();
  switch (f) {
    case F_EXCITED:  // 星光闪烁(两组位置交替)
      if (phase % 2 == 0) {
        drawSparkle(DECO_RX + 16, DECO_Y + 12, 5, C_GOLD);
        drawSparkle(DECO_LX + 24, DECO_Y + 24, 4, C_GOLD);
      } else {
        drawSparkle(DECO_RX + 26, DECO_Y + 24, 4, C_GOLD);
        drawSparkle(DECO_LX + 14, DECO_Y + 12, 5, C_GOLD);
      }
      break;
    case F_SURPRISED:
      drawGlyph("!", DECO_RX + 16, DECO_Y + 10, 3, TFT_YELLOW);
      break;
    case F_CONFUSED:
      drawGlyph("?", DECO_RX + 16, DECO_Y + 10, 3, C_WATER);
      break;
    default:
      break;
  }
}

void drawSoundBars(int phase) {  // 聆听:两侧声波条轮流起伏
  clearDeco();
  static const int H[3][3] = {{8, 14, 20}, {14, 20, 8}, {20, 8, 14}};
  for (int k = 0; k < 3; k++) {
    const int h = H[phase % 3][k];
    const int y = DECO_Y + 20 - h / 2;
    display.fillRect(DECO_RX + 4 + 10 * k, y, 5, h, C_WATER);
    display.fillRect(DECO_LX + 26 - 10 * k, y, 5, h, C_WATER);
  }
}

void drawThinkDots(int count) {  // 思考:右侧 1~3 个点
  restoreSceneRect(DECO_RX, DECO_Y + 12, DECO_W, 16);
  for (int k = 0; k < count; k++) display.fillCircle(DECO_RX + 8 + 10 * k, DECO_Y + 20, 3, TFT_WHITE);
}

void drawZzz(int phase) {  // 睡觉:右侧 z 依次变大
  clearDeco();
  const int n = phase % 4;
  if (n >= 1) drawGlyph("z", DECO_RX + 4, DECO_Y + 24, 1, TFT_LIGHTGREY);
  if (n >= 2) drawGlyph("z", DECO_RX + 12, DECO_Y + 14, 2, TFT_LIGHTGREY);
  if (n >= 3) drawGlyph("Z", DECO_RX + 20, DECO_Y + 4, 3, TFT_LIGHTGREY);
}

void drawBubbleFrame(int x, int y, int w, int h) {
  // 实体纯色填充 (阶梯圆角无缝填充, 绝无缺失孔洞)
  display.fillRect(x + 3, y + 1, w - 6, h - 2, C_BUBBLE);
  display.fillRect(x + 1, y + 3, 2, h - 6, C_BUBBLE);
  display.fillRect(x + w - 3, y + 3, 2, h - 6, C_BUBBLE);
  display.drawPixel(x + 2, y + 2, C_BUBBLE);
  display.drawPixel(x + w - 3, y + 2, C_BUBBLE);
  display.drawPixel(x + 2, y + h - 3, C_BUBBLE);
  display.drawPixel(x + w - 3, y + h - 3, C_BUBBLE);

  // 像素描边 (C_EDGE)
  display.drawFastHLine(x + 3, y, w - 6, C_EDGE);
  display.drawFastHLine(x + 3, y + h - 1, w - 6, C_EDGE);
  display.drawFastVLine(x, y + 3, h - 6, C_EDGE);
  display.drawFastVLine(x + w - 1, y + 3, h - 6, C_EDGE);

  // 四角阶梯像素
  display.drawPixel(x + 2, y + 1, C_EDGE);
  display.drawPixel(x + 1, y + 2, C_EDGE);
  display.drawPixel(x + w - 3, y + 1, C_EDGE);
  display.drawPixel(x + w - 2, y + 2, C_EDGE);
  display.drawPixel(x + 2, y + h - 2, C_EDGE);
  display.drawPixel(x + 1, y + h - 3, C_EDGE);
  display.drawPixel(x + w - 3, y + h - 2, C_EDGE);
  display.drawPixel(x + w - 2, y + h - 3, C_EDGE);

  // 气泡尾巴 (指向猫咪额头中心 160, y+h+8)
  const int tx = 160, ty = y + h - 1;
  display.fillTriangle(tx - 7, ty, tx + 7, ty, tx, ty + 8, C_BUBBLE);
  display.drawLine(tx - 8, ty, tx, ty + 8, C_EDGE);
  display.drawLine(tx + 8, ty, tx, ty + 8, C_EDGE);
  display.drawFastHLine(tx - 7, ty, 15, C_BUBBLE);  // 抹平气泡底部与尾巴连接处的线
}

void drawBubbleText(const String& t1, uint16_t c1, const String& t2, uint16_t c2) {
  // 气泡覆盖 y=8..92, x=14..306, 尾巴指向 y=100
  drawBubbleFrame(14, 8, 292, 84);
  const int y = drawTextCJK(t1, 26, 16, 290, c1, C_BUBBLE);
  if (t2.length()) {
    if (y < 46) {
      display.drawFastHLine(26, 42, 268, 0xD6B8);
      drawTextCJK(t2, 26, 48, 290, c2, C_BUBBLE);
    } else {
      drawTextCJK(t2, 26, y + 2, 290, c2, C_BUBBLE);
    }
  }
}


// ---- 宠物外观:几何像素风 + 表情 ----
// 依赖宿主先声明 Seeed_GFX display 并包含 cjk.h
// 整只宠物只在 drawPet() 里整画一次(状态切换时);表情/动画只用 drawFeatures/drawEyesOnly/装饰层局部重绘,防闪烁
#pragma once

enum Face {
  F_NORMAL, F_BLINK, F_HAPPY, F_SAD, F_LISTEN, F_THINK,
  F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SLEEPY, F_SLEEP, F_DIZZY, F_YAWN
};

const int CX = 160, CY = 152, R = 40;          // 脸中心与半径
const uint16_t C_BODY = 0xFDEF;                // 暖灰白
const uint16_t C_EDGE = 0x8410;                // 描边
const uint16_t C_BLUSH = 0xFB60;               // 腮红
const uint16_t C_BUBBLE = 0xFFFF;
const uint16_t C_WATER = 0x5DFF;               // 泪滴/声波
const uint16_t C_GOLD = 0xFEA0;                // 星光/音符

// 装饰层:脸两侧黑底区域,不与气泡(y<=116)、耳朵、提示区(y>=212)重叠
const int DECO_LX = CX - 84, DECO_RX = CX + 44, DECO_Y = CY - 36, DECO_W = 40, DECO_H = 56;

// look:眼睛整体水平偏移(张望/歪头)
void drawEyes(int look, int f, uint16_t color) {
  const int ex[2] = {CX + look - 19, CX + look + 13};
  const int ey = CY - 12;
  switch (f) {
    case F_BLINK:
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey + 3, 6, 3, color);
      break;
    case F_HAPPY:
      for (int i = 0; i < 2; i++) {
        display.drawLine(ex[i] - 1, ey + 4, ex[i] + 2, ey - 2, color);
        display.drawLine(ex[i] + 2, ey - 2, ex[i] + 5, ey + 4, color);
      }
      break;
    case F_EXCITED:  // 加粗的 ^ ^
      for (int i = 0; i < 2; i++) {
        for (int k = 0; k < 2; k++) {
          display.drawLine(ex[i] - 1, ey + 4 - k, ex[i] + 2, ey - 2 - k, color);
          display.drawLine(ex[i] + 2, ey - 2 - k, ex[i] + 5, ey + 4 - k, color);
        }
      }
      break;
    case F_SAD:
      for (int i = 0; i < 2; i++) display.drawLine(ex[i] - 1, ey - 2, ex[i] - 1, ey + 5, color);
      display.fillCircle(ex[0] + 1, ey + 8, 2, C_WATER);  // 泪滴(在眼区内,擦除时会一起擦掉)
      break;
    case F_THINK:
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey, 6, 3, color);
      break;
    case F_SURPRISED:
      for (int i = 0; i < 2; i++) {
        display.drawCircle(ex[i] + 3, ey + 2, 5, color);
        display.fillCircle(ex[i] + 3, ey + 2, 2, color);
      }
      break;
    case F_SHY:  // > <
      display.drawLine(ex[0], ey - 2, ex[0] + 5, ey + 2, color);
      display.drawLine(ex[0] + 5, ey + 2, ex[0], ey + 6, color);
      display.drawLine(ex[1] + 5, ey - 2, ex[1], ey + 2, color);
      display.drawLine(ex[1], ey + 2, ex[1] + 5, ey + 6, color);
      break;
    case F_CONFUSED:  // 一只睁一只眯
      display.fillRect(ex[0], ey - 3, 6, 10, color);
      display.fillRect(ex[1], ey + 2, 6, 3, color);
      break;
    case F_SLEEPY:  // 半眯
      for (int i = 0; i < 2; i++) {
        display.drawFastHLine(ex[i] - 1, ey + 1, 8, color);
        display.fillRect(ex[i], ey + 2, 6, 4, color);
      }
      break;
    case F_SLEEP:
    case F_YAWN:  // 闭眼 ︶
      for (int i = 0; i < 2; i++) {
        display.drawLine(ex[i] - 1, ey + 2, ex[i] + 2, ey + 5, color);
        display.drawLine(ex[i] + 2, ey + 5, ex[i] + 5, ey + 2, color);
      }
      break;
    case F_DIZZY:  // 蚊香眼
      for (int i = 0; i < 2; i++) {
        display.drawCircle(ex[i] + 3, ey + 2, 5, color);
        display.drawCircle(ex[i] + 3, ey + 2, 2, color);
      }
      break;
    default:  // 睁眼(F_NORMAL / F_LISTEN)
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey - 3, 6, 10, color);
      break;
  }
}

void drawMouth(int f) {
  const int mx = CX, my = CY + 20;
  switch (f) {
    case F_HAPPY:
      display.drawLine(mx - 7, my - 2, mx, my + 3, TFT_BLACK);
      display.drawLine(mx, my + 3, mx + 7, my - 2, TFT_BLACK);
      break;
    case F_EXCITED:  // 张嘴大笑:下半圆 + 小舌头
      display.fillCircle(mx, my, 6, TFT_BLACK);
      display.fillRect(mx - 6, my - 6, 13, 6, C_BODY);
      display.fillCircle(mx, my + 3, 2, C_BLUSH);
      break;
    case F_SAD:
      display.drawLine(mx - 6, my + 2, mx, my - 3, TFT_BLACK);
      display.drawLine(mx, my - 3, mx + 6, my + 2, TFT_BLACK);
      break;
    case F_LISTEN:
      display.fillCircle(mx, my, 4, TFT_BLACK);
      break;
    case F_THINK:
      display.drawLine(mx - 6, my, mx + 6, my, TFT_BLACK);
      break;
    case F_SURPRISED:
      display.drawCircle(mx, my, 4, TFT_BLACK);
      display.drawCircle(mx, my, 3, TFT_BLACK);
      break;
    case F_SHY:
    case F_DIZZY:  // 波浪嘴
      display.drawLine(mx - 6, my, mx - 3, my - 2, TFT_BLACK);
      display.drawLine(mx - 3, my - 2, mx, my, TFT_BLACK);
      display.drawLine(mx, my, mx + 3, my - 2, TFT_BLACK);
      display.drawLine(mx + 3, my - 2, mx + 6, my, TFT_BLACK);
      break;
    case F_CONFUSED:
      display.drawLine(mx - 5, my + 1, mx + 5, my - 2, TFT_BLACK);
      break;
    case F_SLEEPY:
      display.drawFastHLine(mx - 3, my, 7, TFT_BLACK);
      break;
    case F_SLEEP:
      display.fillCircle(mx, my, 2, TFT_BLACK);
      break;
    case F_YAWN:
      display.fillCircle(mx, my + 1, 6, TFT_BLACK);
      break;
    default:
      display.fillCircle(mx - 1, my, 1, TFT_BLACK);
      display.fillCircle(mx + 3, my, 1, TFT_BLACK);
      break;
  }
}

// 只重画眼区(眨眼/张望/思考转眼)
void drawEyesOnly(int f, int look) {
  display.fillRect(CX - 26, CY - 17, 52, 17, C_BODY);
  drawEyes(look, f, TFT_BLACK);
}

// 重画五官(眼 + 嘴 + 腮红),不动轮廓
void drawFeatures(int f, int look = 0) {
  display.fillRect(CX - 26, CY - 17, 52, 17, C_BODY);  // 眼区
  display.fillRect(CX - 12, CY + 12, 25, 18, C_BODY);  // 嘴区
  display.fillCircle(CX - 27, CY + 8, 9, C_BODY);      // 腮红区
  display.fillCircle(CX + 27, CY + 8, 9, C_BODY);
  const int br = (f == F_SHY) ? 9 : 6;                  // 害羞:腮红变大
  display.fillCircle(CX - 27, CY + 8, br, C_BLUSH);
  display.fillCircle(CX + 27, CY + 8, br, C_BLUSH);
  drawEyes(look, f, TFT_BLACK);
  drawMouth(f);
}

// 整画:清屏 + 耳朵 + 脸 + 五官(只在状态切换时调用)
void drawPet(int f) {
  display.fillScreen(TFT_BLACK);
  display.fillTriangle(CX - 34, CY - 26, CX - 8, CY - 38, CX - 26, CY - 52, C_BODY);
  display.fillTriangle(CX + 8, CY - 38, CX + 34, CY - 26, CX + 26, CY - 52, C_BODY);
  display.drawLine(CX - 34, CY - 26, CX - 8, CY - 38, C_EDGE);
  display.drawLine(CX - 8, CY - 38, CX - 26, CY - 52, C_EDGE);
  display.drawLine(CX + 8, CY - 38, CX + 34, CY - 26, C_EDGE);
  display.drawLine(CX + 34, CY - 26, CX + 26, CY - 52, C_EDGE);
  display.fillCircle(CX, CY, R, C_BODY);
  display.drawCircle(CX, CY, R, C_EDGE);
  drawFeatures(f, 0);
}

// ---- 装饰层 ----
void clearDeco() {
  display.fillRect(DECO_LX, DECO_Y, DECO_W, DECO_H, TFT_BLACK);
  display.fillRect(DECO_RX, DECO_Y, DECO_W, DECO_H, TFT_BLACK);
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
        drawSparkle(DECO_RX + 12, DECO_Y + 14, 5, C_GOLD);
        drawSparkle(DECO_LX + 26, DECO_Y + 36, 4, C_GOLD);
      } else {
        drawSparkle(DECO_RX + 24, DECO_Y + 36, 4, C_GOLD);
        drawSparkle(DECO_LX + 14, DECO_Y + 14, 5, C_GOLD);
      }
      break;
    case F_SURPRISED:
      drawGlyph("!", DECO_RX + 12, DECO_Y + 8, 3, TFT_YELLOW);
      break;
    case F_CONFUSED:
      drawGlyph("?", DECO_RX + 12, DECO_Y + 8, 3, C_WATER);
      break;
    default:
      break;
  }
}

void drawSoundBars(int phase) {  // 聆听:两侧声波条轮流起伏
  clearDeco();
  static const int H[3][3] = {{8, 16, 24}, {16, 24, 8}, {24, 8, 16}};
  for (int k = 0; k < 3; k++) {
    const int h = H[phase % 3][k];
    const int y = DECO_Y + 28 - h / 2;
    display.fillRect(DECO_RX + 4 + 10 * k, y, 5, h, C_WATER);
    display.fillRect(DECO_LX + 26 - 10 * k, y, 5, h, C_WATER);
  }
}

void drawThinkDots(int count) {  // 思考:右侧 1~3 个点
  display.fillRect(DECO_RX, DECO_Y + 34, DECO_W, 12, TFT_BLACK);
  for (int k = 0; k < count; k++) display.fillCircle(DECO_RX + 8 + 10 * k, DECO_Y + 40, 3, TFT_WHITE);
}

void drawZzz(int phase) {  // 睡觉:右侧 z 依次变大
  clearDeco();
  const int n = phase % 4;
  if (n >= 1) drawGlyph("z", DECO_RX + 4, DECO_Y + 38, 1, TFT_LIGHTGREY);
  if (n >= 2) drawGlyph("z", DECO_RX + 12, DECO_Y + 22, 2, TFT_LIGHTGREY);
  if (n >= 3) drawGlyph("Z", DECO_RX + 22, DECO_Y + 2, 3, TFT_LIGHTGREY);
}

void drawBubbleHead() {  // 气泡尾巴指向宠物
  display.fillTriangle(150, 104, 172, 104, 160, 116, C_BUBBLE);
}

void drawBubbleText(const String& t1, uint16_t c1, const String& t2, uint16_t c2) {
  display.fillRoundRect(14, 6, 292, 98, 10, C_BUBBLE);
  display.drawRoundRect(14, 6, 292, 98, 10, TFT_BLACK);
  drawBubbleHead();
  const int y = drawTextCJK(t1, 26, 14, 290, c1);
  if (t2.length()) {
    if (y < 56) {
      display.drawFastHLine(26, 52, 268, 0xBDF7);
      drawTextCJK(t2, 26, 58, 290, c2);
    } else {
      drawTextCJK(t2, 26, y + 2, 290, c2);
    }
  }
}

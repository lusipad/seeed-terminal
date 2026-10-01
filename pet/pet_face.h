// ---- 宠物外观:几何像素风 + 表情 ----
// 依赖宿主先声明 Seeed_GFX display 并包含 cjk.h
#pragma once

enum Face { F_NORMAL, F_BLINK, F_HAPPY, F_SAD, F_LISTEN, F_THINK };

const int CX = 160, CY = 152, R = 40;          // 脸中心与半径
const uint16_t C_BODY = 0xFDEF;                // 暖灰白
const uint16_t C_EDGE = 0x8410;                // 描边
const uint16_t C_BLUSH = 0xFB60;               // 腮红
const uint16_t C_BUBBLE = 0xFFFF;

void drawEyes(int dx, int f, uint16_t color) {
  const int ex[2] = {CX + dx - 19, CX + dx + 13};
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
    case F_SAD:
      for (int i = 0; i < 2; i++) {
        display.drawLine(ex[i] - 1, ey - 2, ex[i] - 1, ey + 5, color);
        display.drawPixel(ex[i] - 1, ey + 8, 0x5DFF);  // 泪滴
      }
      break;
    case F_THINK:
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey, 6, 3, color);
      break;
    default:  // 睁眼
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey - 3, 6, 10, color);
      break;
  }
}

void drawPet(int dx, int f) {
  display.fillScreen(TFT_BLACK);

  // 耳朵
  display.fillTriangle(CX + dx - 34, CY - 26, CX + dx - 8, CY - 38, CX + dx - 26, CY - 52, C_BODY);
  display.fillTriangle(CX + dx + 8, CY - 38, CX + dx + 34, CY - 26, CX + dx + 26, CY - 52, C_BODY);
  display.drawLine(CX + dx - 34, CY - 26, CX + dx - 8, CY - 38, C_EDGE);
  display.drawLine(CX + dx - 8, CY - 38, CX + dx - 26, CY - 52, C_EDGE);
  display.drawLine(CX + dx + 8, CY - 38, CX + dx + 34, CY - 26, C_EDGE);
  display.drawLine(CX + dx + 34, CY - 26, CX + dx + 26, CY - 52, C_EDGE);

  // 脸
  display.fillCircle(CX + dx, CY, R, C_BODY);
  display.drawCircle(CX + dx, CY, R, C_EDGE);

  // 腮红
  display.fillCircle(CX + dx - 27, CY + 8, 6, C_BLUSH);
  display.fillCircle(CX + dx + 27, CY + 8, 6, C_BLUSH);

  // 眼睛
  drawEyes(dx, f, TFT_BLACK);

  // 嘴
  const int mx = CX + dx;
  switch (f) {
    case F_HAPPY:
      display.drawLine(mx - 7, CY + 18, mx, CY + 23, TFT_BLACK);
      display.drawLine(mx, CY + 23, mx + 7, CY + 18, TFT_BLACK);
      break;
    case F_SAD:
      display.drawLine(mx - 6, CY + 22, mx, CY + 17, TFT_BLACK);
      display.drawLine(mx, CY + 17, mx + 6, CY + 22, TFT_BLACK);
      break;
    case F_LISTEN:
      display.fillCircle(mx, CY + 20, 4, TFT_BLACK);
      break;
    case F_THINK:
      display.drawLine(mx - 6, CY + 20, mx + 6, CY + 20, TFT_BLACK);
      break;
    default:
      display.fillCircle(mx - 1, CY + 20, 1, TFT_BLACK);
      display.fillCircle(mx + 3, CY + 20, 1, TFT_BLACK);
      break;
  }
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

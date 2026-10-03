// 宿主模拟器的 Seeed_GFX 替身:同名 API,画进 320x240 RGB565 帧缓冲,
// sim::dumpFrame() 可导出 PPM。原语行为对齐 Seeed_GFX2(含 drawChar 的 bg==color 透明语义)。
#pragma once
#include <cmath>

#include "Arduino.h"

// 真机字库由构建脚本从本机 Seeed_GFX2 库拷到 sim/generated/(gitignore);
// 拷不到时生成占位宏,ASCII 以方框呈现
#include "generated/Font_GLCD.h"

enum class Seeed_Product { Wio_Terminal };

#define TFT_BLACK 0x0000
#define TFT_NAVY 0x000F
#define TFT_DARKGREEN 0x03E0
#define TFT_DARKCYAN 0x03EF
#define TFT_MAROON 0x7800
#define TFT_PURPLE 0x780F
#define TFT_OLIVE 0x7BE0
#define TFT_LIGHTGREY 0xD69A
#define TFT_DARKGREY 0x7BEF
#define TFT_BLUE 0x001F
#define TFT_GREEN 0x07E0
#define TFT_CYAN 0x07FF
#define TFT_RED 0xF800
#define TFT_MAGENTA 0xF81F
#define TFT_YELLOW 0xFFE0
#define TFT_WHITE 0xFFFF
#define TFT_ORANGE 0xFDA0
#define TFT_GREENYELLOW 0xB7E0
#define TFT_PINK 0xFE19
#define TFT_BROWN 0x9A60
#define TFT_SKYBLUE 0x867D
#define TFT_VIOLET 0x915C

struct SimGfxResult {
  const char* message;
};

namespace sim {
extern uint16_t fb[240][320];  // fb[y][x],RGB565
}

class Seeed_GFX {
 public:
  explicit Seeed_GFX(Seeed_Product) {}
  bool begin() { return true; }
  SimGfxResult lastResult() const { return {"sim"}; }

  void fillScreen(uint16_t c) { fillRect(0, 0, 320, 240, c); }

  void drawPixel(int32_t x, int32_t y, uint32_t color) {
    if (x < 0 || y < 0 || x >= 320 || y >= 240) return;
    sim::fb[y][x] = (uint16_t)color;
  }

  uint16_t readPixel(int32_t x, int32_t y) {
    if (x < 0 || y < 0 || x >= 320 || y >= 240) return 0;
    return sim::fb[y][x];
  }

  void drawFastHLine(int32_t x, int32_t y, int32_t w, uint32_t c) {
    for (int32_t i = 0; i < w; i++) drawPixel(x + i, y, c);
  }
  void drawFastVLine(int32_t x, int32_t y, int32_t h, uint32_t c) {
    for (int32_t i = 0; i < h; i++) drawPixel(x, y + i, c);
  }

  void fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t c) {
    for (int32_t j = 0; j < h; j++) drawFastHLine(x, y + j, w, c);
  }
  void drawRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t c) {
    drawFastHLine(x, y, w, c);
    drawFastHLine(x, y + h - 1, w, c);
    drawFastVLine(x, y, h, c);
    drawFastVLine(x + w - 1, y, h, c);
  }

  void drawLine(int32_t x0, int32_t y0, int32_t x1, int32_t y1, uint32_t c) {
    int32_t dx = x1 > x0 ? x1 - x0 : x0 - x1, sx = x0 < x1 ? 1 : -1;
    int32_t dy = y1 > y0 ? y0 - y1 : y1 - y0, sy = y0 < y1 ? 1 : -1;
    int32_t err = dx + dy;
    while (true) {
      drawPixel(x0, y0, c);
      if (x0 == x1 && y0 == y1) break;
      const int32_t e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  void fillCircle(int32_t x0, int32_t y0, int32_t r, uint32_t c) {
    for (int32_t dy = -r; dy <= r; dy++) {
      const int32_t dx = (int32_t)(std::sqrt((double)(r * r - dy * dy)) + 0.5);
      drawFastHLine(x0 - dx, y0 + dy, 2 * dx + 1, c);
    }
  }
  void drawCircle(int32_t x0, int32_t y0, int32_t r, uint32_t c) {
    int32_t f = 1 - r, ddx = 1, ddy = -2 * r, x = 0, y = r;
    drawPixel4(x0, y0, x, y, c);
    while (x < y) {
      if (f >= 0) { y--; ddy += 2; f += ddy; }
      x++; ddx += 2; f += ddx;
      drawPixel4(x0, y0, x, y, c);
    }
  }

  // 标准三角扫描线(与 Adafruit/Seeed 同算法)
  void fillTriangle(int32_t x0, int32_t y0, int32_t x1, int32_t y1, int32_t x2, int32_t y2,
                    uint32_t c) {
    if (y0 > y1) { swap(y0, y1); swap(x0, x1); }
    if (y1 > y2) { swap(y2, y1); swap(x2, x1); }
    if (y0 > y1) { swap(y0, y1); swap(x0, x1); }
    if (y0 == y2) {
      int32_t a = x0, b = x0;
      if (x1 < a) a = x1;
      if (x1 > b) b = x1;
      if (x2 < a) a = x2;
      if (x2 > b) b = x2;
      drawFastHLine(a, y0, b - a + 1, c);
      return;
    }
    const int32_t last = (y1 - y0 == y2 - y1) ? y1 : y1 - 1;
    for (int32_t y = y0; y <= last; y++) {
      int32_t a = x0 + (x1 - x0) * (y - y0) / (y1 - y0);
      int32_t b = x0 + (x2 - x0) * (y - y0) / (y2 - y0);
      if (a > b) swap(a, b);
      drawFastHLine(a, y, b - a + 1, c);
    }
    for (int32_t y = last + 1; y <= y2; y++) {
      int32_t a = x1 + (x2 - x1) * (y - y1) / (y2 - y1);
      int32_t b = x0 + (x2 - x0) * (y - y0) / (y2 - y0);
      if (a > b) swap(a, b);
      drawFastHLine(a, y, b - a + 1, c);
    }
  }

  void fillRoundRect(int32_t x, int32_t y, int32_t w, int32_t h, int32_t r, uint32_t c) {
    if (r <= 0) { fillRect(x, y, w, h, c); return; }
    if (2 * r > w) r = w / 2;
    if (2 * r > h) r = h / 2;
    fillRect(x + r, y, w - 2 * r, h, c);
    fillRect(x, y + r, r, h - 2 * r, c);
    fillRect(x + w - r, y + r, r, h - 2 * r, c);
    for (int32_t dy = 1; dy <= r; dy++) {
      const int32_t dx = (int32_t)(std::sqrt((double)(r * r - dy * dy)) + 0.5);
      drawFastHLine(x + r - dx, y + r - dy, dx, c);
      drawFastHLine(x + w - r, y + r - dy, dx, c);
      drawFastHLine(x + r - dx, y + h - r + dy - 1, dx, c);
      drawFastHLine(x + w - r, y + h - r + dy - 1, dx, c);
    }
  }
  void drawRoundRect(int32_t x, int32_t y, int32_t w, int32_t h, int32_t r, uint32_t c) {
    if (r <= 0) { drawRect(x, y, w, h, c); return; }
    if (2 * r > w) r = w / 2;
    if (2 * r > h) r = h / 2;
    drawFastHLine(x + r, y, w - 2 * r, c);
    drawFastHLine(x + r, y + h - 1, w - 2 * r, c);
    drawFastVLine(x, y + r, h - 2 * r, c);
    drawFastVLine(x + w - 1, y + r, h - 2 * r, c);
    drawCircleHelper(x + r, y + r, r, 0x8, c);
    drawCircleHelper(x + w - r - 1, y + r, r, 0x4, c);
    drawCircleHelper(x + w - r - 1, y + h - r - 1, r, 0x2, c);
    drawCircleHelper(x + r, y + h - r - 1, r, 0x1, c);
  }

  // 与 Seeed_GFX2 一致:bg == color 时只画前景(透明),否则连背景一起画
  void drawChar(int32_t x, int32_t y, uint16_t c, uint32_t color, uint32_t bg, uint8_t size) {
    if (c > 255) return;
    const bool fillbg = (bg != color);
    for (uint8_t i = 0; i < 6; i++) {
      uint8_t line = (i == 5) ? 0 : pgm_read_byte(&glcd_font[0] + (c * 5) + i);
      for (uint8_t j = 0; j < 8; j++) {
        if (line & 0x1) {
          if (size == 1) drawPixel(x + i, y + j, color);
          else fillRect(x + i * size, y + j * size, size, size, color);
        } else if (fillbg) {
          if (size == 1) drawPixel(x + i, y + j, bg);
          else fillRect(x + i * size, y + j * size, size, size, bg);
        }
        line >>= 1;
      }
    }
  }

  void setTextSize(uint8_t s) { textSize = s ? s : 1; }
  void setTextColor(uint16_t c) { textColor = c; }
  void drawString(const char* s, int32_t x, int32_t y) {
    int32_t cx = x;
    while (*s) {
      drawChar(cx, y, (uint8_t)*s, textColor, textColor, textSize);  // bg==color → 透明
      cx += 6 * textSize;
      s++;
    }
  }

  void pushImage(int32_t x, int32_t y, int32_t w, int32_t h, const uint16_t* data) {
    for (int32_t j = 0; j < h; j++)
      for (int32_t i = 0; i < w; i++) drawPixel(x + i, y + j, data[j * w + i]);
  }

 private:
  static void swap(int32_t& a, int32_t& b) { const int32_t t = a; a = b; b = t; }
  void drawPixel4(int32_t cx, int32_t cy, int32_t x, int32_t y, uint32_t c) {
    drawPixel(cx + x, cy + y, c);
    drawPixel(cx - x, cy + y, c);
    drawPixel(cx + x, cy - y, c);
    drawPixel(cx - x, cy - y, c);
  }
  // 圆角区域填充:side=-1 只向左延伸(左角),+1 只向右延伸(右角)
  void fillCorner(int32_t cx, int32_t cy, int32_t r, uint32_t c, int32_t side) {
    for (int32_t dy = -r; dy <= r; dy++) {
      const int32_t dx = (int32_t)(std::sqrt((double)(r * r - dy * dy)) + 0.5);
      if (side < 0) drawFastHLine(cx - dx, cy + dy, dx, c);
      else drawFastHLine(cx, cy + dy, dx + 1, c);
    }
  }
  void drawCircleHelper(int32_t x0, int32_t y0, int32_t r, uint8_t corner, uint32_t c) {
    int32_t f = 1 - r, ddx = 1, ddy = -2 * r, x = 0, y = r;
    while (x < y) {
      if (f >= 0) { y--; ddy += 2; f += ddy; }
      x++; ddx += 2; f += ddx;
      if (corner & 0x8) { drawPixel(x0 - x, y0 - y, c); drawPixel(x0 - y, y0 - x, c); }
      if (corner & 0x4) { drawPixel(x0 + x, y0 - y, c); drawPixel(x0 + y, y0 - x, c); }
      if (corner & 0x2) { drawPixel(x0 + x, y0 + y, c); drawPixel(x0 + y, y0 + x, c); }
      if (corner & 0x1) { drawPixel(x0 - x, y0 + y, c); drawPixel(x0 - y, y0 + x, c); }
    }
  }
  uint8_t textSize = 1;
  uint16_t textColor = TFT_WHITE;
};

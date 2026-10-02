#include "WioKitCjk.h"
#include "WioKitFontHz16.h"

static Seeed_GFX* cjkDisp = nullptr;

void wioCjkBegin(Seeed_GFX& d) { cjkDisp = &d; }

// 二分查找 UTF-8(3 字节) -> GB2312(2 字节)
static bool utf8ToGb(const uint8_t* u, uint8_t gbOut[2]) {
  int lo = 0, hi = HZ16_INDEX_COUNT - 1;
  while (lo <= hi) {
    const int mid = (lo + hi) >> 1;
    const uint8_t* e = &HZ16_INDEX[mid * 5];
    const int cmp = memcmp(u, e, 3);
    if (cmp == 0) { gbOut[0] = e[3]; gbOut[1] = e[4]; return true; }
    if (cmp < 0) hi = mid - 1; else lo = mid + 1;
  }
  return false;
}

static void drawHZ16(const uint8_t* u, int x, int y, uint16_t color) {
  uint8_t gb[2];
  if (!utf8ToGb(u, gb)) {
    cjkDisp->drawRect(x, y, 15, 15, color);  // 缺字占位框
    return;
  }
  const int qu = gb[0] - 0xA0, wei = gb[1] - 0xA0;
  uint32_t idx;
  if (qu >= 1 && qu <= 3) idx = (uint32_t)(qu - 1) * 94 + (wei - 1);
  else if (qu >= 16 && qu <= 55) idx = 94 * 3 + (uint32_t)(qu - 16) * 94 + (wei - 1);
  else { cjkDisp->drawRect(x, y, 15, 15, color); return; }

  const uint8_t* g = &HZ16_FONT[idx * 32];
  for (int row = 0; row < 16; row++) {
    for (int col = 0; col < 16; col++) {
      if ((g[row * 2 + (col >> 3)] >> (7 - (col & 7))) & 1) {
        cjkDisp->drawPixel(x + col, y + row, color);
      }
    }
  }
}

// 中英混排绘制(ASCII 走内置 6x8 字库,CJK 16x16),自动折行;返回结束 y
int drawTextCJK(const String& s, int x, int y, int maxX, uint16_t color) {
  if (!cjkDisp) return y;
  int cx = x, cy = y;
  const uint8_t* p = (const uint8_t*)s.c_str();
  while (*p) {
    if (*p == '\n') { cx = x; cy += 18; p++; continue; }
    if (*p < 0x80) {
      if (cx + 6 > maxX) { cx = x; cy += 18; }
      cjkDisp->drawChar(cx, cy + 4, *p, color, TFT_BLACK, 1);
      cx += 6; p++;
    } else if (p[0] >= 0xE0 && p[1] != 0 && p[2] != 0) {
      if (cx + 16 > maxX) { cx = x; cy += 18; }
      drawHZ16(p, cx, cy, color);
      cx += 16; p += 3;
    } else if (p[0] >= 0xC0 && p[0] < 0xE0 && p[1] != 0) {
      cx += 8; p += 2;  // 2 字节 UTF-8(重音西文等)占位
    } else {
      p++;  // 畸形字节
    }
  }
  return cy + 18;
}

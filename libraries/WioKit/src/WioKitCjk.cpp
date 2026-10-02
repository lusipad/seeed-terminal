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

static void drawHZ16(const uint8_t* u, int x, int y, uint16_t color, uint16_t bg) {
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

  // 性能:16x16 字形拼进行缓冲(512B 栈数组),pushImage 按行批量推送。
  // 原 drawPixel 逐像素 = 每像素一次地址窗口 + 写(每字最多 256 次 SPI 事务);
  // 现在每行一次批量写,每字 16 次,实测 5-10 倍提速。背景像素填 bg。
  uint16_t line[256];
  const uint8_t* g = &HZ16_FONT[idx * 32];
  for (int row = 0; row < 16; row++) {
    uint16_t* out = &line[row * 16];
    const uint8_t hi = g[row * 2], lo = g[row * 2 + 1];
    for (int col = 0; col < 8; col++) {
      out[col] = ((hi << col) & 0x80) ? color : bg;
      out[col + 8] = ((lo << col) & 0x80) ? color : bg;
    }
  }
  cjkDisp->pushImage(x, y, 16, 16, line);
}

// 中英混排绘制(ASCII 走内置 6x8 字库,CJK 16x16),自动折行;返回结束 y
int drawTextCJK(const String& s, int x, int y, int maxX, uint16_t color, uint16_t bg) {
  if (!cjkDisp) return y;
  int cx = x, cy = y;
  const uint8_t* p = (const uint8_t*)s.c_str();
  while (*p) {
    if (*p == '\n') { cx = x; cy += 18; p++; continue; }
    if (*p < 0x80) {
      if (cx + 6 > maxX) { cx = x; cy += 18; }
      cjkDisp->drawChar(cx, cy + 4, *p, color, bg, 1);
      cx += 6; p++;
    } else if (p[0] >= 0xE0 && p[1] != 0 && p[2] != 0) {
      if (cx + 16 > maxX) { cx = x; cy += 18; }
      drawHZ16(p, cx, cy, color, bg);
      cx += 16; p += 3;
    } else if (p[0] >= 0xC0 && p[0] < 0xE0 && p[1] != 0) {
      cx += 8; p += 2;  // 2 字节 UTF-8(重音西文等)占位
    } else {
      p++;  // 畸形字节
    }
  }
  return cy + 18;
}

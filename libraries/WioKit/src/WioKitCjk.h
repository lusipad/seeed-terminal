// ---- L1 中文渲染:UTF-8 -> GB2312 -> HZK16 16x16 点阵,中英混排自动折行 ----
// display 显式注入(解耦点①):sketch 里
//   Seeed_GFX display(Seeed_Product::Wio_Terminal);
//   ... display.begin(); wioCjkBegin(display);   // setup() 注入一次
// 只想画中文就只 include 本模块(字库数据在 WioKitFontHz16.h,~150KB 进 Flash)
#pragma once
#include <Arduino.h>
#include <Seeed_GFX.h>

void wioCjkBegin(Seeed_GFX& d);

// 中英混排绘制(ASCII 走内置 6x8 字库,CJK 16x16),x..maxX 内自动折行;返回结束 y。
// bg 为字形/字符背景像素色(默认黑):CJK 字形按行批量 pushImage 推送时,
// 背景像素会以 bg 写屏(替代原先"背景不画"),画在气泡等浅色底上必须传真实底色。
int drawTextCJK(const String& s, int x, int y, int maxX, uint16_t color, uint16_t bg = TFT_BLACK);

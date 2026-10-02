// CjkHello —— WioKit 最小示例:屏幕画中文(检验库脱离应用可独立使用)
// 编译烧录:bash tools/flash_and_log.sh examples/CjkHello 30
// 只 include WioKitCjk 一个模块;其余模块不进固件。

#include <Arduino.h>
#include <Seeed_GFX.h>

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include <WioKitCjk.h>

void setup() {
  Serial.begin(115200);
  if (!display.begin()) {
    Serial.print("ERR display: ");
    Serial.println(display.lastResult().message);
    while (true) delay(1000);
  }
  wioCjkBegin(display);  // 注入 display,之后 drawTextCJK 全局可用

  display.fillScreen(TFT_BLACK);
  drawTextCJK("你好,Wio Terminal!", 40, 90, 320, TFT_WHITE);
  drawTextCJK("中英混排 + 折行:the quick brown fox jumps over", 20, 120, 320, TFT_GREEN);
  drawTextCJK("WioKit 库化中文渲染 OK", 40, 150, 320, TFT_YELLOW);
}

void loop() {
  delay(1000);
}

// HelloWio — Wio Terminal 全链路验证程序
// 板载蓝色 LED(LED_BUILTIN, GPIO13)按 1Hz 闪烁,串口同步输出心跳。

#include <Arduino.h>

const uint32_t BLINK_INTERVAL_MS = 500;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  Serial.begin(115200);
  // 上传后串口监视器可能晚几秒才打开,最多等 3 秒,避免卡死在无主机场景
  const uint32_t start = millis();
  while (!Serial && millis() - start < 3000) {
  }

  Serial.println();
  Serial.print("Wio Terminal online | build: ");
  Serial.print(__DATE__);
  Serial.print(" ");
  Serial.println(__TIME__);
}

void loop() {
  static uint32_t count = 0;

  digitalWrite(LED_BUILTIN, HIGH);
  delay(BLINK_INTERVAL_MS);
  digitalWrite(LED_BUILTIN, LOW);
  delay(BLINK_INTERVAL_MS);

  Serial.print("blink #");
  Serial.println(++count);
}

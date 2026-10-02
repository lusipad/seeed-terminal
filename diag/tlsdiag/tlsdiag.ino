// TLS 连接诊断 v3:测试各 AI 平台端点从板子侧的可达性,为语音链路选型
#include <Arduino.h>
#include <rpcWiFi.h>
#include <rpcWiFiClientSecure.h>

// WiFi 凭据由本目录 wifi_secrets.h 提供(拷 pet/wifi_secrets.h 过来即可,已被 gitignore);
// 没有时在下面两行手动填——不要把真实密钥提交进仓库
#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
#define WIFI_SSID "你的WiFi名"
#define WIFI_PASS "你的WiFi密码"
#warning "tlsdiag: 未找到 wifi_secrets.h,请拷贝或手填 WiFi 凭据"
#endif

const char* TARGETS[] = {
  "openapi.baidu.com",  // 百度令牌接口(语音识别取 token)
  "vop.baidu.com",      // 对照:已知可达
};
const int TARGET_COUNT = sizeof(TARGETS) / sizeof(TARGETS[0]);

void setup() {
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2500) {
  }
  Serial.println("=== TLS DIAG v3 ===");

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  const unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > 20000) {
      Serial.println("WIFI FAIL");
      while (true) delay(1000);
    }
    delay(300);
  }
  Serial.print("WIFI OK ");
  Serial.println(WiFi.localIP());

  for (int i = 0; i < TARGET_COUNT; i++) {
    Serial.print("TEST ");
    Serial.println(TARGETS[i]);
    IPAddress ip;
    if (WiFi.hostByName(TARGETS[i], ip) != 1) {
      Serial.println("  DNS FAIL");
      continue;
    }
    WiFiClientSecure client;
    const uint32_t t = millis();
    const bool ok = client.connect(TARGETS[i], 443, 12000);
    Serial.print("  -> ");
    Serial.print(ok ? "OK" : "FAIL");
    Serial.print(" (");
    Serial.print(millis() - t);
    Serial.println("ms)");
    client.stop();
    delay(300);
  }
  Serial.println("=== DIAG DONE ===");
}

void loop() {
  delay(1000);
}

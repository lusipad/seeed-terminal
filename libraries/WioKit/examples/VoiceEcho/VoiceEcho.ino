// VoiceEcho —— 录音 → 百度 ASR → DeepSeek → 上屏(验证 WioKit L1+L2 全链路)
// 首次使用:把 pet/wifi_secrets.h 拷到本目录(或照 wifi_secrets.h.example 新建),
//           然后 bash tools/flash_and_log.sh libraries/WioKit/examples/VoiceEcho 600
// 操作:按一下 B 说话,说完自动识别;转写与回答显示在屏幕,各阶段耗时打在串口。
// 没有密钥也能编译:开机提示缺少配置(库本身不含密钥,由应用注入)。

#include <Arduino.h>
#include <Seeed_GFX.h>

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include <WioKitCjk.h>

#if __has_include("wifi_secrets.h")
#define ECHO_HAS_WIFI 1
#include "wifi_secrets.h"
#else
#define ECHO_HAS_WIFI 0
#endif

#include <WioKitLogic.h>   // parseEmotionTag
#include <WioKitMic.h>     // 录音 + VAD + 裁剪
#include <WioKitNet.h>     // WiFi + HTTP
#include <WioKitTiming.h>  // 计时账本
#if ECHO_HAS_WIFI
#include <WioKitAsrBaidu.h>
#include <WioKitLlmDeepSeek.h>
#endif

const int PIN_KEY_B = WIO_KEY_B;

void show(const String& l1, uint16_t c1, const String& l2, uint16_t c2) {
  display.fillScreen(TFT_BLACK);
  drawTextCJK(l1, 14, 60, 308, c1);
  drawTextCJK(l2, 14, 130, 308, c2);
}

void printTiming() {
  Serial.print("T: net=");
  Serial.print(wioTiming().net);
  Serial.print(" upload=");
  Serial.print(wioTiming().upload);
  Serial.print(" asr=");
  Serial.print(wioTiming().asr);
  Serial.print(" llm_conn=");
  Serial.print(wioTiming().llmConn);
  Serial.print(" llm=");
  Serial.println(wioTiming().llm);
}

void setup() {
  pinMode(PIN_KEY_B, INPUT_PULLUP);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2500) {
  }
  if (!display.begin()) {
    Serial.print("ERR display: ");
    Serial.println(display.lastResult().message);
    while (true) delay(1000);
  }
  wioCjkBegin(display);
  if (!wioMicBegin()) {
    show("麦克风初始化失败", TFT_RED, "", TFT_BLACK);
    while (true) delay(1000);
  }
  wioMicConfig(400, 900, 8000);
#if ECHO_HAS_WIFI
  if (strlen(BAIDU_API_KEY) < 4 || strlen(WIFI_SSID) < 1) {
    show("wifi_secrets.h 还是空的", TFT_YELLOW, "填好 WiFi 与百度 Key 再烧录", 0x8410);
    while (true) delay(1000);
  }
  wioNetBegin(WIFI_SSID, WIFI_PASS);
  wioAsrBaiduBegin(BAIDU_API_KEY, BAIDU_SECRET_KEY);
  wioLlmDeepSeekBegin(DEEPSEEK_KEY, "你是语音助手,用简体中文简短回答。");
  Serial.println("HELLO VoiceEcho 1.0");
  const bool netOk = wioNetConnected();
  show("VoiceEcho", TFT_WHITE, netOk ? "网络就绪,按 B 说话" : "网络未就绪,按 B 时再试",
       netOk ? TFT_GREEN : TFT_RED);
#else
  Serial.println("HELLO VoiceEcho offline");
  show("缺少 wifi_secrets.h", TFT_YELLOW, "拷贝密钥文件到本目录后重新编译", 0x8410);
#endif
}

void loop() {
#if ECHO_HAS_WIFI
  static unsigned long lastMs = 0;
  if (digitalRead(PIN_KEY_B) != LOW) return;
  if (millis() - lastMs < 200) return;
  lastMs = millis();

  wioTimingReset();
  show("在听…说完我自己停", TFT_GREEN, "", TFT_BLACK);
  wioRecStart();

  uint32_t samples = 0, hint = 0;
  while (wioRecPoll(samples, hint) == 0) {
  }
  if (samples == 0) {
    show("没录到声音,再试一次", TFT_RED, "", TFT_BLACK);
    return;
  }

  show("识别中…", TFT_WHITE, "", TFT_BLACK);
  uint32_t lo = 0, hi = samples;
  wioRecTrim(lo, hi);
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  String transcript, note;
  if (!wioAsrBaidu(wioRecBuffer() + lo, n, transcript, note)) {
    show("识别失败:" + note, TFT_RED, "", TFT_BLACK);
    printTiming();
    return;
  }

  String raw, reply;
  if (strlen(DEEPSEEK_KEY) > 4 && wioLlmAsk(transcript, raw, note)) {
    size_t ts = 0;
    parseEmotionTag(raw.c_str(), raw.length(), &ts);  // 剥掉情绪标签再上屏
    reply = raw.substring(ts);
  }
  show("你:" + transcript, 0x8410, reply.length() ? reply : "(只识别,不回答)", TFT_GREEN);
  printTiming();
#endif
}

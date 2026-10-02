// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机会眨眼、张望、哼歌;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。
// 硬件能力(录音/渲染/网络/传感器)在 libraries/WioKit,这里只保留应用层:
// 状态机、表情人设(pet_face/pet_anim)、系统提示词、密钥。

#include <Arduino.h>
#include <Seeed_GFX.h>

#include <WioKitLogic.h>   // L0 纯逻辑(HTTP 判停/chunked/情绪标签/探测器)
#include <WioKitCjk.h>     // L1 中文渲染(字库在库里,~150KB Flash)
#include <WioKitMic.h>     // L1 麦克风 DMA 录音 + VAD
#include <WioKitSense.h>   // L1 光线 + IMU(判定逻辑在 WioKitLogic)
#include <WioKitNet.h>     // L1 WiFi + HTTP + base64
#include <WioKitTiming.h>  // 各阶段计时账本("T:" 行)

// ---- 密钥:应用层负责(解耦点③,库永不含密钥)。没有 wifi_secrets.h 也能编译出离线宠物 ----
#if __has_include("wifi_secrets.h")
#define PET_HAS_WIFI 1
#include "wifi_secrets.h"
#else
#define PET_HAS_WIFI 0
#endif

#if PET_HAS_WIFI
#include <WioKitAsrBaidu.h>    // L2 百度 ASR
#include <WioKitLlmDeepSeek.h> // L2 DeepSeek
#endif

#ifndef PET_TEST_OFFLINE
#define PET_TEST_OFFLINE 0   // 1 = 开机预连直接失败(测试离线开机)
#endif
#ifndef PET_TEST_BAD_TOKEN
#define PET_TEST_BAD_TOKEN 0 // 1 = 预连后把 token 改坏(测试失效自动重取)
#endif

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include "pet_face.h"
#include "pet_anim.h"

const int PIN_KEY_B = WIO_KEY_B;
const int PIN_KEY_C = WIO_KEY_C;
const int PIN_JOY_L = WIO_5S_LEFT;
const int PIN_JOY_R = WIO_5S_RIGHT;
// 全部 8 个按键输入(唤醒/提前结束显示时任意键都算)
const int ALL_KEYS[8] = {WIO_KEY_A, WIO_KEY_B, WIO_KEY_C, WIO_5S_UP,
                         WIO_5S_DOWN, WIO_5S_LEFT, WIO_5S_RIGHT, WIO_5S_PRESS};

void beep(int freq, int dur) {
  tone(WIO_BUZZER, freq, dur);
}

const uint32_t PET_TRAILING_MS = 900;  // 说完静音多久自动停(实测可调,与库内 VAD 配套)

// ============================================================
// 语音链路编排(应用层):裁剪 → 识别 → 回答 → 情绪标签
// ============================================================

#if PET_HAS_WIFI

const char* const PET_SYSTEM_PROMPT =
    "你是电子桌宠\"小维\",性格活泼元气,说话简短、口语化、爱用感叹号。"
    "回答必须以情绪标签开头,格式如 [开心],情绪只能从 开心/兴奋/惊讶/害羞/疑惑/难过 里选一个;"
    "标签后直接是回答正文,用简体中文,45字以内,不要任何其他前缀或解释。";

// 每轮结束打印 "T:" 行(格式不变,性能基线可对比)
void petPrintTiming(uint32_t processMs) {
  Serial.print("T: trail=");
  Serial.print(PET_TRAILING_MS);
  Serial.print(" net=");
  Serial.print(wioTiming().net);
  Serial.print(" upload=");
  Serial.print(wioTiming().upload);
  Serial.print(" asr=");
  Serial.print(wioTiming().asr);
  Serial.print(" llm_conn=");
  Serial.print(wioTiming().llmConn);
  Serial.print(" llm=");
  Serial.print(wioTiming().llm);
  Serial.print(" total=");
  Serial.println(PET_TRAILING_MS + processMs);
}

// 开机预连:WiFi(只试 1 次,≤15s)+ 百度 token。失败不阻止开机:离线照常做宠物,按 B 时再连
void petNetWarmup() {
  const uint32_t t0 = millis();
#if PET_TEST_OFFLINE
  const bool ok = false;  // 测试:模拟开机时无网
#else
  const bool ok = wioNetConnected(1) && wioAsrBaiduWarmup();
#endif
  Serial.print("V: warmup ");
  Serial.print(ok ? "ok" : "failed");
  Serial.print(" ms=");
  Serial.println(millis() - t0);
}

// 识别 + 回答(阻塞,数秒):成功 true;transcript/reply/note 填充。
// 连网/令牌/失效重取在 wioAsrBaidu 内部;情绪标签解析在这里做(标签属于小维人设,不在库)
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, int& emotion, String& note) {
  transcript = "";
  reply = "";
  note = "";
  emotion = EMO_HAPPY;
  wioTimingReset();

  // 静音裁剪:去掉首尾低于阈值的段,只留有效语音(+100ms 余量)
  uint32_t lo = 0, hi = samples;
  wioRecTrim(lo, hi);
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  if (!wioAsrBaidu(wioRecBuffer() + lo, n, transcript, note)) return false;
  if (strlen(DEEPSEEK_KEY) < 5) {
    return true;  // 只识别,无回答
  }
  String raw;
  if (!wioLlmAsk(transcript, raw, note)) return false;
  size_t textStart = 0;
  emotion = parseEmotionTag(raw.c_str(), raw.length(), &textStart);
  reply = raw.substring(textStart);  // 标签不上屏
  if (!reply.length()) {  // 空回复,或只给了标签没有正文
    note = "llm empty reply";
    return false;
  }
  return true;
}

#else  // !PET_HAS_WIFI:离线宠物,宠物行为照常,B 键按下后走"连不上网"提示

void petPrintTiming(uint32_t processMs) { (void)processMs; }
void petNetWarmup() {}
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, int& emotion, String& note) {
  (void)samples;
  transcript = "";
  reply = "";
  emotion = EMO_HAPPY;
  note = "wifi failed";
  return false;
}

#endif  // PET_HAS_WIFI

// ============================================================
// 状态机
// ============================================================

enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW, ST_SLEEP };
PetState state = ST_IDLE;
unsigned long stateStart = 0;
unsigned long showUntil = 0;
uint32_t recSamples = 0;
unsigned long lastInteract = 0;              // 最近一次有人互动(按键/摸头/拿起)
const unsigned long PET_DROWSY_MS = 180000;  // 3 分钟没人理 → 犯困
const unsigned long PET_SLEEP_MS = 300000;   // 5 分钟 → 睡觉
const int PET_DIM_LEVEL = 40;                // 睡觉时背光 PWM(0-255)

// 背光:LCD_BACKLIGHT 实测不支持 PWM,analogWrite 会直接全灭且无法调暗 —— 睡觉时保持亮度,只显示睡觉画面
void setBacklight(bool dim) {
  (void)dim;
  (void)PET_DIM_LEVEL;
}

// Emotion(WioKitLogic.h)→ 表情;顺序必须与 enum Emotion 一致:开心 兴奋 惊讶 害羞 疑惑 难过
const int EMO_FACE[6] = {F_HAPPY, F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SAD};

// 把技术性 note 翻成小维口吻(原 note 仍显示在第二行,方便排查)
String friendlyNote(const String& note) {
  if (note.startsWith("wifi")) return "我连不上 WiFi 啦…";
  if (note.startsWith("asr rejected")) return "没听清,再说一遍嘛~";
  if (note.startsWith("asr")) return "耳朵(语音识别)出故障了";
  if (note.startsWith("baidu")) return "语音服务登录失败了";
  if (note.startsWith("llm")) return "脑袋(DeepSeek)卡住了";
  return "出了点小状况";
}

void drawIdleHint() {
  drawTextCJK("按一下 B 说话,说完我自己停", 62, 220, 320, TFT_DARKGREY);
}

void enterIdle() {
  state = ST_IDLE;
  stateStart = millis();
  drawPet(F_NORMAL);
  drawIdleHint();
  petAnimSet(A_IDLE);
}

// 显示一段表情 + 气泡,durMs 后自动回待机(期间按键也可提前返回)
void enterShow(int face, const String& t1, uint16_t c1, const String& t2, uint32_t durMs) {
  state = ST_SHOW;
  stateStart = millis();
  showUntil = millis() + durMs;
  drawPet(face);
  if (t1.length()) drawBubbleText(t1, c1, t2, TFT_BLACK);
  petAnimSet(A_EMOTE, face);
}

void enterSleep() {
  Serial.println("P: sleep");
  state = ST_SLEEP;
  stateStart = millis();
  drawPet(F_SLEEP);
  petAnimSet(A_SLEEP);
  setBacklight(true);
}

void wakeUp() {
  Serial.println("P: wake");
  setBacklight(false);
  lastInteract = millis();
  state = ST_IDLE;
  stateStart = millis();
  drawPet(F_SLEEP);
  drawIdleHint();
  petAnimSet(A_WAKE);  // 睁眼动画结束后自动转 A_IDLE
}

void startDizzy() {
  lastInteract = millis();
  state = ST_SHOW;
  stateStart = millis();
  showUntil = millis() + 3000;
  drawPet(F_DIZZY);
  petAnimSet(A_DIZZY);
}

// 传感器事件:只在 IDLE / SHOW / SLEEP 处理;录音、思考时不采样
void handleSense() {
  if (state != ST_IDLE && state != ST_SHOW && state != ST_SLEEP) return;
  const int ev = wioSensePoll();
  if (ev == SE_NONE) return;
  Serial.print("S: event=");
  Serial.println(ev);
  if (state == ST_SLEEP) {
    if (ev == SE_LIGHT || ev == SE_PICKUP || ev == SE_SHAKE) wakeUp();
    return;
  }
  if (ev == SE_DARK) {
    enterSleep();
    return;
  }
  if (ev == SE_SHAKE) {
    beep(523, 60);
    startDizzy();
    return;
  }
  if (ev == SE_PICKUP) {
    lastInteract = millis();
    if (petAnimCurrent() == A_DROWSY) petAnimSet(A_IDLE);
  }
}

void setup() {
  for (int i = 0; i < 8; i++) pinMode(ALL_KEYS[i], INPUT_PULLUP);

  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2500) {
  }

  if (!display.begin()) {
    Serial.print("ERR display: ");
    Serial.println(display.lastResult().message);
    while (true) delay(1000);
  }
  wioCjkBegin(display);  // 注入 display(解耦点①),之后 drawTextCJK 全局可用
  randomSeed(analogRead(A0) ^ micros());
  wioMicBegin();
  wioMicConfig(400, PET_TRAILING_MS, 8000);  // 静音阈值 / 截断静音时长 / 没说话超时
  wioSenseBegin();
#if PET_HAS_WIFI
  wioNetSetYield(petAnimTick);  // 解耦点②:网络等待期间动画照常
  wioNetBegin(WIFI_SSID, WIFI_PASS);  // 解耦点③:密钥由应用注入,库永不含密钥
  wioAsrBaiduBegin(BAIDU_API_KEY, BAIDU_SECRET_KEY);
  wioLlmDeepSeekBegin(DEEPSEEK_KEY, PET_SYSTEM_PROMPT);
#endif
  Serial.println("HELLO pet 1.2");
  drawPet(F_SLEEP);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
  petAnimSet(A_WAKE);
  petNetWarmup();
#if PET_TEST_BAD_TOKEN
  wioAsrBaiduDebugToken("invalid_token_for_selftest_0000");
#endif
  lastInteract = millis();
  enterIdle();
}

bool pressed(int pin) {
  static unsigned long lastMs = 0;
  if (digitalRead(pin) != LOW) return false;
  if (millis() - lastMs < 200) return false;
  lastMs = millis();
  return true;
}

bool anyKeyDown() {
  for (int i = 0; i < 8; i++) {
    if (digitalRead(ALL_KEYS[i]) == LOW) return true;
  }
  return false;
}

void loop() {
  petAnimTick();
  handleSense();
  switch (state) {
    case ST_IDLE: {
      const unsigned long idleFor = millis() - lastInteract;
      if (idleFor > PET_SLEEP_MS) {
        enterSleep();
        break;
      }
      if (idleFor > PET_DROWSY_MS && petAnimCurrent() == A_IDLE) petAnimSet(A_DROWSY);
      if (pressed(PIN_KEY_C)) {  // C 键:叫醒犯困的小维
        lastInteract = millis();
        petAnimSet(A_IDLE);
        break;
      }
      if (pressed(PIN_JOY_L) || pressed(PIN_JOY_R)) {  // 摸头
        lastInteract = millis();
        beep(1568, 80);
        enterShow(F_HAPPY, "", TFT_BLACK, "", 1200);
        break;
      }
      if (pressed(PIN_KEY_B)) {
        lastInteract = millis();
        wioRecStart();
        state = ST_RECORD;
        stateStart = millis();
        drawPet(F_LISTEN);
        drawBubbleText("在听…说完我会自己停", TFT_BLACK, "", TFT_BLACK);
        petAnimSet(A_LISTEN);
        beep(988, 60);
      }
      break;
    }

    case ST_RECORD: {
      uint32_t samples = 0, hint = 0;
      const int st = wioRecPoll(samples, hint);
      if (st == 2) {  // 超时没说话
        beep(196, 250);
        enterShow(F_SAD, "你还没说话呢~", TFT_BLACK, "按一下 B 再开口就好", 15000);
        break;
      }
      if (st == 1) {  // 录完
        recSamples = samples;
        beep(880, 50);
        state = ST_THINK;
        stateStart = millis();
        drawPet(F_THINK);
        drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
        petAnimSet(A_THINK);
      }
      break;
    }

    case ST_THINK: {
      // 识别 + 回答(阻塞数秒;等待期间 petAnimTick 由网络循环驱动)
      String t, r, note;
      int emo = EMO_HAPPY;
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, t, r, emo, note);
      petPrintTiming(millis() - tProc);
      if (ok) {
        beep(1319, 90);
        const int face = (emo >= 0 && emo < 6) ? EMO_FACE[emo] : F_HAPPY;
        enterShow(face, "你:" + t, 0x8410,
                  r.length() ? "小维:" + r : String("(还没配置 DeepSeek Key,我不会说话呀)"), 15000);
      } else {
        beep(196, 250);
        enterShow(F_SAD, "呜…" + friendlyNote(note), 0x8410, note, 15000);
      }
      break;
    }

    case ST_SHOW: {
      const bool keyAfterGrace = millis() - stateStart > 400 && anyKeyDown();
      if (millis() > showUntil || keyAfterGrace) {
        while (anyKeyDown()) petAnimTick();  // 等松手,避免同一次按键在待机里又触发
        enterIdle();
      }
      break;
    }

    case ST_SLEEP: {
      if (anyKeyDown()) {
        wakeUp();
        while (anyKeyDown()) petAnimTick();  // 等松手,避免叫醒的那一下又触发录音
      }
      break;
    }
  }
}

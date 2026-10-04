// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机会眨眼、张望、哼歌;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。
// 硬件能力(录音/渲染/网络/传感器)在 libraries/WioKit,这里只保留应用层:
// 状态机、表情人设(pet_face/pet_anim)、系统提示词、密钥。

#include <Arduino.h>
#include <unistd.h>
#include <Seeed_GFX.h>

enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW, ST_SLEEP, ST_CONFIG };
PetState state = ST_IDLE;

#include <WioKitLogic.h>   // L0 纯逻辑(HTTP 判停/chunked/情绪标签/探测器)
#include <WioKitCjk.h>     // L1 中文渲染(字库在库里,~150KB Flash)
#include <WioKitMic.h>     // L1 麦克风 DMA 录音 + VAD
#include <WioKitSense.h>   // L1 光线 + IMU(判定逻辑在 WioKitLogic)
#include <WioKitNet.h>     // L1 WiFi + HTTP + base64
#include <WioKitTiming.h>  // 各阶段计时账本("T:" 行)

#include <WioKitConfig.h>      // L1 配置持久化 + SoftAP 网页配网
#include <WioKitAsrBaidu.h>    // L2 百度 ASR
#include <WioKitLlmDeepSeek.h> // L2 DeepSeek

// ---- 默认密钥/回退:若本地有 wifi_secrets.h 且未指定发布模式则用作开发调试缺省值 ----
#if __has_include("wifi_secrets.h") && !defined(PET_RELEASE_BUILD)
#define HAS_COMPILED_SECRETS 1
#include "wifi_secrets.h"
#else
#define HAS_COMPILED_SECRETS 0
#endif

#ifndef PET_TEST_OFFLINE
#define PET_TEST_OFFLINE 0   // 1 = 开机预连直接失败(测试离线开机)
#endif
#ifndef PET_TEST_BAD_TOKEN
#define PET_TEST_BAD_TOKEN 0 // 1 = 预连后把 token 改坏(测试失效自动重取)
#endif

Seeed_GFX display(Seeed_Product::Wio_Terminal);

WioConfig activeConfig;
bool hasActiveConfig = false;
static String petSysPrompt;

#include "pet_pages.h"
#include "pet_face.h"
#include "pet_anim.h"

// 桌面多功能看板状态定义
int curPage = PAGE_PET;
int lastPageBeforeVoice = PAGE_PET;
uint32_t netEpochBase = 0;
uint32_t netEpochMillis = 0;
bool hasSyncedTime = false;
uint32_t nextTimeSyncMs = 0;

uint32_t pomoRemainingSec = POMO_DURATION_SEC;
bool pomoRunning = false;
uint32_t pomoLastTickMs = 0;
int pomoCompletedTotal = 0;
bool pomoJustFinished = false;

void startPomodoro() {
  if (!pomoRunning) {
    pomoRunning = true;
    pomoLastTickMs = millis();
  }
}

void pausePomodoro() {
  pomoRunning = false;
}

void resetPomodoro() {
  pomoRunning = false;
  pomoRemainingSec = POMO_DURATION_SEC;
  pomoJustFinished = false;
}

void tickPomodoroLogic() {
  if (!pomoRunning) return;
  const unsigned long now = millis();
  if (now - pomoLastTickMs >= 1000) {
    const uint32_t secPassed = (now - pomoLastTickMs) / 1000;
    pomoLastTickMs += secPassed * 1000;
    if (pomoRemainingSec > secPassed) {
      pomoRemainingSec -= secPassed;
    } else {
      pomoRemainingSec = 0;
      pomoRunning = false;
      pomoCompletedTotal++;
      pomoJustFinished = true;
    }
  }
}

const int PIN_KEY_A = WIO_KEY_A;
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

const uint32_t PET_TRAILING_MS = 1200;  // 说完静音多久自动停(放宽到1.2s,避免换气断句)

// ============================================================
// 语音链路编排(应用层):裁剪 → 识别 → 回答 → 情绪标签
// ============================================================

const char* getPetSystemPrompt() {
  petSysPrompt = "你是电子桌宠\"小维\",性格活泼元气,说话简短、口语化、爱用感叹号。"
                 "回答必须以情绪标签开头,格式如 [开心],情绪只能从 开心/兴奋/惊讶/害羞/疑惑/难过 里选一个;"
                 "标签后直接是回答正文,用简体中文,45字以内,不要使用Emoji表情,不要使用Markdown符号(如*、#),直接说纯文本。";
  if (hasActiveConfig && strlen(activeConfig.city) > 0) {
    petSysPrompt += "主人常驻城市是: ";
    petSysPrompt += activeConfig.city;
    petSysPrompt += "。被问及天气时据此作答。";
  }
  return petSysPrompt.c_str();
}

void handleTestCommands();
void petYieldLoop() {
  handleTestCommands();
  petAnimTick();
}

void applyActiveConfig() {
  if (hasActiveConfig && strlen(activeConfig.ssid) > 0) {
    wioNetSetYield(petYieldLoop);
    wioNetBegin(activeConfig.ssid, activeConfig.pass);
    wioAsrBaiduBegin(activeConfig.baiduApiKey, activeConfig.baiduSecret);
    wioLlmDeepSeekBegin(activeConfig.deepseekKey, getPetSystemPrompt());
  }
}

// ---- 多轮对话上下文 (保存最近 2 轮对答 = 4 条消息: user, assistant, user, assistant) ----
const size_t MAX_HISTORY_MSGS = 4;
static WioLlmMsg chatHistory[MAX_HISTORY_MSGS];
static size_t chatHistoryCount = 0;
static uint32_t lastChatTime = 0;
const uint32_t CHAT_CONTEXT_EXPIRE_MS = 90000;  // 90秒不说话则上下文自动重置

void clearChatHistory() {
  chatHistoryCount = 0;
}

void addChatHistory(const String& userText, const String& assistantText) {
  if (chatHistoryCount + 2 <= MAX_HISTORY_MSGS) {
    chatHistory[chatHistoryCount++] = {"user", userText};
    chatHistory[chatHistoryCount++] = {"assistant", assistantText};
  } else {
    for (size_t i = 2; i < chatHistoryCount; i++) {
      chatHistory[i - 2] = chatHistory[i];
    }
    chatHistory[chatHistoryCount - 2] = {"user", userText};
    chatHistory[chatHistoryCount - 1] = {"assistant", assistantText};
  }
  lastChatTime = millis();
}

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
  if (!hasActiveConfig || strlen(activeConfig.ssid) == 0) {
    Serial.println("V: no wifi config, skipping warmup");
    return;
  }
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
bool petProcessVoice(uint32_t samples, bool bufferFull, String& transcript, String& reply, int& emotion, String& note) {
  transcript = "";
  reply = "";
  note = "";
  emotion = EMO_HAPPY;
  wioTimingReset();

  if (!hasActiveConfig || strlen(activeConfig.ssid) == 0) {
    note = "wifi not configured";
    return false;
  }

  // 静音裁剪:去掉首尾低于阈值的段,只留有效语音(+100ms 余量)
  uint32_t lo = 0, hi = samples;
  wioRecTrim(lo, hi);
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  if (!wioAsrBaidu(wioRecBuffer() + lo, n, transcript, note)) {
    if (bufferFull) {
      note = "asr buffer full";
    }
    return false;
  }
  if (!hasActiveConfig || strlen(activeConfig.deepseekKey) < 5) {
    return true;  // 只识别,无回答
  }

  // 90 秒无互动则清除过期历史
  if (chatHistoryCount > 0 && millis() - lastChatTime > CHAT_CONTEXT_EXPIRE_MS) {
    clearChatHistory();
    Serial.println("P: chat context expired");
  }

  String raw;
  if (!wioLlmAskWithHistory(chatHistory, chatHistoryCount, transcript, raw, note)) return false;
  size_t textStart = 0;
  emotion = parseEmotionTag(raw.c_str(), raw.length(), &textStart);
  reply = raw.substring(textStart);  // 标签不上屏
  if (!reply.length()) {  // 空回复,或只给了标签没有正文
    note = "llm empty reply";
    return false;
  }

  // 记录本轮对话进多轮上下文
  addChatHistory(transcript, reply);
  return true;
}

// ============================================================
// 状态机
// ============================================================

const char* petStateStr(PetState s) {
  switch (s) {
    case ST_IDLE: return "ST_IDLE";
    case ST_RECORD: return "ST_RECORD";
    case ST_THINK: return "ST_THINK";
    case ST_SHOW: return "ST_SHOW";
    case ST_SLEEP: return "ST_SLEEP";
    case ST_CONFIG: return "ST_CONFIG";
    default: return "UNKNOWN";
  }
}

void petSetState(PetState s) {
  if (state != s) {
    state = s;
    Serial.print("!STATE ");
    Serial.println(petStateStr(s));
  }
}
unsigned long stateStart = 0;
unsigned long showUntil = 0;
uint32_t recSamples = 0;
bool recBufferFull = false;
unsigned long lastInteract = 0;              // 最近一次有人互动(按键/摸头/拿起)
const unsigned long PET_DROWSY_MS = 180000;  // 3 分钟没人理 → 犯困
const unsigned long PET_SLEEP_MS = 300000;   // 5 分钟 → 睡觉
const int PET_DIM_LEVEL = 40;                // 睡觉时背光 PWM(0-255)

// 背光:LCD_BACKLIGHT 实测不支持 PWM,analogWrite 会直接全灭且无法调暗 —— 睡觉时保持亮度,只显示睡觉画面
void setBacklight(bool dim) {
  (void)dim;
  (void)PET_DIM_LEVEL;
}

void setBacklightPower(bool on) {
  pinMode(LCD_BACKLIGHT, OUTPUT);
  digitalWrite(LCD_BACKLIGHT, on ? HIGH : LOW);
}

// Emotion(WioKitLogic.h)→ 表情;顺序必须与 enum Emotion 一致:开心 兴奋 惊讶 害羞 疑惑 难过
const int EMO_FACE[6] = {F_HAPPY, F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SAD};

// 把技术性 note 翻成小维口吻(原 note 仍显示在第二行,方便排查)
String friendlyNote(const String& note) {
  if (note.startsWith("asr buffer full")) return "一句话太长啦~";
  if (note.startsWith("wifi")) return "我连不上 WiFi 啦…";
  if (note.startsWith("asr rejected")) return "没听清,再说一遍嘛~";
  if (note.startsWith("asr")) return "耳朵(语音识别)出故障了";
  if (note.startsWith("baidu")) return "语音服务登录失败了";
  if (note.startsWith("llm")) return "脑袋(DeepSeek)卡住了";
  return "出了点小状况";
}

void drawIdleHint() {
  drawTextCJK("按 B 说话 | 摇杆切页 | 压下互动", 34, 218, 320, TFT_LIGHTGREY, C_BOTTOM_BG);
}

void switchPage(int newPage) {
  if (newPage < 0) newPage = 2;
  if (newPage > 2) newPage = 0;
  curPage = newPage;
  lastPageBeforeVoice = curPage;
  lastInteract = millis();
  if (state == ST_IDLE) {
    if (curPage == PAGE_PET) {
      drawPet(F_NORMAL);
      drawIdleHint();
      petAnimSet(A_IDLE);
    } else if (curPage == PAGE_CLOCK) {
      drawClockPage(true);
    } else if (curPage == PAGE_FOCUS) {
      drawFocusPage(true);
    }
  }
}

void enterConfig() {
  petSetState(ST_CONFIG);
  stateStart = millis();
  beep(1200, 80);
  drawPet(F_LISTEN);
  drawBubbleText("手机连接热点: Wio-Pet", TFT_BLACK, "打开网页 192.168.4.1", TFT_BLACK);
  drawTextCJK("手机完成配置 | 按 B 退出", 64, 218, 320, TFT_LIGHTGREY, C_BOTTOM_BG);
  petAnimSet(A_LISTEN);
  if (!wioPortalBegin("Wio-Pet", activeConfig)) {
    Serial.println("V: portal start failed");
    wioPortalEnd();
    enterIdle();
  }
}

void enterIdle() {
  petSetState(ST_IDLE);
  stateStart = millis();
  curPage = lastPageBeforeVoice;
  if (curPage == PAGE_PET) {
    drawPet(F_NORMAL);
    drawIdleHint();
    petAnimSet(A_IDLE);
  } else if (curPage == PAGE_CLOCK) {
    drawClockPage(true);
  } else if (curPage == PAGE_FOCUS) {
    drawFocusPage(true);
  }
}

// 显示一段表情 + 气泡,durMs 后自动回待机(期间按键也可提前返回)
void enterShow(int face, const String& t1, uint16_t c1, const String& t2, uint32_t durMs) {
  petSetState(ST_SHOW);
  stateStart = millis();
  showUntil = millis() + durMs;
  drawPet(face);
  if (t1.length()) drawBubbleText(t1, c1, t2, TFT_BLACK);
  petAnimSet(A_EMOTE, face);
}

void enterSleep() {
  Serial.println("P: sleep");
  clearChatHistory();
  petSetState(ST_SLEEP);
  stateStart = millis();
  drawPet(F_SLEEP);
  petAnimSet(A_SLEEP);
  setBacklight(true);
}

void wakeUp() {
  Serial.println("P: wake");
  setBacklight(false);
  lastInteract = millis();
  petSetState(ST_IDLE);
  stateStart = millis();
  drawPet(F_SLEEP);
  drawIdleHint();
  petAnimSet(A_WAKE);  // 睁眼动画结束后自动转 A_IDLE
}

void startDizzy() {
  lastInteract = millis();
  petSetState(ST_SHOW);
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

  // 翻转事件检测 (Flip-to-Focus 扣下即专注)
  if (ev == SE_FACEDOWN) {
    Serial.println("P: flip facedown -> focus mode");
    lastInteract = millis();
    curPage = PAGE_FOCUS;
    lastPageBeforeVoice = PAGE_FOCUS;
    startPomodoro();
    setBacklightPower(false);
    beep(880, 40);
    return;
  }
  if (ev == SE_FACEUP) {
    Serial.println("P: flip faceup -> restore display");
    lastInteract = millis();
    setBacklightPower(true);
    beep(1319, 60);
    if (state == ST_IDLE) {
      if (curPage == PAGE_FOCUS) {
        drawFocusPage(true);
      } else if (curPage == PAGE_CLOCK) {
        drawClockPage(true);
      } else {
        drawPet(F_NORMAL);
        drawIdleHint();
      }
    }
    return;
  }

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
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);
  pinMode(WIO_BUZZER, OUTPUT);
  tone(WIO_BUZZER, 1200, 60);

  for (int i = 0; i < 8; i++) pinMode(ALL_KEYS[i], INPUT_PULLUP);
  pinMode(LCD_BACKLIGHT, OUTPUT);
  digitalWrite(LCD_BACKLIGHT, LOW);  // 先保持背光关闭，彻底杜绝开机白屏！

  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 1000) {
  }
  Serial.println("INIT: start");

  display.begin();
  Serial.println("INIT: display ok");

  wioCjkBegin(display);  // 注入 display(解耦点①),之后 drawTextCJK 全局可用
  randomSeed(analogRead(A0) ^ micros());
  wioMicBegin();
  Serial.println("INIT: mic ok");
  wioMicConfig(400, PET_TRAILING_MS, 8000);  // 静音阈值 / 截断静音时长 / 没说话超时
  wioSenseBegin();
  Serial.println("INIT: sense ok");
  wioConfigInit();
  hasActiveConfig = wioConfigLoad(activeConfig);
  Serial.println("INIT: config ok");
  if (!hasActiveConfig) {
#if HAS_COMPILED_SECRETS
    memset(&activeConfig, 0, sizeof(activeConfig));
    strncpy(activeConfig.ssid, WIFI_SSID, sizeof(activeConfig.ssid) - 1);
    strncpy(activeConfig.pass, WIFI_PASS, sizeof(activeConfig.pass) - 1);
    strncpy(activeConfig.baiduApiKey, BAIDU_API_KEY, sizeof(activeConfig.baiduApiKey) - 1);
    strncpy(activeConfig.baiduSecret, BAIDU_SECRET_KEY, sizeof(activeConfig.baiduSecret) - 1);
    strncpy(activeConfig.deepseekKey, DEEPSEEK_KEY, sizeof(activeConfig.deepseekKey) - 1);
    strncpy(activeConfig.city, "上海", sizeof(activeConfig.city) - 1);
    hasActiveConfig = true;
    Serial.println("V: using default compiled secrets");
#endif
  } else {
    // 若 Flash 存储的是旧默认值“深圳”或为空，则平滑迁移为“上海”并持久化
    if (strcmp(activeConfig.city, "深圳") == 0 || strlen(activeConfig.city) == 0) {
      strncpy(activeConfig.city, "上海", sizeof(activeConfig.city) - 1);
      wioConfigSave(activeConfig);
      Serial.println("V: migrated default city to 上海 in Flash");
    }
  }
  applyActiveConfig();
  Serial.println("HELLO pet 1.3");
  drawPet(F_SLEEP);
  digitalWrite(LCD_BACKLIGHT, HIGH);  // 首帧就绪后再亮屏，从深黑优雅平滑醒来！
  if (hasActiveConfig && strlen(activeConfig.ssid) > 0) {
    drawTextCJK("小维醒来中…正在连网", 84, 218, 320, TFT_LIGHTGREY, C_BOTTOM_BG);
    petAnimSet(A_WAKE);
    petNetWarmup();
    if (WiFi.status() == WL_CONNECTED) {
      syncNetworkTime();
    }
  } else {
    drawTextCJK("初次见面! 按 A 键配网", 80, 218, 320, TFT_LIGHTGREY, C_BOTTOM_BG);
    petAnimSet(A_WAKE);
  }
#if PET_TEST_BAD_TOKEN
  wioAsrBaiduDebugToken("invalid_token_for_selftest_0000");
#endif
  lastInteract = millis();
  enterIdle();
  Serial.println("!READY");
}

static int injectedKey = -1;

void petInjectKey(int pin) {
  injectedKey = pin;
}

bool pressed(int pin) {
  if (injectedKey == pin) {
    injectedKey = -1;
    return true;
  }
  static unsigned long lastMs = 0;
  if (digitalRead(pin) != LOW) return false;
  if (millis() - lastMs < 200) return false;
  lastMs = millis();
  return true;
}

uint32_t petFreeRam() {
  char top = 't';
  return (uint32_t)(&top - reinterpret_cast<char*>(sbrk((ptrdiff_t)0)));
}

void handleTestCommands() {
  while (Serial.available()) {
    static String cmdBuf = "";
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '!' && cmdBuf.length() > 0 && !cmdBuf.startsWith("!")) {
      cmdBuf = "";  // 丢弃前面由于端口打开产生的脏字符
    }
    if (c == '\n') {
      cmdBuf.trim();
      if (cmdBuf.length() > 0) {
        if (cmdBuf == "!PING") {
          Serial.println("!PONG");
        } else if (cmdBuf == "!STATUS") {
          Serial.print("!STATUS state=");
          Serial.print(petStateStr(state));
          Serial.print(" anim=");
          Serial.print(petAnimCurrent());
          Serial.print(" page=");
          Serial.print(curPage);
          Serial.print(" pomo=");
          Serial.print(pomoRemainingSec);
          Serial.print(" pomo_run=");
          Serial.print(pomoRunning ? 1 : 0);
          Serial.print(" ram=");
          Serial.print(petFreeRam());
          Serial.print(" uptime=");
          Serial.println(millis());
        } else if (cmdBuf == "!KEY_A" || cmdBuf == "!KEY A") {
          petInjectKey(PIN_KEY_A);
          Serial.println("!OK KEY_A");
        } else if (cmdBuf == "!KEY_B" || cmdBuf == "!KEY B") {
          petInjectKey(PIN_KEY_B);
          Serial.println("!OK KEY_B");
        } else if (cmdBuf == "!KEY_C" || cmdBuf == "!KEY C") {
          petInjectKey(PIN_KEY_C);
          Serial.println("!OK KEY_C");
        } else if (cmdBuf == "!KEY_JOY_L" || cmdBuf == "!KEY_LEFT") {
          petInjectKey(PIN_JOY_L);
          Serial.println("!OK KEY_JOY_L");
        } else if (cmdBuf == "!KEY_JOY_R" || cmdBuf == "!KEY_RIGHT") {
          petInjectKey(PIN_JOY_R);
          Serial.println("!OK KEY_JOY_R");
        } else if (cmdBuf == "!KEY_JOY_PRESS" || cmdBuf == "!KEY_PRESS") {
          petInjectKey(WIO_5S_PRESS);
          Serial.println("!OK KEY_JOY_PRESS");
        } else if (cmdBuf.startsWith("!PAGE ")) {
          int pg = cmdBuf.substring(6).toInt();
          switchPage(pg);
          Serial.print("!OK PAGE ");
          Serial.println(pg);
          Serial.flush();
        } else if (cmdBuf == "!POMO_START") {
          startPomodoro();
          Serial.println("!OK POMO_START");
        } else if (cmdBuf == "!POMO_PAUSE") {
          pausePomodoro();
          Serial.println("!OK POMO_PAUSE");
        } else if (cmdBuf == "!POMO_RESET") {
          resetPomodoro();
          Serial.println("!OK POMO_RESET");
        } else if (cmdBuf == "!CFG_DUMP") {
          Serial.print("!CFG ssid=");
          Serial.print(activeConfig.ssid);
          Serial.print(" city=");
          Serial.println(activeConfig.city);
        } else if (cmdBuf == "!CFG_CLEAR") {
          wioConfigClear();
          Serial.println("!OK CFG_CLEAR");
        } else if (cmdBuf.startsWith("!ANIM ")) {
          int a = cmdBuf.substring(6).toInt();
          petAnimSet(a);
          Serial.print("!OK ANIM ");
          Serial.println(a);
        } else if (cmdBuf.startsWith("!LOOK ")) {
          int lk = cmdBuf.substring(6).toInt();
          drawFeatures(F_NORMAL, lk);
          Serial.print("!OK LOOK ");
          Serial.println(lk);
        }
      }
      cmdBuf = "";
    } else {
      if (cmdBuf.length() < 64) cmdBuf += c;
    }
  }
}

bool anyKeyDown() {
  for (int i = 0; i < 8; i++) {
    if (digitalRead(ALL_KEYS[i]) == LOW) return true;
  }
  return false;
}

void loop() {
  digitalWrite(LED_BUILTIN, ((millis() / 500) % 2) ? HIGH : LOW);
  handleTestCommands();
  petAnimTick();
  handleSense();
  tickPomodoroLogic();
  if (pomoJustFinished) {
    pomoJustFinished = false;
    beep(1568, 150);
    delay(150);
    beep(1760, 250);
    if (state == ST_IDLE && curPage == PAGE_FOCUS) {
      drawFocusPage(false);
    }
  }
  if (hasSyncedTime && millis() > nextTimeSyncMs) {
    syncNetworkTime();
  }
  switch (state) {
    case ST_IDLE: {
      const unsigned long idleFor = millis() - lastInteract;
      if (curPage == PAGE_PET && !pomoRunning) {
        if (idleFor > PET_SLEEP_MS) {
          enterSleep();
          break;
        }
        if (idleFor > PET_DROWSY_MS && petAnimCurrent() == A_IDLE) petAnimSet(A_DROWSY);
      }

      // 实时看板帧刷新
      if (curPage == PAGE_CLOCK) {
        drawClockPage(false);
      } else if (curPage == PAGE_FOCUS) {
        drawFocusPage(false);
      }

      if (pressed(PIN_KEY_A)) {  // A 键:进入端侧热点网页配网
        lastInteract = millis();
        setBacklightPower(true);
        enterConfig();
        break;
      }

      if (pressed(PIN_KEY_B)) {  // B 键:全局对讲问答
        lastInteract = millis();
        setBacklightPower(true);
        lastPageBeforeVoice = curPage;
        beep(988, 50);
        delay(55);  // 等蜂鸣音彻底播完再开麦,杜绝麦克风采集到蜂鸣声造成误触发
        wioRecStart();
        petSetState(ST_RECORD);
        stateStart = millis();
        drawPet(F_LISTEN);
        drawBubbleText("在听…说完我会自己停", TFT_BLACK, "也可再按 B 立即发送 / C 取消", TFT_BLACK);
        petAnimSet(A_LISTEN);
        break;
      }

      if (pressed(PIN_JOY_R)) {  // 摇杆右: 下一页
        setBacklightPower(true);
        switchPage((curPage + 1) % 3);
        beep(1200, 30);
        break;
      }
      if (pressed(PIN_JOY_L)) {  // 摇杆左: 上一页
        setBacklightPower(true);
        switchPage((curPage + 2) % 3);
        beep(1200, 30);
        break;
      }

      if (curPage == PAGE_PET) {
        if (pressed(PIN_KEY_C)) {  // C 键:叫醒犯困的小维
          lastInteract = millis();
          petAnimSet(A_IDLE);
          break;
        }
        if (pressed(WIO_5S_PRESS) || pressed(WIO_5S_UP) || pressed(WIO_5S_DOWN)) {  // 摸头/互动
          lastInteract = millis();
          beep(1568, 80);
          enterShow(F_HAPPY, "", TFT_BLACK, "", 1200);
          break;
        }
      } else if (curPage == PAGE_CLOCK) {
        if (pressed(WIO_5S_PRESS)) {  // 压下对时
          lastInteract = millis();
          beep(1200, 50);
          drawTextCJK("正在网络对时...", 100, 160, 240, C_TEXT_GOLD, C_BG_CLOCK);
          if (syncNetworkTime()) {
            beep(1568, 80);
          } else {
            beep(440, 150);
          }
          drawClockPage(true);
          break;
        }
      } else if (curPage == PAGE_FOCUS) {
        if (pressed(WIO_5S_PRESS)) {  // 启停番茄钟
          lastInteract = millis();
          if (pomoRunning) {
            pausePomodoro();
            beep(600, 80);
          } else {
            startPomodoro();
            beep(1200, 80);
          }
          drawFocusPage(true);
          break;
        }
        if (pressed(PIN_KEY_C)) {  // 重置番茄钟
          lastInteract = millis();
          resetPomodoro();
          beep(880, 80);
          drawFocusPage(true);
          break;
        }
      }
      break;
    }

    case ST_RECORD: {
      uint32_t samples = 0, hint = 0;

      // 1. 按键干预：
      // - 录音超 200ms 后按 C 键：取消本次录音，快速返回待机
      // - 录音超 200ms 后按 B 键：提前结束说话，手动立即送入思考
      if (millis() - stateStart > 200) {
        if (pressed(PIN_KEY_C)) {
          wioRecPoll(samples, hint);  // 关麦清理
          beep(440, 60);
          enterIdle();
          break;
        }
        if (pressed(PIN_KEY_B)) {
          wioRecPoll(samples, hint);  // 关麦清理
          recSamples = (samples > 1600) ? samples : 1600;
          recBufferFull = false;
          beep(880, 50);
          petSetState(ST_THINK);
          stateStart = millis();
          drawPet(F_THINK);
          drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
          petAnimSet(A_THINK);
          break;
        }
      }

      // 2. 底层 VAD 自动判停
      const int st = wioRecPoll(samples, hint);
      if (st == 2) {  // 超时没说话
        beep(196, 250);
        enterShow(F_SAD, "你还没说话呢~", TFT_BLACK, "按一下 B 再开口就好", 3000);
        break;
      }
      if (st == 1 || st == 3) {  // 录完: 1=正常说完截断, 3=录满3秒强行截断
        recSamples = samples;
        recBufferFull = (st == 3);
        if (recBufferFull) {
          Serial.println("V: buffer full (hit 3s limit)");
        }
        beep(880, 50);
        petSetState(ST_THINK);
        stateStart = millis();
        drawPet(F_THINK);
        drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
        petAnimSet(A_THINK);
        break;
      }

      // 3. 硬件/环境硬看门狗：录音最长决不允许超过 4.0 秒，杜绝任何卡死
      if (millis() - stateStart > 4000) {
        wioRecPoll(samples, hint);  // 停止底层录音
        if (samples > 3200) {
          recSamples = samples;
          recBufferFull = true;
          beep(880, 50);
          petSetState(ST_THINK);
          stateStart = millis();
          drawPet(F_THINK);
          drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
          petAnimSet(A_THINK);
        } else {
          beep(196, 250);
          enterShow(F_SAD, "你还没说话呢~", TFT_BLACK, "按一下 B 再开口就好", 3000);
        }
        break;
      }
      break;
    }

    case ST_THINK: {
      // 识别 + 回答(阻塞数秒;等待期间 petAnimTick 由网络循环驱动)
      String t, r, note;
      int emo = EMO_HAPPY;
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, recBufferFull, t, r, emo, note);
      petPrintTiming(millis() - tProc);
      if (ok) {
        beep(1319, 90);
        const int face = (emo >= 0 && emo < 6) ? EMO_FACE[emo] : F_HAPPY;
        String cleanR = "";
        for (size_t i = 0; i < r.length(); i++) {
          char c = r[i];
          if (c != '*' && c != '#' && c != '`') cleanR += c;
        }
        enterShow(face, "你:" + t, 0x8410,
                  cleanR.length() ? "小维:" + cleanR : String("(还没配置 DeepSeek Key,我不会说话呀)"), 15000);
      } else {
        beep(196, 250);
        if (note == "asr buffer full") {
          enterShow(F_CONFUSED, "呜…一句话太长啦~", 0x8410, "单次说话请在3秒内哦", 15000);
        } else {
          enterShow(F_SAD, "呜…" + friendlyNote(note), 0x8410, note, 15000);
        }
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

    case ST_CONFIG: {
      if (millis() - stateStart > 300 && (pressed(PIN_KEY_B) || pressed(PIN_KEY_C) || pressed(PIN_KEY_A))) {
        Serial.println("V: exit config by button");
        beep(880, 80);
        wioPortalEnd();
        enterIdle();
        break;
      }
      WioConfig newCfg;
      const int st = wioPortalPoll(newCfg);
      if (st == 1) {  // 手机配网已保存
        Serial.println("V: config saved from web");
        beep(1568, 150);
        activeConfig = newCfg;
        hasActiveConfig = true;
        wioPortalEnd();
        drawPet(F_HAPPY);
        drawBubbleText("配置保存成功！", TFT_BLACK, "正在重新连网中…", TFT_BLACK);
        petAnimSet(A_EMOTE, F_HAPPY);
        delay(1200);
        applyActiveConfig();
        petNetWarmup();
        enterIdle();
        break;
      }
      if (st == 2) {  // 手机网页点击退出
        Serial.println("V: exit config by web");
        beep(880, 80);
        wioPortalEnd();
        enterIdle();
        break;
      }
      break;
    }
  }
}


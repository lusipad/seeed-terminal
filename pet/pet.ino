// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机会眨眼、张望、哼歌;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。

#include <Arduino.h>
#include <Seeed_GFX.h>
#include <WioKitLogic.h>  // L0 纯逻辑(原 pet_logic.h,库化后唯一来源在 libraries/WioKit)

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include "cjk.h"  // (下一步迁移到 WioKitCjk)
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

#include "voice_pet.h"  // 语音链路(麦克风 DMA/百度ASR/DeepSeek)
#include "pet_sense.h"  // 光线 + IMU

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

// Emotion(pet_logic.h)→ 表情;顺序必须与 enum Emotion 一致:开心 兴奋 惊讶 害羞 疑惑 难过
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
  const int ev = petSensePoll();
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
  randomSeed(analogRead(A0) ^ micros());
  petMicBegin();
  petSenseBegin();
  Serial.println("HELLO pet 1.2");
  drawPet(F_SLEEP);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
  petAnimSet(A_WAKE);
  petNetWarmup();
#if PET_TEST_BAD_TOKEN
  baiduToken = "invalid_token_for_selftest_0000";
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
        petRecStart();
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
      const int st = petRecPoll(samples, hint);
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

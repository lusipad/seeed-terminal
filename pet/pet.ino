// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机会眨眼、张望、哼歌;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。

#include <Arduino.h>
#include <Seeed_GFX.h>

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include "cjk.h"
#include "pet_face.h"
#include "pet_anim.h"

const int PIN_KEY_B = WIO_KEY_B;
const int PIN_KEY_C = WIO_KEY_C;
const int PIN_JOY_L = WIO_5S_LEFT;
const int PIN_JOY_R = WIO_5S_RIGHT;

void beep(int freq, int dur) {
  tone(WIO_BUZZER, freq, dur);
}

#include "voice_pet.h"  // 语音链路(麦克风 DMA/百度ASR/DeepSeek)

// ============================================================
// 状态机
// ============================================================

enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW };
PetState state = ST_IDLE;
unsigned long stateStart = 0;
unsigned long showUntil = 0;
uint32_t recSamples = 0;

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

void setup() {
  pinMode(PIN_KEY_B, INPUT_PULLUP);
  pinMode(PIN_KEY_C, INPUT_PULLUP);
  pinMode(PIN_JOY_L, INPUT_PULLUP);
  pinMode(PIN_JOY_R, INPUT_PULLUP);

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
  Serial.println("HELLO pet 1.2");
  drawPet(F_SLEEP);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
  petAnimSet(A_WAKE);
  petNetWarmup();
#if PET_TEST_BAD_TOKEN
  baiduToken = "invalid_token_for_selftest_0000";
#endif
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
  return digitalRead(PIN_KEY_B) == LOW || digitalRead(PIN_KEY_C) == LOW ||
         digitalRead(PIN_JOY_L) == LOW || digitalRead(PIN_JOY_R) == LOW;
}

void loop() {
  petAnimTick();
  switch (state) {
    case ST_IDLE: {
      if (pressed(PIN_JOY_L) || pressed(PIN_JOY_R)) {  // 摸头
        beep(1568, 80);
        enterShow(F_HAPPY, "", TFT_BLACK, "", 1200);
        break;
      }
      if (pressed(PIN_KEY_B)) {
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
  }
}

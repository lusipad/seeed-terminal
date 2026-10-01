// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机安静会眨眼;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。

#include <Arduino.h>
#include <Seeed_GFX.h>

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include "cjk.h"
#include "pet_face.h"

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
unsigned long lastBlink = 0;
uint32_t recSamples = 0;
String showT1 = "", showT2 = "";
int showFace = F_NORMAL;

void drawIdleHint() {
  drawTextCJK("按一下 B 说话,说完我自己停", 62, 220, 320, TFT_DARKGREY);
}

void blinkEyes() {
  const int ex[2] = {CX - 19, CX + 13};
  const int ey = CY - 12;
  for (int i = 0; i < 2; i++) {
    display.fillRect(ex[i] - 2, ey - 5, 10, 16, C_BODY);
    display.fillRect(ex[i], ey + 3, 6, 3, TFT_BLACK);
  }
  delay(160);
  for (int i = 0; i < 2; i++) {
    display.fillRect(ex[i] - 2, ey - 5, 10, 16, C_BODY);
    display.fillRect(ex[i], ey - 3, 6, 10, TFT_BLACK);
  }
}

void enterIdle() {
  state = ST_IDLE;
  stateStart = millis();
  lastBlink = millis();
  drawPet(0, F_NORMAL);
  drawIdleHint();
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
  petMicBegin();
  Serial.println("HELLO pet 1.1");
  drawPet(0, F_NORMAL);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
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

bool anyKeyPressed() {
  const int pins[4] = {PIN_KEY_B, PIN_KEY_C, PIN_JOY_L, PIN_JOY_R};
  for (int i = 0; i < 4; i++) {
    if (digitalRead(pins[i]) == LOW) {
      delay(30);
      return true;
    }
  }
  return false;
}

void loop() {
  switch (state) {
    case ST_IDLE: {
      if (millis() - lastBlink > 3200) {
        lastBlink = millis();
        blinkEyes();
      }
      if (pressed(PIN_JOY_L) || pressed(PIN_JOY_R)) {
        beep(1568, 80);
        drawPet(0, F_HAPPY);
        display.setTextSize(1);
        display.setTextColor(TFT_DARKGREY);
        display.drawString("hehe ~", 140, 224);
        delay(900);
        enterIdle();
        break;
      }
      if (pressed(PIN_KEY_B)) {
        petRecStart();
        state = ST_RECORD;
        stateStart = millis();
        drawPet(0, F_LISTEN);
        drawBubbleText("在听…说完我会自己停", TFT_BLACK, "", TFT_BLACK);
        beep(988, 60);
      }
      break;
    }

    case ST_RECORD: {
      uint32_t samples = 0, hint = 0;
      const int st = petRecPoll(samples, hint);
      if (st == 2) {  // 超时没说话
        state = ST_SHOW;
        stateStart = millis();
        showFace = F_SAD;
        showT1 = "你还没说话呢~";
        showT2 = "按一下 B 再开口就好";
        beep(196, 250);
        drawPet(0, showFace);
        drawBubbleText(showT1, TFT_BLACK, showT2, TFT_BLACK);
        break;
      }
      if (st == 1) {  // 录完
        recSamples = samples;
        beep(880, 50);
        state = ST_THINK;
        stateStart = millis();
        drawPet(0, F_THINK);
        drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
      }
      break;
    }

    case ST_THINK: {
      // 识别 + 回答(阻塞数秒)
      String t, r, note;
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, t, r, note);
      petPrintTiming(millis() - tProc);
      state = ST_SHOW;
      stateStart = millis();
      if (ok) {
        showFace = F_HAPPY;
        showT1 = "你:" + t;
        showT2 = (r.length() ? "小维:" + r : String("(还没配置 DeepSeek Key,我不会说话呀)"));
        beep(1319, 90);
      } else {
        showFace = F_SAD;
        showT1 = "呜…出问题了";
        showT2 = note;
        beep(196, 250);
      }
      drawPet(0, showFace);
      drawBubbleText(showT1, 0x8410, showT2, TFT_BLACK);
      break;
    }

    case ST_SHOW: {
      if (millis() - stateStart > 15000 || anyKeyPressed()) {
        enterIdle();
      }
      break;
    }
  }
}

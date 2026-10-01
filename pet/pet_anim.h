// ---- 动画调度器:非阻塞,按 millis() 推进,每次 tick 最多画一帧 ----
// loop() 与网络等待循环(readHttpBody / 上传 / 连 WiFi)都调用 petAnimTick(),阻塞请求期间画面照样动
#pragma once

enum Anim { A_NONE, A_IDLE, A_LISTEN, A_THINK, A_EMOTE, A_WAKE, A_DROWSY, A_SLEEP, A_DIZZY };

int animCur = A_NONE;
int animFace = F_NORMAL;
int animStep = 0;
unsigned long animNext = 0;

// A_IDLE 内部:眨眼 + 随机小动作(1=张望 2=哼歌 3=歪头)
bool idleBlinking = false;
unsigned long idleBlinkAt = 0;
int idleAct = 0;
int idleStep = 0;
unsigned long idleActAt = 0;

void petAnimSet(int anim, int face = F_NORMAL) {
  animCur = anim;
  animFace = face;
  animStep = 0;
  animNext = 0;  // 下一次 tick 立即画第一帧
  const unsigned long now = millis();
  idleBlinking = false;
  idleBlinkAt = now + random(2500, 5000);
  idleAct = 0;
  idleStep = 0;
  idleActAt = now + random(8000, 20000);
}

int petAnimCurrent() { return animCur; }

void endIdleAct(unsigned long now) {
  idleAct = 0;
  idleStep = 0;
  idleActAt = now + random(8000, 20000);
  animNext = now + 100;
}

void tickIdle(unsigned long now) {
  if (animStep == 0) {  // 进入待机:复位五官与装饰
    clearDeco();
    drawFeatures(F_NORMAL);
    animStep = 1;
  }
  if (idleAct == 1) {  // 张望:左 → 中 → 右 → 中
    static const int LOOK[4] = {-4, 0, 4, 0};
    drawEyesOnly(F_NORMAL, LOOK[idleStep]);
    if (++idleStep >= 4) endIdleAct(now);
    else animNext = now + 350;
    return;
  }
  if (idleAct == 2) {  // 哼歌:开心嘴 + ♪ 从右侧往上飘
    if (idleStep == 0) drawFeatures(F_HAPPY);
    clearDeco();
    if (idleStep < 4) drawNote(DECO_RX + 10 + 4 * idleStep, DECO_Y + 48 - 10 * idleStep, C_GOLD);
    if (++idleStep >= 5) {
      drawFeatures(F_NORMAL);
      endIdleAct(now);
    } else {
      animNext = now + 300;
    }
    return;
  }
  if (idleAct == 3) {  // 歪头:眼睛偏一侧 + 疑惑嘴,停 1 秒
    if (idleStep == 0) {
      drawFeatures(F_CONFUSED, 3);
      idleStep = 1;
      animNext = now + 1000;
      return;
    }
    drawFeatures(F_NORMAL);
    endIdleAct(now);
    return;
  }
  if (idleBlinking) {  // 眨眼的第二帧:睁眼
    drawEyesOnly(F_NORMAL, 0);
    idleBlinking = false;
    idleBlinkAt = now + random(2500, 5000);
  } else if (now >= idleActAt) {
    idleAct = random(1, 4);
    idleStep = 0;
    animNext = now;
    return;
  } else if (now >= idleBlinkAt) {
    drawEyesOnly(F_BLINK, 0);
    idleBlinking = true;
    animNext = now + 160;
    return;
  }
  animNext = (idleBlinkAt < idleActAt) ? idleBlinkAt : idleActAt;
}

void petAnimTick() {
  const unsigned long now = millis();
  if (animCur == A_NONE || now < animNext) return;
  switch (animCur) {
    case A_IDLE:
      tickIdle(now);
      break;
    case A_LISTEN:
      if (animStep == 0) drawFeatures(F_LISTEN);
      drawSoundBars(animStep);
      animStep++;
      animNext = now + 150;
      break;
    case A_THINK: {  // 眼睛左右看 + 三个点循环
      static const int LOOK[4] = {0, -4, 0, 4};
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_THINK);
      }
      drawEyesOnly(F_NORMAL, LOOK[animStep % 4]);
      drawThinkDots(animStep % 3 + 1);
      animStep++;
      animNext = now + 300;
      break;
    }
    case A_EMOTE:  // 表情 + 装饰;兴奋时星光闪烁,其余静止
      if (animStep == 0) drawFeatures(animFace);
      drawEmoteDeco(animFace, animStep);
      animStep++;
      animNext = now + (animFace == F_EXCITED ? 400 : 60000);
      break;
    case A_WAKE: {  // 慢慢睁眼,结束后自动转待机
      static const int SEQ[4] = {F_SLEEP, F_SLEEPY, F_SLEEPY, F_NORMAL};
      if (animStep == 0) clearDeco();
      drawEyesOnly(SEQ[animStep], 0);
      if (++animStep >= 4) {
        petAnimSet(A_IDLE);
        return;
      }
      animNext = now + 250;
      break;
    }
    case A_DROWSY:  // 半眯眼;每 6 秒打一次哈欠(0.8 秒)
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_SLEEPY);
        animStep = 1;
        animNext = now + 6000;
      } else if (animStep == 1) {
        drawFeatures(F_YAWN);
        animStep = 2;
        animNext = now + 800;
      } else {
        drawFeatures(F_SLEEPY);
        animStep = 1;
        animNext = now + 6000;
      }
      break;
    case A_SLEEP:
      if (animStep == 0) drawFeatures(F_SLEEP);
      drawZzz(animStep);
      animStep++;
      animNext = now + 500;
      break;
    case A_DIZZY:  // 蚊香眼左右晃
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_DIZZY);
      }
      drawEyesOnly(F_DIZZY, (animStep % 2) ? 2 : -2);
      animStep++;
      animNext = now + 100;
      break;
    default:
      break;
  }
}

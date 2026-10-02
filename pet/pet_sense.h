// ---- 传感器:光线(关灯睡觉)+ IMU(摇晃/拿起);判定逻辑在 pet_logic.h ----
// 只在 IDLE / SHOW / SLEEP 状态调用 petSensePoll(录音时不碰 ADC,避免干扰麦克风 DMA)
#pragma once
#include <LIS3DHTR.h>
#include "wiring_private.h"  // pinPeripheral

enum SenseEvent { SE_NONE, SE_DARK, SE_LIGHT, SE_SHAKE, SE_PICKUP };

// 光线阈值(0-1023,越小越暗):把 PET_SENSE_DEBUG 设 1,看日志 "S: light=" 实测后改
const int PET_DARK_TH = 60;
const int PET_LIGHT_TH = 120;
#define PET_LIGHT_ENABLED 0  // 光线读数在麦克风共用 ADC1 时尚不可靠(恒为 ~1),确认前不让它触发睡觉/唤醒
#ifndef PET_SENSE_DEBUG
#define PET_SENSE_DEBUG 1  // 1 = 每 2 秒打印光线与加速度,用于标定
#endif

LIS3DHTR<TwoWire> lis;
bool imuOk = false;
LightDetector lightDet(PET_DARK_TH, PET_LIGHT_TH, 10000, 2000);
MotionDetector motionDet(800, 300, 3000);
unsigned long lightNext = 0, imuNext = 0, senseDbgNext = 0;
long lightAvg = -1;
int lastAx = 0, lastAy = 0, lastAz = 0;

// 光线传感器(PD01/AIN15)与麦克风(AIN12)共用 ADC1:麦克风让 ADC1 自由运行 + DMA 持续搬运。
// 不能用 analogRead —— 它会改通道并在读完后关掉 ADC1,麦克风随之停摆。
// 这里临时把通道切到光线(并加长采样时间)、等几次转换、读结果,再恢复麦克风的设置;ADC1 全程不停。
int readLightShared() {
  const uint8_t micCh = g_APinDescription[WIO_MIC].ulADCChannelNumber;
  const uint8_t micSamplen = ADC1->SAMPCTRL.bit.SAMPLEN;
  ADC1->SAMPCTRL.bit.SAMPLEN = 63;  // 光敏电路内阻高:麦克风设的最短采样时间充不满采样电容,读数会接近 0
  while (ADC1->SYNCBUSY.bit.SAMPCTRL) {
  }
  ADC1->INPUTCTRL.bit.MUXPOS = g_APinDescription[WIO_LIGHT].ulADCChannelNumber;
  while (ADC1->SYNCBUSY.bit.INPUTCTRL) {
  }
  delay(2);  // 等若干次转换,丢掉切换前旧通道/旧采样时间的结果
  const int v = ADC1->RESULT.reg;  // 12 bit
  ADC1->INPUTCTRL.bit.MUXPOS = micCh;
  while (ADC1->SYNCBUSY.bit.INPUTCTRL) {
  }
  ADC1->SAMPCTRL.bit.SAMPLEN = micSamplen;
  while (ADC1->SYNCBUSY.bit.SAMPCTRL) {
  }
  return v >> 2;  // 折算成 0-1023,与阈值量程一致
}

void petSenseBegin() {
  pinPeripheral(WIO_LIGHT, PIO_ANALOG);
  lis.begin(Wire1);
  imuOk = lis.isConnection();
  if (imuOk) {
    lis.setOutputDataRate(LIS3DHTR_DATARATE_50HZ);
    lis.setFullScaleRange(LIS3DHTR_RANGE_2G);
  }
  Serial.println(imuOk ? "S: imu ok" : "S: imu FAIL (shake/pickup disabled)");
}

// 非阻塞:到采样时间才读;每次最多返回一个事件
int petSensePoll() {
  const unsigned long now = millis();
  int ev = SE_NONE;
  if (now >= lightNext) {
    lightNext = now + 500;
    const int raw = readLightShared();
    lightAvg = (lightAvg < 0) ? raw : (lightAvg * 3 + raw) / 4;
    const int r = lightDet.update((int)lightAvg, (uint32_t)now);
#if PET_LIGHT_ENABLED
    if (r == 1) ev = SE_DARK;
    else if (r == 2) ev = SE_LIGHT;
#else
    (void)r;
#endif
  }
  if (imuOk && now >= imuNext) {
    imuNext = now + 50;
    lastAx = (int)(lis.getAccelerationX() * 1000);
    lastAy = (int)(lis.getAccelerationY() * 1000);
    lastAz = (int)(lis.getAccelerationZ() * 1000);
    const int m = motionDet.update(lastAx, lastAy, lastAz, (uint32_t)now);
    if (m == MOTION_SHAKE) ev = SE_SHAKE;
    else if (m == MOTION_PICKUP && ev == SE_NONE) ev = SE_PICKUP;
  }
#if PET_SENSE_DEBUG
  if (now >= senseDbgNext) {
    senseDbgNext = now + 2000;
    Serial.print("S: light=");
    Serial.print(lightAvg);
    Serial.print(" a=");
    Serial.print(lastAx);
    Serial.print(",");
    Serial.print(lastAy);
    Serial.print(",");
    Serial.print(lastAz);
    Serial.print(" adc1_en=");  // 麦克风要求 ADC1 保持使能且通道停在 AIN12
    Serial.print(ADC1->CTRLA.bit.ENABLE);
    Serial.print(" mux=");
    Serial.println(ADC1->INPUTCTRL.bit.MUXPOS);
  }
#endif
  return ev;
}

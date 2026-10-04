// ---- L1 传感器:光线(关灯睡觉)+ IMU(摇晃/拿起);判定逻辑在 WioKitLogic.h(L0) ----
// 光线传感器(PD01/AIN15)与麦克风(AIN12)共用 ADC1:这里用"共享读法"——
// 临时切通道、等几次转换、读结果、恢复麦克风设置,ADC1 全程不停,麦克风 DMA 不受干扰。
// 勿改成 analogRead:它会改通道并在读完后关掉 ADC1,麦克风随之停摆(踩坑成果)。
// 只在非录音状态调用 wioSensePoll();录音期间 ADC 采样属于麦克风。
#pragma once
#include <Arduino.h>

enum SenseEvent { SE_NONE, SE_DARK, SE_LIGHT, SE_SHAKE, SE_PICKUP, SE_FACEDOWN, SE_FACEUP };

// 查询当前设备是否处于正面朝下平扣状态
bool wioSenseIsFaceDown();

// 光线读数在麦克风共用 ADC1 时尚不可靠(恒为 ~1):默认不触发睡觉/唤醒,
// 真机标定确认后改 1 启用。WIO_SENSE_DEBUG=1 时每 2 秒打印光线/加速度/ADC 状态用于标定。
#ifndef WIO_SENSE_LIGHT_ENABLED
#define WIO_SENSE_LIGHT_ENABLED 0
#endif
#ifndef WIO_SENSE_DEBUG
#define WIO_SENSE_DEBUG 1
#endif

// ADC1 共享读法 + LIS3DH @Wire1。返回 IMU 是否就绪;失败时摇晃/拿起不可用,光线仍可用
bool wioSenseBegin();

// 阈值(默认 60 / 120 / 800 / 300 / 3000,光线量程 0-1023、加速度单位 mg):
// darkTh 越小越暗;shakeMg/pickupMg 为偏离/变化阈值;stillMs 静止多久才算放稳
void wioSenseConfig(int darkTh, int lightTh, int shakeMg, int pickupMg, uint32_t stillMs);

// 非阻塞:到采样时间才读;每次最多返回一个事件
int wioSensePoll();

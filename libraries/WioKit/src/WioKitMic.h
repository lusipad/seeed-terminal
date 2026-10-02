// ---- L1 麦克风:官方 Seeed Arduino Mic 库(DMA 16bit 采样 + FilterBuHp 高通),
// ---- 按下即录,应用轮询声能自动截断(VAD),首尾静音裁剪 ----
// 96KB PCM 缓冲是库内静态数组(int16 x 48000 ≈ 3 秒 @16kHz,占 SAMD51 RAM 一半),
// 经 wioRecBuffer() 零拷贝暴露给应用——复制一份即爆内存,勿拷贝。
#pragma once
#include <Arduino.h>

#define WIO_MIC_SAMPLE_RATE 16000U
#define WIO_MIC_MAX_SAMPLES 48000U  // 3 秒 @16kHz

// 初始化 DMA 采集 + 高通滤波;失败返回 false(打印 "V: mic init FAIL")
bool wioMicBegin();

// 调参(可不调,默认 400 / 900 / 8000):
// silenceAvg  16bit 尺度的静音能量阈值;trailingMs 说完静音多久自动停;
// noSpeechMs  一直没说话的超时
void wioMicConfig(int silenceAvg, uint32_t trailingMs, uint32_t noSpeechMs);

void wioRecStart();

// 轮询:0=录音中 1=录完(VAD 截断或缓冲录满) 2=超时没说话
// samples=本次有效样本数;hint=累计有声样本数(应用可忽略)
int wioRecPoll(uint32_t& samples, uint32_t& hint);

// 内部 PCM,零拷贝;下次 wioRecStart() 前有效
const int16_t* wioRecBuffer();

// 首尾静音裁剪:调用前 lo=0、hi=样本数;返回后 [lo,hi) 为有效语音区间(不搬数据)。
// 裁剪阈值 400 为实测值,与 VAD 的 silenceAvg 相互独立。
void wioRecTrim(uint32_t& lo, uint32_t& hi);

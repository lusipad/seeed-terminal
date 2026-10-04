#include "WioKitMic.h"
#include <mic.h>
#include "processing/filters.h"

static int16_t recPcm[WIO_MIC_MAX_SAMPLES];

static volatile uint16_t micIdx = 0;
static volatile uint8_t micRecording = 0;
static volatile bool micDone = false;
static FilterBuHp micFilter;

static int micSilenceAvg = 400;
static uint32_t micTrailingMs = 900;
static uint32_t micNoSpeechMs = 8000;

// 轮询状态(文件内静态:上一轮的 VAD 记忆)
static bool speechSeen = false;
static uint32_t lastVoice = 0;
static uint32_t recStart = 0;
static uint32_t lastPoll = 0;

static mic_config_t mic_config{
  .channel_cnt = 1,
  .sampling_rate = WIO_MIC_SAMPLE_RATE,
  .buf_size = 320,
  .debug_pin = 1,
};
static DMA_ADC_Class Mic(&mic_config);

static void audio_rec_callback(uint16_t* buf, uint32_t buf_len) {
  if (!micRecording) return;
  for (uint32_t i = 0; i < buf_len; i++) {
    // 12bit 无偏 ADC(中点 1024)转 16bit PCM,过高通去直流
    recPcm[micIdx++] = micFilter.step((int16_t)(buf[i] - 1024) * 16);
    if (micIdx >= WIO_MIC_MAX_SAMPLES) {
      micRecording = 0;
      micDone = true;
      break;
    }
  }
}

bool wioMicBegin() {
  Mic.set_callback(audio_rec_callback);
  if (!Mic.begin()) {
    Serial.println("V: mic init FAIL");
    return false;
  }
  Serial.println("V: mic init ok");
  return true;
}

void wioMicConfig(int silenceAvg, uint32_t trailingMs, uint32_t noSpeechMs) {
  micSilenceAvg = silenceAvg;
  micTrailingMs = trailingMs;
  micNoSpeechMs = noSpeechMs;
}

void wioRecStart() {
  micIdx = 0;
  micDone = false;
  micRecording = 1;
  recStart = millis();
  speechSeen = false;
  lastVoice = millis();
  lastPoll = 0;
}

// 轮询:返回 0=还在录 1=录完(结束) 2=超时没说话 3=缓冲录满(达到 3 秒上限强行截断)
int wioRecPoll(uint32_t& samples, uint32_t& speechHint) {
  const uint32_t now = millis();
  const int window = (micIdx < 1600) ? micIdx : 1600;
  uint32_t sum = 0;
  for (int i = 0; i < window; i++) {
    const int16_t v = recPcm[micIdx - 1 - i];
    sum += (v < 0) ? -v : v;
  }
  const uint32_t avg = window ? sum / window : 0;
  const bool voiced = (avg > (uint32_t)micSilenceAvg);

  if (now - lastPoll < 80) return 0;
  lastPoll = now;

  if (voiced) {
    speechHint += window;
    speechSeen = true;
    lastVoice = now;
  }

  // 1. 硬件 DMA 录满 48000 样本(3 秒)
  if (micDone || micIdx >= WIO_MIC_MAX_SAMPLES) {
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 3;
  }

  // 2. 正常说话后，静音时长超过 trailing 阈值截断
  if (speechSeen && (now - lastVoice > micTrailingMs)) {
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 1;
  }

  // 3. 总体录音时长保护(最多 3.5 秒或设定的 noSpeechMs)
  // 如果期间捕获过声音则作为说话完成截断(1)，完全无声才报超时(2)
  if ((now - recStart > micNoSpeechMs) || (now - recStart > 3500)) {
    micRecording = 0;
    samples = micIdx;
    const bool hadSpeech = speechSeen;
    speechSeen = false;
    return hadSpeech ? 1 : 2;
  }

  return 0;
}

const int16_t* wioRecBuffer() { return recPcm; }

void wioRecTrim(uint32_t& lo, uint32_t& hi) {
  while (lo < hi && abs(recPcm[lo]) < 400) lo++;
  while (hi > lo + 1600 && abs(recPcm[hi - 1]) < 400) hi--;
}

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
}

// 轮询:返回 0=还在录 1=录完(结束) 2=超时没说话
int wioRecPoll(uint32_t& samples, uint32_t& speechHint) {
  const int window = (micIdx < 1600) ? micIdx : 1600;
  uint32_t sum = 0;
  for (int i = 0; i < window; i++) {
    const int16_t v = recPcm[micIdx - 1 - i];
    sum += (v < 0) ? -v : v;
  }
  const uint32_t avg = window ? sum / window : 0;
  const bool voiced = (avg > (uint32_t)micSilenceAvg);

  if (millis() - lastPoll < 100) return 0;
  lastPoll = millis();

  if (voiced) {
    speechHint += window;
    if (!speechSeen) { recStart = millis(); speechSeen = true; }
    lastVoice = millis();
  }

  if (micDone) {  // 缓冲录满
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 1;
  }
  if (speechSeen && millis() - lastVoice > micTrailingMs) {  // 说完,自动截断
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 1;
  }
  if (millis() - recStart > micNoSpeechMs) {  // 一直没说话
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 2;
  }
  return 0;
}

const int16_t* wioRecBuffer() { return recPcm; }

void wioRecTrim(uint32_t& lo, uint32_t& hi) {
  while (lo < hi && abs(recPcm[lo]) < 400) lo++;
  while (hi > lo + 1600 && abs(recPcm[hi - 1]) < 400) hi--;
}

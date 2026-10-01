// ---- AI 桌宠语音链路 ----
// 录音:官方 Seeed Arduino Mic 库(DMA 16bit 采样 + 高通滤波),按一下就录,
//       由 pet.ino 轮询声能自动截断;识别百度,回答 DeepSeek,结果引用返回。

#include <Arduino.h>
#if __has_include("wifi_secrets.h")
#define PET_HAS_WIFI 1
#include <rpcWiFi.h>
#include <rpcWiFiClientSecure.h>
#include <ArduinoJson.h>
#include "wifi_secrets.h"
#else
#define PET_HAS_WIFI 0
#endif

#if PET_HAS_WIFI

#include <mic.h>
#include "processing/filters.h"

const uint32_t PET_SAMPLE_RATE = 16000;
const uint32_t PET_MAX_SAMPLES = 48000;  // 3 秒
int16_t petPcm[PET_MAX_SAMPLES];

volatile uint16_t micIdx = 0;
volatile uint8_t micRecording = 0;
volatile bool micDone = false;
FilterBuHp micFilter;

const int PET_SILENCE_AVG = 400;   // 16bit 尺度:低于此视为静音(可调)
const uint32_t PET_TRAILING_MS = 1300;  // 说完静音多久自动停
const uint32_t PET_NO_SPEECH_MS = 8000;

mic_config_t mic_config{
  .channel_cnt = 1,
  .sampling_rate = PET_SAMPLE_RATE,
  .buf_size = 320,
  .debug_pin = 1,
};
DMA_ADC_Class Mic(&mic_config);

static void audio_rec_callback(uint16_t* buf, uint32_t buf_len) {
  if (!micRecording) return;
  for (uint32_t i = 0; i < buf_len; i++) {
    // 12bit 无偏 ADC(中点 1024)转 16bit PCM,过高通去直流
    petPcm[micIdx++] = micFilter.step((int16_t)(buf[i] - 1024) * 16);
    if (micIdx >= PET_MAX_SAMPLES) {
      micRecording = 0;
      micDone = true;
      break;
    }
  }
}

void petMicBegin() {
  Mic.set_callback(audio_rec_callback);
  if (!Mic.begin()) {
    Serial.println("V: mic init FAIL");
  } else {
    Serial.println("V: mic init ok");
  }
}

void petRecStart() {
  micIdx = 0;
  micDone = false;
  micRecording = 1;
}

// 轮询:返回 0=还在录 1=录完(结束) 2=超时没说话
int petRecPoll(uint32_t& samples, uint32_t& speechHint) {
  const int window = (micIdx < 1600) ? micIdx : 1600;
  uint32_t sum = 0;
  for (int i = 0; i < window; i++) {
    const int16_t v = petPcm[micIdx - 1 - i];
    sum += (v < 0) ? -v : v;
  }
  const uint32_t avg = window ? sum / window : 0;
  const bool voiced = (avg > PET_SILENCE_AVG);
  static bool speechSeen = false;
  static uint32_t lastVoice = 0;
  static uint32_t recStart = 0;
  static uint32_t lastPoll = 0;

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
  if (speechSeen && millis() - lastVoice > PET_TRAILING_MS) {  // 说完,自动截断
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 1;
  }
  if (millis() - recStart > PET_NO_SPEECH_MS) {  // 一直没说话
    micRecording = 0;
    samples = micIdx;
    speechSeen = false;
    return 2;
  }
  return 0;
}

const char B64TAB[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
struct B64State { uint8_t carry[2]; uint8_t ncarry; };
char b64Out[1024];
size_t b64OutLen = 0;

template <typename ClientT>
void b64OutPush(ClientT& client, const char* g) {
  if (b64OutLen + 4 > sizeof(b64Out)) {
    client.write((const uint8_t*)b64Out, b64OutLen);
    b64OutLen = 0;
  }
  memcpy(b64Out + b64OutLen, g, 4);
  b64OutLen += 4;
}

template <typename ClientT>
void b64OutFlush(ClientT& client) {
  if (b64OutLen) {
    client.write((const uint8_t*)b64Out, b64OutLen);
    b64OutLen = 0;
  }
}

template <typename ClientT>
void b64Write(ClientT& client, B64State& st, const uint8_t* data, size_t len) {
  uint8_t grp[3];
  size_t i = 0;
  while (true) {
    uint8_t n = st.ncarry;
    if (n > 0) { grp[0] = st.carry[0]; if (n > 1) grp[1] = st.carry[1]; }
    while (n < 3 && i < len) grp[n++] = data[i++];
    if (n == 0) break;
    if (n == 3) {
      const uint32_t v = ((uint32_t)grp[0] << 16) | ((uint32_t)grp[1] << 8) | grp[2];
      const char out[4] = {B64TAB[(v >> 18) & 63], B64TAB[(v >> 12) & 63], B64TAB[(v >> 6) & 63], B64TAB[v & 63]};
      b64OutPush(client, out);
      st.ncarry = 0;
      if (i >= len) break;
    } else {
      st.carry[0] = grp[0]; st.carry[1] = grp[1]; st.ncarry = n;
      break;
    }
  }
}

template <typename ClientT>
void b64Flush(ClientT& client, B64State& st) {
  if (st.ncarry) {
    uint32_t v = (uint32_t)st.carry[0] << 16;
    if (st.ncarry > 1) v |= (uint32_t)st.carry[1] << 8;
    const char out[4] = {B64TAB[(v >> 18) & 63], B64TAB[(v >> 12) & 63], st.ncarry > 1 ? B64TAB[(v >> 6) & 63] : '=', '='};
    b64OutPush(client, out);
    st.ncarry = 0;
  }
  b64OutFlush(client);
}

void makeWavHeader(uint8_t h[44], uint32_t dataLen) {
  memcpy(h, "RIFF", 4);
  uint32_t v = 36 + dataLen; memcpy(h + 4, &v, 4);
  memcpy(h + 8, "WAVE", 4);
  memcpy(h + 12, "fmt ", 4);
  v = 16; memcpy(h + 16, &v, 4);
  h[20] = 1; h[21] = 0;
  h[22] = 1; h[23] = 0;
  v = PET_SAMPLE_RATE; memcpy(h + 24, &v, 4);
  v = PET_SAMPLE_RATE * 2; memcpy(h + 28, &v, 4);
  h[32] = 2; h[33] = 0;
  h[34] = 16; h[35] = 0;
  memcpy(h + 36, "data", 4);
  v = dataLen; memcpy(h + 40, &v, 4);
}

template <typename ClientT>
bool readHttpBody(ClientT& client, String& body, uint32_t maxWaitMs, const char* label) {
  String payload;
  const unsigned long start = millis();
  size_t lastLen = 0;
  unsigned long lastGrowth = millis();
  while ((client.connected() || client.available()) && payload.length() < 16000) {
    while (client.available()) payload += (char)client.read();
    if (payload.length() != lastLen) { lastLen = payload.length(); lastGrowth = millis(); }
    if (payload.length() > 0 && millis() - lastGrowth > 3000) break;  // 3s 无新数据即收工
    if (millis() - start > maxWaitMs) break;
    delay(5);
  }
  client.stop();
  if (payload.length() && payload.indexOf("\r\n\r\n") < 0) {
    Serial.print("V: http raw=");
    Serial.println(payload.substring(0, 170));  // 不完整响应:原样打印排查
  }
  Serial.print("V: http[");
  Serial.print(label);
  Serial.print("] wait=");
  Serial.print(millis() - start);
  Serial.print("ms len=");
  Serial.println(payload.length());
  const int headerEnd = payload.indexOf("\r\n\r\n");
  if (headerEnd < 0) return false;
  if (!payload.startsWith("HTTP/1.1 200") && !payload.startsWith("HTTP/1.0 200")) return false;
  body = payload.substring(headerEnd + 4);
  if (payload.indexOf("chunked") >= 0) {
    String decoded;
    int pos = 0;
    while (pos < (int)body.length()) {
      const int lineEnd = body.indexOf("\r\n", pos);
      if (lineEnd < 0) break;
      const int chunkLen = (int)strtol(body.substring(pos, lineEnd).c_str(), NULL, 16);
      if (chunkLen == 0) break;
      decoded += body.substring(lineEnd + 2, lineEnd + 2 + chunkLen);
      pos = lineEnd + 2 + chunkLen + 2;
    }
    body = decoded;
  }
  return true;
}

bool wifiPetConnected() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.print("V: wifi begin ssid=\"");
  Serial.print(WIFI_SSID);
  Serial.println("\"");
  for (int attempt = 1; attempt <= 3; attempt++) {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    const unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
      if (millis() - start > 15000) break;
      delay(500);
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("V: wifi OK ip=");
      Serial.println(WiFi.localIP());
      return true;
    }
    WiFi.disconnect();
    delay(1500);
  }
  return false;
}

String baiduToken = "";

bool fetchBaiduToken() {
  if (baiduToken.length() > 10) return true;
  WiFiClientSecure client;
  if (!client.connect("openapi.baidu.com", 443, 12000)) return false;
  const String req = String("GET /oauth/2.0/token?grant_type=client_credentials&client_id=") +
                     BAIDU_API_KEY + "&client_secret=" + BAIDU_SECRET_KEY +
                     " HTTP/1.1\r\nHost: openapi.baidu.com\r\nConnection: close\r\n\r\n";
  client.print(req);
  String body;
  if (!readHttpBody(client, body, 30000, "token")) return false;
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;
  baiduToken = String(doc["access_token"] | "");
  return baiduToken.length() > 10;
}

// 识别 + 回答(阻塞,数秒):成功 true;transcript/reply/note 填充
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, String& note) {
  transcript = "";
  reply = "";
  note = "";

  if (!wifiPetConnected()) {
    note = "wifi failed";
    return false;
  }
  if (!fetchBaiduToken()) {
    note = "baidu token failed";
    return false;
  }

  // ASR 走 HTTP 明文(80 端口):板载 TLS 写入只有 ~5KB/s,上传大音频会被服务器掐线;
  // 明文 TCP 快数倍。令牌仍走 HTTPS,音频本身在家庭网络内明文传输(玩具可接受)。
  WiFiClient client;
  if (!client.connect("vop.baidu.com", 80, 15000)) {
    note = "asr connect failed";
    return false;
  }

  // 静音裁剪:去掉首尾低于阈值的段,只留有效语音(+100ms 余量)
  uint32_t lo = 0, hi = samples;
  while (lo < hi && abs(petPcm[lo]) < 400) lo++;
  while (hi > lo + 1600 && abs(petPcm[hi - 1]) < 400) hi--;
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  const uint32_t wavLen = 44 + 2 * n;
  const uint32_t b64Len = ((wavLen + 2) / 3) * 4;
  const String head = String("{\"format\":\"wav\",\"rate\":16000,\"dev_pid\":1537,") +
                      "\"channel\":1,\"cuid\":\"wioterminal001\",\"token\":\"" + baiduToken +
                      "\",\"len\":" + String(wavLen) + ",\"speech\":\"";
  const char* tail = "\"}";
  String req = "POST /server_api HTTP/1.1\r\n"
               "Host: vop.baidu.com\r\n"
               "Content-Type: application/json\r\n"
               "Connection: close\r\nContent-Length: ";
  req += String(head.length() + b64Len + strlen(tail));
  req += "\r\n\r\n";
  client.print(req);
  client.print(head);
  B64State st = {{0, 0}, 0};
  const uint32_t upT = millis();
  // WAV 头 + int16 小端 PCM,必须 flush,否则实际字节数少于 Content-Length,服务器会一直等
  uint8_t wavHead[44];
  makeWavHeader(wavHead, 2 * n);
  b64Write(client, st, wavHead, 44);
  b64Write(client, st, (const uint8_t*)(petPcm + lo), 2 * n);
  b64Flush(client, st);
  client.print(tail);
  Serial.print("V: wav uploaded ms=");
  Serial.println(millis() - upT);

  String asrBody;
  if (!readHttpBody(client, asrBody, 60000, "asr")) {
    note = "asr http error";
    return false;
  }
  JsonDocument adoc;
  if (deserializeJson(adoc, asrBody)) {
    note = "asr bad json";
    return false;
  }
  const int errNo = adoc["err_no"] | -1;
  transcript = String(adoc["result"][0] | "");
  Serial.print("V: baidu err_no=");
  Serial.print(errNo);
  Serial.print(" transcript=");
  Serial.println(transcript);
  if (errNo != 0 || !transcript.length()) {
    note = "asr rejected";
    return false;
  }

  if (strlen(DEEPSEEK_KEY) < 5) {
    return true;  // 只识别,无回答
  }

  WiFiClientSecure client2;
  if (!client2.connect("api.deepseek.com", 443, 20000)) {
    note = "llm connect failed";
    return false;
  }
  JsonDocument req2;
  req2["model"] = "deepseek-chat";
  JsonArray msgs = req2["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] =
      "你是电子桌宠\"小维\",说话风格:活泼、简短、口语化。"
      "用简体中文回答用户(45字以内),直接输出回答,不要任何前缀或解释。";
  JsonObject user = msgs.add<JsonObject>();
  user["role"] = "user";
  user["content"] = transcript;
  req2["max_tokens"] = 300;

  String body2;
  serializeJson(req2, body2);
  String req2s = "POST /v1/chat/completions HTTP/1.1\r\n"
                 "Host: api.deepseek.com\r\n"
                 "Authorization: Bearer " DEEPSEEK_KEY "\r\n"
                 "Content-Type: application/json\r\n"
                 "Connection: close\r\nContent-Length: ";
  req2s += String(body2.length());
  req2s += "\r\n\r\n";
  req2s += body2;
  client2.print(req2s);

  String llmBody;
  if (!readHttpBody(client2, llmBody, 30000, "llm")) {
    note = "llm http error";
    return false;
  }
  JsonDocument ldoc;
  if (deserializeJson(ldoc, llmBody)) {
    note = "llm bad json";
    return false;
  }
  reply = String(ldoc["choices"][0]["message"]["content"] | "");
  Serial.print("V: reply=");
  Serial.println(reply);
  if (!reply.length()) {
    note = "llm empty reply";
    return false;
  }
  return true;
}

#endif  // PET_HAS_WIFI

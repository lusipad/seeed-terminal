// ---- AI 桌宠语音链路 ----
// 识别百度,回答 DeepSeek,结果引用返回;录音在 WioKitMic(L1),经 wioRecBuffer 零拷贝取用。

#include <Arduino.h>
#ifndef PET_TEST_OFFLINE
#define PET_TEST_OFFLINE 0   // 1 = 开机预连直接失败(测试离线开机)
#endif
#ifndef PET_TEST_BAD_TOKEN
#define PET_TEST_BAD_TOKEN 0 // 1 = 预连后把 token 改坏(测试失效自动重取)
#endif
#if __has_include("wifi_secrets.h")
#define PET_HAS_WIFI 1
#include <rpcWiFi.h>
#include <rpcWiFiClientSecure.h>
#include <ArduinoJson.h>
#include <WioKitLogic.h>
#include "wifi_secrets.h"
#else
#define PET_HAS_WIFI 0
#endif

#if PET_HAS_WIFI

#include <WioKitMic.h>
#include <WioKitNet.h>  // WiFi/HTTP/b64(L1);等待循环经 wioNetYield 回调 petAnimTick

const uint32_t PET_SAMPLE_RATE = 16000;

// 每轮对话各阶段耗时(ms);pet.ino 在每轮结束调用 petPrintTiming 打印 "T:" 行
struct PetTiming { uint32_t net, upload, asr, llmConn, llm; };
PetTiming petTm = {0, 0, 0, 0, 0};

void petPrintTiming(uint32_t processMs) {
  Serial.print("T: trail=");
  Serial.print(PET_TRAILING_MS);
  Serial.print(" net=");
  Serial.print(petTm.net);
  Serial.print(" upload=");
  Serial.print(petTm.upload);
  Serial.print(" asr=");
  Serial.print(petTm.asr);
  Serial.print(" llm_conn=");
  Serial.print(petTm.llmConn);
  Serial.print(" llm=");
  Serial.print(petTm.llm);
  Serial.print(" total=");
  Serial.println(PET_TRAILING_MS + processMs);
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
  if (!wioReadHttp(client, body, 30000, "token")) return false;
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;
  baiduToken = String(doc["access_token"] | "");
  return baiduToken.length() > 10;
}

// 开机预连:WiFi(只试 1 次,≤15s)+ 百度 token。失败不阻止开机:离线照常做宠物,按 B 时再连
void petNetWarmup() {
  const uint32_t t0 = millis();
#if PET_TEST_OFFLINE
  const bool ok = false;  // 测试:模拟开机时无网
#else
  const bool ok = wioNetConnected(1) && fetchBaiduToken();
#endif
  Serial.print("V: warmup ");
  Serial.print(ok ? "ok" : "failed");
  Serial.print(" ms=");
  Serial.println(millis() - t0);
}

const char* const PET_SYSTEM_PROMPT =
    "你是电子桌宠\"小维\",性格活泼元气,说话简短、口语化、爱用感叹号。"
    "回答必须以情绪标签开头,格式如 [开心],情绪只能从 开心/兴奋/惊讶/害羞/疑惑/难过 里选一个;"
    "标签后直接是回答正文,用简体中文,45字以内,不要任何其他前缀或解释。";

// 上传一次识别请求。返回百度 err_no;传输层失败返回 -1(note 填原因);响应缺 err_no 返回 -2
int baiduAsrOnce(uint32_t lo, uint32_t n, String& transcript, String& note) {
  // ASR 走 HTTP 明文(80 端口):板载 TLS 写入只有 ~5KB/s,上传大音频会被服务器掐线;
  // 明文 TCP 快数倍。令牌仍走 HTTPS,音频本身在家庭网络内明文传输(玩具可接受)。
  WiFiClient client;
  if (!client.connect("vop.baidu.com", 80, 15000)) {
    note = "asr connect failed";
    return -1;
  }
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
  B64Stream<WiFiClient> b64(client);
  const uint32_t upT = millis();
  // WAV 头 + int16 小端 PCM,必须 flush,否则实际字节数少于 Content-Length,服务器会一直等
  uint8_t wavHead[44];
  wioMakeWavHeader(wavHead, 2 * n, PET_SAMPLE_RATE);
  b64.write(wavHead, 44);
  b64.write((const uint8_t*)(wioRecBuffer() + lo), 2 * n);
  b64.flush();
  client.print(tail);
  petTm.upload = millis() - upT;
  Serial.print("V: wav uploaded ms=");
  Serial.println(petTm.upload);

  String asrBody;
  const uint32_t tAsr = millis();
  const bool ok = wioReadHttp(client, asrBody, 60000, "asr");
  petTm.asr = millis() - tAsr;
  if (!ok) {
    note = "asr http error";
    return -1;
  }
  JsonDocument adoc;
  if (deserializeJson(adoc, asrBody)) {
    note = "asr bad json";
    return -1;
  }
  const int errNo = adoc["err_no"] | -2;
  transcript = String(adoc["result"][0] | "");
  Serial.print("V: baidu err_no=");
  Serial.print(errNo);
  Serial.print(" transcript=");
  Serial.println(transcript);
  return errNo;
}

// 问 DeepSeek,reply 为回答原文
bool petAskLlm(const String& question, String& reply, int& emotion, String& note) {
  const uint32_t tConn = millis();
  WiFiClientSecure client2;
  if (!client2.connect("api.deepseek.com", 443, 20000)) {
    note = "llm connect failed";
    return false;
  }
  petTm.llmConn = millis() - tConn;
  const uint32_t tLlm = millis();
  JsonDocument req2;
  req2["model"] = "deepseek-chat";
  JsonArray msgs = req2["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = PET_SYSTEM_PROMPT;
  JsonObject user = msgs.add<JsonObject>();
  user["role"] = "user";
  user["content"] = question;
  req2["max_tokens"] = 120;  // 回答 45 字以内,够用且限制最坏耗时

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
  const bool ok = wioReadHttp(client2, llmBody, 30000, "llm");
  petTm.llm = millis() - tLlm;
  if (!ok) {
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
  size_t textStart = 0;
  emotion = parseEmotionTag(reply.c_str(), reply.length(), &textStart);
  reply = reply.substring(textStart);  // 标签不上屏
  if (!reply.length()) {  // 空回复,或只给了标签没有正文
    note = "llm empty reply";
    return false;
  }
  return true;
}

// 识别 + 回答(阻塞,数秒):成功 true;transcript/reply/note 填充
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, int& emotion, String& note) {
  transcript = "";
  reply = "";
  note = "";
  emotion = EMO_HAPPY;
  petTm = {0, 0, 0, 0, 0};

  const uint32_t tNet = millis();
  if (!wioNetConnected()) {
    note = "wifi failed";
    return false;
  }
  if (!fetchBaiduToken()) {
    note = "baidu token failed";
    return false;
  }
  petTm.net = millis() - tNet;

  // 静音裁剪:去掉首尾低于阈值的段,只留有效语音(+100ms 余量)
  uint32_t lo = 0, hi = samples;
  wioRecTrim(lo, hi);
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  int errNo = baiduAsrOnce(lo, n, transcript, note);
  if (errNo == 110 || errNo == 111 || errNo == 3302) {  // token 失效/鉴权失败:重取一次再试
    Serial.print("V: token rejected err_no=");
    Serial.println(errNo);
    baiduToken = "";
    if (!fetchBaiduToken()) {
      note = "baidu token failed";
      return false;
    }
    errNo = baiduAsrOnce(lo, n, transcript, note);
  }
  if (errNo == -1) return false;
  if (errNo != 0 || !transcript.length()) {
    note = "asr rejected";
    return false;
  }

  if (strlen(DEEPSEEK_KEY) < 5) {
    return true;  // 只识别,无回答
  }
  return petAskLlm(transcript, reply, emotion, note);
}

#endif  // PET_HAS_WIFI

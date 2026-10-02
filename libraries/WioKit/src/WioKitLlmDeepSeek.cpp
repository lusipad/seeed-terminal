#include "WioKitLlmDeepSeek.h"
#include <WioKitNet.h>
#include <WioKitTiming.h>
#include <rpcWiFi.h>
#include <rpcWiFiClientSecure.h>
#include <ArduinoJson.h>

static const char* llmKey = nullptr;
static const char* llmSystemPrompt = nullptr;

void wioLlmDeepSeekBegin(const char* key, const char* systemPrompt) {
  llmKey = key;
  llmSystemPrompt = systemPrompt;
}

bool wioLlmAsk(const String& question, String& reply, String& note) {
  reply = "";
  note = "";
  const uint32_t tConn = millis();
  WiFiClientSecure client;
  if (!client.connect("api.deepseek.com", 443, 20000)) {
    note = "llm connect failed";
    return false;
  }
  wioTiming().llmConn = millis() - tConn;
  const uint32_t tLlm = millis();
  JsonDocument req;
  req["model"] = "deepseek-chat";
  JsonArray msgs = req["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = llmSystemPrompt;
  JsonObject user = msgs.add<JsonObject>();
  user["role"] = "user";
  user["content"] = question;
  req["max_tokens"] = 120;  // 回答 45 字以内,够用且限制最坏耗时

  String body;
  serializeJson(req, body);
  String reqStr = "POST /v1/chat/completions HTTP/1.1\r\n"
                  "Host: api.deepseek.com\r\n"
                  "Authorization: Bearer ";
  reqStr += llmKey;
  reqStr += "\r\nContent-Type: application/json\r\n"
            "Connection: close\r\nContent-Length: ";
  reqStr += String(body.length());
  reqStr += "\r\n\r\n";
  reqStr += body;
  client.print(reqStr);

  String llmBody;
  const bool ok = wioReadHttp(client, llmBody, 30000, "llm");
  wioTiming().llm = millis() - tLlm;
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
  if (!reply.length()) {
    note = "llm empty reply";
    return false;
  }
  return true;
}

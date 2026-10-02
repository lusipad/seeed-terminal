// ---- L1 网络:WiFi 连接 + HTTP 收发 + base64 流式上传 + WAV 头(header-only 模板) ----
// 解耦点②:库的等待循环统一调用 wioNetYield();应用经 wioNetSetYield() 注册回调
// (如桌宠动画帧),不注册则等待期间什么都不做。函数指针而非虚函数:零开销、无堆分配。
// 判停语义:按 Content-Length / chunked 终止块收满立即返回;无长度信息退回
// "3 秒无新数据"兜底(RTL8720 栈在 Connection:close 后 connected() 不会及时变 false)。
#pragma once
#include <Arduino.h>
#include <rpcWiFi.h>
#include "WioKitLogic.h"

// 连接参数与回调经内联函数的函数级 static 保存:header-only 且跨编译单元单例(C++11)
struct WioNetState {
  const char* ssid;
  const char* pass;
  void (*yieldFn)();
};
inline WioNetState& wioNetState() {
  static WioNetState s = {nullptr, nullptr, nullptr};
  return s;
}

// 应用在 setup() 调用:注入密钥(解耦点③:库永不含密钥,secrets 头由应用 include)
inline void wioNetBegin(const char* ssid, const char* pass) {
  wioNetState().ssid = ssid;
  wioNetState().pass = pass;
}

// 注册等待期回调(如 petAnimTick);不注册则等待期间什么都不做
inline void wioNetSetYield(void (*fn)()) { wioNetState().yieldFn = fn; }

inline void wioNetYield() {
  if (wioNetState().yieldFn) wioNetState().yieldFn();
}

// 连 WiFi(默认试 3 次,每次 ≤15s);已连上立即返回 true
inline bool wioNetConnected(int attempts = 3) {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.print("V: wifi begin ssid=\"");
  Serial.print(wioNetState().ssid);
  Serial.println("\"");
  for (int attempt = 1; attempt <= attempts; attempt++) {
    WiFi.begin(wioNetState().ssid, wioNetState().pass);
    const unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
      if (millis() - start > 15000) break;
      for (int k = 0; k < 50; k++) {  // 等 500ms,期间应用回调照常
        wioNetYield();
        delay(10);
      }
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

static const char WIO_B64TAB[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
struct B64State { uint8_t carry[2]; uint8_t ncarry; };

// 流式 base64 编码:内部 1KB 批量写出,每写出一批让 wioNetYield() 走一帧。
// 用法:B64Stream<WiFiClient> s(client); s.write(wavHead, 44); s.write(pcm, n); s.flush();
template <typename ClientT>
struct B64Stream {
  ClientT* client;
  B64State st;
  char out[1024];
  size_t outLen;

  explicit B64Stream(ClientT& c) : client(&c), st{{0, 0}, 0}, outLen(0) {}

  void push(const char* g) {
    if (outLen + 4 > sizeof(out)) {
      client->write((const uint8_t*)out, outLen);
      outLen = 0;
      wioNetYield();  // 每写出 1KB 让应用回调走一帧
    }
    memcpy(out + outLen, g, 4);
    outLen += 4;
  }

  void write(const uint8_t* data, size_t len) {
    uint8_t grp[3];
    size_t i = 0;
    while (true) {
      uint8_t n = st.ncarry;
      if (n > 0) { grp[0] = st.carry[0]; if (n > 1) grp[1] = st.carry[1]; }
      while (n < 3 && i < len) grp[n++] = data[i++];
      if (n == 0) break;
      if (n == 3) {
        const uint32_t v = ((uint32_t)grp[0] << 16) | ((uint32_t)grp[1] << 8) | grp[2];
        const char g[4] = {WIO_B64TAB[(v >> 18) & 63], WIO_B64TAB[(v >> 12) & 63], WIO_B64TAB[(v >> 6) & 63], WIO_B64TAB[v & 63]};
        push(g);
        st.ncarry = 0;
        if (i >= len) break;
      } else {
        st.carry[0] = grp[0]; st.carry[1] = grp[1]; st.ncarry = n;
        break;
      }
    }
  }

  void flush() {
    if (st.ncarry) {
      uint32_t v = (uint32_t)st.carry[0] << 16;
      if (st.ncarry > 1) v |= (uint32_t)st.carry[1] << 8;
      const char g[4] = {WIO_B64TAB[(v >> 18) & 63], WIO_B64TAB[(v >> 12) & 63], st.ncarry > 1 ? WIO_B64TAB[(v >> 6) & 63] : '=', '='};
      push(g);
      st.ncarry = 0;
    }
    if (outLen) {
      client->write((const uint8_t*)out, outLen);
      outLen = 0;
    }
  }
};

// 16bit 单声道 PCM 的 WAV 头(44 字节)
inline void wioMakeWavHeader(uint8_t h[44], uint32_t dataLen, uint32_t sampleRate) {
  memcpy(h, "RIFF", 4);
  uint32_t v = 36 + dataLen; memcpy(h + 4, &v, 4);
  memcpy(h + 8, "WAVE", 4);
  memcpy(h + 12, "fmt ", 4);
  v = 16; memcpy(h + 16, &v, 4);
  h[20] = 1; h[21] = 0;
  h[22] = 1; h[23] = 0;
  v = sampleRate; memcpy(h + 24, &v, 4);
  v = sampleRate * 2; memcpy(h + 28, &v, 4);
  h[32] = 2; h[33] = 0;
  h[34] = 16; h[35] = 0;
  memcpy(h + 36, "data", 4);
  v = dataLen; memcpy(h + 40, &v, 4);
}

// 读一个 HTTP 响应:按 Content-Length / chunked 终止块判断收完立即返回;
// 无长度信息或异常时退回"3 秒无新数据即收工"兜底。成功(200 且头完整)返回 true,body 为解码后的正文。
template <typename ClientT>
bool wioReadHttp(ClientT& client, String& body, uint32_t maxWaitMs, const char* label, bool keepOpen = false) {
  String payload;
  const unsigned long start = millis();
  size_t lastLen = 0;
  unsigned long lastGrowth = millis();
  int hs = HTTP_NEED_MORE;
  while ((client.connected() || client.available()) && payload.length() < 16000) {
    bool got = false;
    while (client.available()) {
      payload += (char)client.read();
      got = true;
    }
    if (got) {
      hs = httpResponseState(payload.c_str(), payload.length());
      if (hs == HTTP_DONE) break;  // 按协议收满,立即收工
    }
    if (payload.length() != lastLen) {
      lastLen = payload.length();
      lastGrowth = millis();
    }
    if (payload.length() > 0 && millis() - lastGrowth > 3000) break;  // 兜底
    if (millis() - start > maxWaitMs) break;
    wioNetYield();
    delay(5);
  }
  if (!keepOpen || hs != HTTP_DONE) client.stop();
  const long headerEnd = httpHeaderEnd(payload.c_str(), payload.length());
  if (payload.length() && headerEnd < 0) {
    Serial.print("V: http raw=");
    Serial.println(payload.substring(0, 170));  // 不完整响应:原样打印排查
  }
  Serial.print("V: http[");
  Serial.print(label);
  Serial.print("] wait=");
  Serial.print(millis() - start);
  Serial.print("ms len=");
  Serial.print(payload.length());
  Serial.print(" done=");
  Serial.println(hs);
  if (headerEnd < 0) return false;
  if (!payload.startsWith("HTTP/1.1 200") && !payload.startsWith("HTTP/1.0 200")) return false;
  body = payload.substring(headerEnd + 4);
  if (httpIsChunked(payload.c_str(), (size_t)headerEnd)) {
    size_t decoded = 0;
    if (!body.length() || !chunkedWalk(body.begin(), body.length(), body.begin(), &decoded)) return false;
    body.remove(decoded);
  }
  return true;
}

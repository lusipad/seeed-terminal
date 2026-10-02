// ---- 各模块公共计时账本 ----
// 库的 L1/L2 模块向这里记账,应用在每轮对话结束时打印;字段与 pet 原有
// "T:" 行一一对应,格式不变,保证性能基线可对比。
#pragma once
#include <stdint.h>

// 每轮语音对话各阶段耗时(ms):
// net = 连 WiFi + 取百度令牌;upload = 音频上传;asr = 识别响应等待;
// llmConn = DeepSeek TLS 握手;llm = DeepSeek 请求发出到响应收完
struct WioKitTiming {
  uint32_t net;
  uint32_t upload;
  uint32_t asr;
  uint32_t llmConn;
  uint32_t llm;
};

// header-only 跨编译单元单例:库内模块与 sketch 看到同一份
inline WioKitTiming& wioTiming() {
  static WioKitTiming t = {0, 0, 0, 0, 0};
  return t;
}

inline void wioTimingReset() { wioTiming() = {0, 0, 0, 0, 0}; }

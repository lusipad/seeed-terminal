// ---- L2 DeepSeek chat 客户端 ----
// 换厂商 = 加新文件,不动 L0/L1(分层原则)。
// 回答原文返回(可含情绪标签);标签解析属于应用人设,应用自行调 L0 的 parseEmotionTag。
#pragma once
#include <Arduino.h>

struct WioLlmMsg {
  String role;     // "user" or "assistant"
  String content;  // 消息正文
};

void wioLlmDeepSeekBegin(const char* key, const char* systemPrompt);

// 问答一次。可传入多轮对话历史上下文(history)。
// historyCount 为历史消息条数(例如最近 1~2 轮对答共 2~4 条消息)。
// 成功 true 且 reply 为回答原文(未剥标签);
// 失败 false,note 为技术原因:llm connect failed / llm http error / llm bad json
bool wioLlmAskWithHistory(const WioLlmMsg* history, size_t historyCount, const String& question, String& reply, String& note);

// 单轮便捷接口(兼容旧调用)
inline bool wioLlmAsk(const String& question, String& reply, String& note) {
  return wioLlmAskWithHistory(nullptr, 0, question, reply, note);
}

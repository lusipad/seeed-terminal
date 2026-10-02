// ---- L2 DeepSeek chat 客户端 ----
// 换厂商 = 加新文件,不动 L0/L1(分层原则)。
// 回答原文返回(可含情绪标签);标签解析属于应用人设,应用自行调 L0 的 parseEmotionTag。
#pragma once
#include <Arduino.h>

void wioLlmDeepSeekBegin(const char* key, const char* systemPrompt);

// 问答一次。成功 true 且 reply 为回答原文(未剥标签);
// 失败 false,note 为技术原因:llm connect failed / llm http error / llm bad json
bool wioLlmAsk(const String& question, String& reply, String& note);

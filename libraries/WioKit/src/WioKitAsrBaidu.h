// ---- L2 百度语音识别:token 缓存/失效自动重取,WAV 封装,明文 80 端口上传 ----
// 换厂商 = 加新文件,不动 L0/L1(分层原则)。情绪标签解析不在本模块:
// 标签约定属于应用人设,应用拿 reply 自行调 L0 的 parseEmotionTag。
#pragma once
#include <Arduino.h>

void wioAsrBaiduBegin(const char* apiKey, const char* secretKey);

// 预取 token(开机调;失败不阻塞,真用时再取)
bool wioAsrBaiduWarmup();

// 识别一段 16kHz 16bit 单声道 PCM(如 wioRecBuffer() + wioRecTrim 得到的区间)。
// 成功返回 true 且 transcript 为识别文字;
// 失败返回 false,note 为技术原因:wifi failed / baidu token failed /
// asr connect failed / asr http error / asr bad json / asr rejected
bool wioAsrBaidu(const int16_t* pcm, uint32_t n, String& transcript, String& note);

// 测试钩子:注入坏 token 验证失效自动重取(110/111/3302),正常应用不用
void wioAsrBaiduDebugToken(const char* token);

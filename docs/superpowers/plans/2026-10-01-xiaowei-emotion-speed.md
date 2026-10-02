# 开发记事:小维 v2 —— 情绪性格 + 响应提速(2026-10-01)

> 本文是当日实施计划的精简版(原文 ~2500 行,含逐任务代码与操作步骤,见本文件的
> git 历史版本)。只留结论、决策与踩坑;对应提交列在文末。

## 目标与手段

让桌宠「小维」有情绪性格,并把"说完 → 回答上屏"的中位耗时比基线缩短 ≥5 秒。提速五招:

- **S1 按协议收工**:按 Content-Length / chunked 终止块判停,替代"3 秒无新数据"兜底
- **S2 开机预连**:boot 时预连 WiFi + 预取百度 token;token 失效(110/111/3302)自动重取一次
- **S3 缩短静音截断**:说完判定从 1300ms 收紧到 900ms
- **S4 限长**:DeepSeek `max_tokens=120`(回答 45 字以内,限制最坏耗时)
- **S5 TLS 连接复用**:条件任务,llm_conn 中位 ≤1500ms 则不做

验收口径:10 轮对话成功率不降,且成功轮中位 total 至少少 5000ms。计时数据见
[docs/perf-log.md](../../perf-log.md)。

## 设计决策(沿用至今)

- 纯逻辑(HTTP 判停/chunked 解码/情绪标签/光线动作探测器)放**无 Arduino 依赖的头文件**,
  由板上自检 sketch 做单元测试(`SELFTEST PASS 51/51`)——这层后来成为 WioKit 的 L0
- 动画用非阻塞调度器按 millis() 推进,`loop()` 与网络等待循环都 tick,阻塞请求期间画面照动
  ——后演化为 WioKitNet 的 yield 回调解耦
- 表情一律几何绘制、局部重绘防闪烁;`fillScreen` 只允许出现在 `drawPet()`
- 情绪白名单:开心/兴奋/惊讶/害羞/疑惑/难过,缺失或非法一律回退"开心"
- 14 种表情枚举 + 待机小动作(眨眼/张望/哼歌/歪头);3 分钟犯困、5 分钟睡觉;摇晃晕 3s + 冷却 5s

## 踩坑

- **漏写 WAV 头 + 漏 b64 flush**:实发字节比 Content-Length 少 ~1KB,百度等满 60s 才响应。
  上传类请求"声明的长度"与"实发字节"必须严格一致
- RTL8720 栈在 `Connection: close` 后 `connected()` 不会及时变 false:按协议判停比按连接状态可靠
- 串口实时日志必须逐行落盘(PowerShell 重定向是块缓冲,会整段丢失)
- 光线传感器与麦克风共用 ADC1:不能用 `analogRead`(会杀 DMA),要临时切通道读后恢复

## 对应提交(节选,均含板级验证)

- `feat(pet): reliable serial logger, per-round timing, baseline`(计时基建 + 基线)
- `feat(pet): pure HTTP completeness + chunked decode logic with on-board selftest`
- `feat(pet): emotion tag parser with fullwidth/whitespace tolerance`
- `perf(pet): stop reading HTTP at protocol end, trailing 900ms, max_tokens 120`(S1/S3/S4)
- `perf(pet): warm up WiFi+token at boot, auto-refresh expired Baidu token`(S2)
- `feat(pet): 14 expressions, non-blocking animation scheduler, animate during network waits`
- `feat(pet): emotion-tagged replies drive expressions; friendly error text`
- `feat(pet): drowsy after 3min, sleep after 5min with dimmed backlight, wake on key`
- `feat(pet): light+IMU sense — sleep on dark, wake on shake/pickup`
- 2026-10-02:上述能力与语音/渲染链路整体迁入 `libraries/WioKit`,
  见 [WioKit 库化设计](../specs/2026-10-02-wiokit-library-design.md)

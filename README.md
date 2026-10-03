# 小维 XiaoWei · Wio Terminal AI 桌宠

> 给 Wio Terminal(SAMD51 + 2.4" 彩屏 + WiFi + 板载麦克风)装上性格:
> **按一下 B 说话,说完自动停 → 百度 ASR 识别 → DeepSeek 回答 → 汉字气泡 + 匹配的表情。**
> 它还会眨眼、张望、哼歌;被摇晃会晕,摸头会开心,没人理会打哈欠、睡着。

| 待机 | 聆听 | 对话 |
|------|------|------|
| ![待机](sim/out/01_idle.png) | ![聆听](sim/out/03_listen.png) | ![对话](sim/out/04_reply_1.png) |

> 上图为**宿主模拟器**渲染(`bash sim/build.sh`,Windows/MSVC):与固件同一份表情、动画、
> 汉字渲染代码(见 `sim/`),屏幕/按键/云端为仿真。欢迎补充实机照片/GIF 到 `docs/img/`。

## 玩法

| 动作 | 反应 |
|------|------|
| 按一下 B | 开始听,说完自动发送(0.9s 静音自动截断,最长 3s) |
| 摇杆左 / 右 | 摸头:开心 |
| 摇晃 | 晕 3 秒(蚊香眼),之后冷却 5 秒 |
| 拿起 | 从犯困里打起精神 |
| 3 分钟没人理 / 5 分钟 | 犯困(打哈欠)/ 睡觉(Zzz) |
| 任意按键 | 睡醒 |

回答以情绪标签(`[开心]` `[兴奋]` `[惊讶]` `[害羞]` `[疑惑]` `[难过]`)开头,由系统提示词约定、
DeepSeek 生成;标签驱动 14 种几何表情,正文以气泡上屏。录音为 16bit@16kHz DMA 采样 + 高通滤波,
上传前做首尾静音裁剪。

## 快速上手

硬件:Wio Terminal + USB-C 数据线 + WiFi(2.4G 信道 12/13 连不上,优先 5G,见 HANDOFF 踩坑史)。

1. 安装 [arduino-cli](https://arduino.github.io/arduino-cli/)、板卡包
   `Seeeduino:samd`(板卡源 `https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`)
   及依赖库:`Seeed_GFX2`、`Seeed Arduino rpcWiFi`、`ArduinoJson`、`Seeed Arduino Mic`、
   `Grove-3-Axis-Digital-Accelerometer-2g-to-16g-LIS3DHTR`
2. 配密钥:`cp pet/wifi_secrets.h.example pet/wifi_secrets.h`,填 WiFi、百度语音 Key、DeepSeek Key
   (该文件已被 gitignore;不填则得到一只"离线宠物"——动画表情照常,说话会提示没网)
3. 编译烧录(一键脚本,Windows/Git Bash,自动按 VID 找串口 + 挂串口日志;其他平台用下面的手动命令):

   ```bash
   bash tools/flash_and_log.sh pet 600
   ```

   ```bash
   arduino-cli compile --fqbn Seeeduino:samd:seeed_wio_terminal --libraries libraries pet
   arduino-cli upload  -p <PORT> --fqbn Seeeduino:samd:seeed_wio_terminal --libraries libraries
   ```

4. 按 B,跟它说句话。

## WioKit —— 它脚下的库

pet 的全部硬件能力沉淀在 [libraries/WioKit/](libraries/WioKit/)(标准 Arduino 库,
编译时 `--libraries libraries` 即可被任何 sketch 复用):

| 层 | 模块 | 内容 |
|----|------|------|
| L0 | `WioKitLogic.h` | 纯逻辑(无 Arduino 依赖):HTTP 判停 / chunked 解码 / 情绪标签 / 光线动作探测器,板上自检覆盖 |
| L1 | `WioKitCjk` | 中文渲染:UTF-8→GB2312→HZK16,行缓冲 + pushImage 批量推送 |
| L1 | `WioKitMic` | DMA 录音 + VAD 自动截断 + 静音裁剪(96KB PCM 零拷贝暴露) |
| L1 | `WioKitNet` | WiFi 连接 / HTTP 收发(预分配 HttpBuf)/ base64 流式上传 / 等待期 yield 回调 |
| L1 | `WioKitSense` | 光线(与麦克风共用 ADC1 的共享读法)+ LIS3DH 摇晃/拿起 |
| L2 | `WioKitAsrBaidu` | 百度 ASR:token 缓存与失效重取、WAV 封装、明文 80 端口上传 |
| L2 | `WioKitLlmDeepSeek` | DeepSeek chat 客户端 |

模块独立 include,不用的不进固件(纯渲染示例固件比 pet 小 40KB+)。独立示例:
`examples/CjkHello`(只画中文)、`examples/VoiceEcho`(录音→识别→回答全链路)。

## 其他项目

- **`console/` + `host/`** — 菜单版桌面控制台(PC 中转 / 板端语音助理 / 直连 DeepSeek 三种形态),
  动作经摇杆选择,串口协议对接 `host/wio_console.py`(配置见 `host/config.json.example`)
- **`diag/tlsdiag/`** — 板子到各 AI 端点的 TLS 可达性诊断,排查网络问题用
- **`sketches/HelloWio/`** — 点灯小品
- **`tests/pet_selftest/`** — WioKit L0 纯逻辑的板上自检(`bash tools/flash_and_log.sh tests/pet_selftest 60`)

## 文档

- [HANDOFF.md](HANDOFF.md) — 开发笔记:软件架构细节、踩坑史(9 条真金白银)、真机验收清单。
  写给下一个接手的人,多半是未来的自己
- [docs/superpowers/specs/](docs/superpowers/specs/) — 两份设计文档:情绪+提速、WioKit 库化
- [docs/superpowers/plans/](docs/superpowers/plans/) — 情绪+提速一轮改造的开发记事(原始过程日志见 git 历史)
- [docs/perf-log.md](docs/perf-log.md) — 语音链路计时基线

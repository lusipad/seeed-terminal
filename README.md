# 小维 XiaoWei · Wio Terminal AI 桌宠

> 给 Wio Terminal(SAMD51 + 2.4" 彩屏 + WiFi + 板载麦克风)装上性格:
> **按一下 B 说话,说完自动停 → 百度 ASR 识别 → DeepSeek 回答 → 汉字气泡 + 匹配的表情。**
> 它还会眨眼、张望、哼歌;被摇晃会晕,摸头会开心,没人理会打哈欠、睡着。

| 待机 | 开心摸头 | 聆听 | 对话展示 | 沉睡 |
| :---: | :---: | :---: | :---: | :---: |
| ![待机](sim/out/01_idle.png) | ![开心](sim/out/02_pet_happy.png) | ![聆听](sim/out/03_listen.png) | ![对话](sim/out/04_reply_1.png) | ![睡觉](sim/out/10_sleep.png) |

> 上图为**宿主模拟器**渲染(`bash sim/build.sh` 或 `sim/build.bat`, Windows/MSVC): 与固件运行完全同一份表情、动画、汉字渲染及像素场景代码。欢迎补充实机照片/GIF 到 `docs/img/`。

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
DeepSeek 生成;标签驱动 14 种高精度像素表情,正文以气泡上屏。画面采用复古像素小屋与小猫场景(256色索引色、局部差分切片刷新)。录音为 16bit@16kHz DMA 采样 + 高通滤波,
上传前做首尾静音裁剪。

## 像素美术与资源架构

- **概念图 100% 还原**: 320x240 复古像素小屋（星空窗口、绿植花盆、木质条纹地板、几何印花坐垫、底部状态框）。
- **14 种情绪像素面部**: 正常、眨眼、开心、兴奋、难过、听、想、惊、害羞、疑惑、犯困、沉睡、眩晕、打哈欠。
- **低内存高帧率架构**:
  - 256 色全局共享调色板 (512 字节 RGB565)
  - 320x240 字节索引背景图 (75.0 KB)
  - 14 个面部差分切片 (37.6 KB, 86x32)
  - **Flash 占用约 113 KB，RAM 堆零占用**（仅使用 640 字节栈上行缓冲，为麦克风 96KB DMA 缓冲区留足裕量）。
- **极速局部刷新**: 面部微表情切换只刷新 `86x32` 脏矩形，SPI 传输仅需 **~1.5ms**，完全零闪烁；气泡与装饰擦除根据索引数组指针按行恢复，无需整屏重绘。
- **资源管线**:
  - `art/src/concept_pixel_art.jpg` (原始概念艺术图)
  - `tools/build_pixel_pet.py` (眼窝深度净空与 14 种像素表情生成)
  - `tools/export_pet_assets.py` (复合调色板量化并导出 `pet/pet_scene_data.h`)

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

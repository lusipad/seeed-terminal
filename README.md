# seeed-terminal — Wio Terminal 折腾仓库

块子的"脸和按钮",大脑在云端。目前有四个项目:

| 目录 | 内容 | 状态 |
|------|------|------|
| `libraries/WioKit/` | **WioKit 基础功能库**(中文渲染/录音/网络/传感器/百度ASR/DeepSeek) | ✅ 已库化,pet 已迁入 |
| `sketches/HelloWio/` | 第一个测试程序:LED 闪烁 + 串口心跳 | ✅ 已验证 |
| `console/` + `host/` | **桌面 AI 控制台**(见下文) | ✅ 已烧录 |
| `diag/tlsdiag/` | TLS 连接诊断小品(排查板子到各端点的可达性) | ✅ 已验证 |

> 另有 `game-console/`(Seeed 官方游戏机)仅本地保留,不入库。

## WioKit 库(libraries/WioKit/)

从桌宠「小维」沉淀出的标准 Arduino 库,所有 sketch 共享一份源码(解决跨目录 include 断链):

- **L0** `WioKitLogic.h`:纯逻辑(HTTP 判停/chunked 解码/情绪标签/光线动作探测器),无 Arduino 依赖,`tests/pet_selftest` 板上自检
- **L1** `WioKitCjk`(中文渲染)、`WioKitMic`(DMA 录音+VAD)、`WioKitNet`(WiFi/HTTP/b64)、`WioKitSense`(光线+IMU),每模块独立 include,不用的不进固件
- **L2** `WioKitAsrBaidu`、`WioKitLlmDeepSeek`:云服务客户端,可选用;换厂商加新文件
- 示例:`examples/CjkHello`(只渲染)、`examples/VoiceEcho`(录音→识别→回答全链路)

```bash
# 编译任何使用库的 sketch 都要带 --libraries(或直接用一键脚本)
bash tools/flash_and_log.sh pet 600
bash tools/flash_and_log.sh tests/pet_selftest 60        # L0 板上自检
arduino-cli compile --fqbn Seeeduino:samd:seeed_wio_terminal --libraries libraries pet
```

Arduino IDE 用户:把 `libraries/WioKit/` 软链或拷贝到 sketchbook 的 `libraries/` 下即可。

## 桌面 AI 控制台(WioConsole)

摇杆选动作、按键触发、屏幕显示状态。三种使用形态:

- **PC 中转模式**:板子 → 串口 → PC 脚本 → DeepSeek API → 结果写回剪贴板 + 回传屏幕
- **语音助理模式(脱离 PC)**:板子直连小米 MiMo API —— 按住 B 说话 → 板载麦克风录音 → MiMo-V2.5-ASR 转文字 → MiMo-V2.6 大模型回答 → 屏幕
- **DeepSeek 直连**(菜单第 7 项):板子自己连 WiFi 调 DeepSeek

### 操作

| 按键 | 功能 |
|------|------|
| 摇杆上/下 | 选动作 |
| 摇杆按下 / 顶部 A | 执行 |
| 顶部 B | 测试 PC 链路;语音模式下按住=录音,松开=发送 |
| 顶部 C | 返回菜单 |

动作清单:1 Translate(翻译剪贴板)、2 Summarize(总结)、3 Commit Msg、4 Inspire(毒鸡汤)、5 Hello Test(PC 链路自检,不需 Key)、**6 Voice Ask(语音问答,脱离 PC)**、7 DeepSeek Cloud。

### 首次使用

1. **PC 中转模式**
   ```bash
   cd host
   pip install -r requirements.txt
   # 编辑 config.json,把 DeepSeek 的 Key 填进 api_key(或设环境变量 DEEPSEEK_API_KEY)
   python wio_console.py
   ```
   连上后板子会自动跑一次 Hello 自检;屏幕左下角 `PC: linked` 表示链路正常。
2. **语音助理 / 直连模式**:编辑 `console/wifi_secrets.h`,填入 WiFi 名称/密码和 MiMo Key(`sk-xxx`),然后重新编译烧录(见下)。
   - 验证 MiMo Key/接口:`python host/test_mimo.py`(大模型对话 + ASR 转写全链路自测)
   - 语音助手依赖 MiMo 开放平台 API:https://platform.xiaomimimo.com

### 改代码后重新烧录

```bash
bash tools/flash_and_log.sh console 600   # 一键:编译+烧录+挂日志(自动找口)
# 或手动(注意 --libraries):
arduino-cli compile --fqbn Seeeduino:samd:seeed_wio_terminal --libraries libraries --build-path build/console console
arduino-cli upload  -p COM3 --fqbn Seeeduino:samd:seeed_wio_terminal --build-path build/console
```

### 已知限制 / 后续路线

- 屏幕暂只能显示 ASCII。语音助手的桥接方案:让 LLM 在回复里附 `HEARD:`/`PY:` 两行无声调拼音,屏幕可读;中文上屏需 microSD 卡放字体 + FreeType 库(下一步)
- 板载麦克风 + 8bit 采样,录音最长 3 秒(RAM 限制);识别效果不佳时换 microSD 卡缓存 + 16bit
- 直连/语音模式未配置 CA 证书(跳过 TLS 证书校验),玩具用途可接受
- 待办:SD 中文字库上屏、HID 一键打字回 PC、提醒/每日简报、对话记忆

## 环境备忘

- arduino-cli:`C:\Program Files\Arduino CLI\arduino-cli.exe`(已进 PATH)
- 板卡:Seeeduino:samd 1.8.6,FQBN `Seeeduino:samd:seeed_wio_terminal`,串口 COM3
- 板卡源:`https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
- 已装库:Seeed_GFX2、Seeed Arduino rpcWiFi(+rpcUnified)、ArduinoJson

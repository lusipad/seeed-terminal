# HANDOFF — Wio Terminal AI 桌宠「小维」交接文档

> 更新:2026-10-01。给下一个接手的会话/工程师:先读"当前状态"和"下一步",避免重复踩坑。

## 一句话

Wio Terminal(SAMD51 + 2.4" 彩屏 + WiFi + 板载麦克风)改造成的**离线语音 AI 桌宠「小维」**:
按一下 B 说话 → 自动截断 → 百度 ASR 转文字 → DeepSeek 回答 → 屏幕以汉字气泡显示。
主产品是 `pet/`(桌宠),另有 `console/`(菜单版控制台)和 `game-console/`(官方游戏机)保留。

## 当前状态(2026-10-01 晚更新)✅

- **语音全链路已跑通**(用户实测:问天气 → 识别正确 → DeepSeek 回答“查不到实时天气”)
- 真正根因不在读取端:`petProcessVoice` 上传时**漏写 WAV 头 + 漏调 `b64Flush()`**,实发字节比 Content-Length 少 ~1KB,百度一直等 → 60s 零响应。已按 console 版 `streamWav16` 的写法修复
- 遗留小问题:本次测试串口日志只记到 `HELLO`,后续 `V:` 行没落盘(监听进程仍存活),原因未查

## 上一轮状态(已过时,留作记录)

- **刚烧录了"响应读取修复"版 pet 固件,用户尚未实测** —— 接手第一件事:
  1. 让用户测一次语音(按一下 B → 说话 → 自动停)
  2. 看日志:`bash tools/flash_and_log.sh none 300`(只听不烧),日志在 `C:\Users\lus\AppData\Local\Temp\wio_serial.log`
  3. 若仍失败,重点看日志里新增的 `V: http raw=...`(不完整响应的原样内容)——上一轮实测百度其实已返回 181 字节响应,但读循环没识别到"响应结束"就扔了,本版改为"3 秒无新数据即收工"+原样打印
- 已确认正常:WiFi(<REDACTED_SSID>, IP 192.168.0.124)、百度令牌获取(2.2s)、音频上传提速(明文 HTTP 2.7s vs TLS 19.7s)、中文汉字渲染
- 唯一未验证环节:**百度响应的读取与解析**(本轮修复的内容)

## 硬件与账号

- 板子:Wio Terminal,串口名会变(COM3/COM4 都出现过),**以 VID_2886 自动查找为准,不要写死**
- 板子底部有两个 USB-C:一个连主控(串口/烧录用这个),另一个是无线模块固件下载口(插上电脑认不出串口)
- WiFi:用户路由器双频,`<REDACTED_SSID>`(2.4G,**信道 12,板子连不上——区域码限制**)→ 用 5G 的 `<REDACTED_SSID>`(信道 44)
- 密钥位置(均已 gitignore,**不要提交、不要外发**):
  - `pet/wifi_secrets.h` / `console/wifi_secrets.h`:WiFi + 百度 ASR(API Key/Secret)+ DeepSeek Key(已实测有效)
  - `host/config.json`:PC 中转模式配置(当前指向 DeepSeek;可改小米 MiMo——PC 上 MiMo 可用,板子上不可用,见坑 1)

## 构建与调试

```bash
bash tools/flash_and_log.sh pet 600      # 编译+烧录 pet + 挂 600s 实时日志
bash tools/flash_and_log.sh none 300     # 只听日志不烧录
bash tools/flash_and_log.sh console 600  # 菜单版控制台
# 日志实时写:C:\Users\lus\AppData\Local\Temp\wio_serial.log(Add-Content 逐行落盘)
```

- arduino-cli 在 `C:\Program Files\Arduino CLI\`,FQBN `Seeeduino:samd:seeed_wio_terminal`,板卡源 `files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
- 串口独占是高频坑:**烧录/读日志前必须 kill 残留 PowerShell 监听**(脚本已内置)
- PowerShell 重定向输出会块缓冲,实时日志必须用 Add-Content 逐行写文件

## 软件架构(pet/)

- `pet.ino`:状态机 `IDLE → RECORD(轮询 VAD)→ THINK(阻塞识别+回答)→ SHOW(气泡)→ IDLE`
  - 待机动画只做**局部眨眼**(整屏重绘会闪烁,用户明确否决过)
  - 摇杆左右 = 摸头(开心表情)
- `voice_pet.h`:语音全链路
  - 麦克风:**必须用官方 Seeed Arduino Mic 库(DMA 16bit + FilterBuHp 高通)**;手搓 analogRead 8bit 方案有直流偏置灾难(silence 偏离中点 80),已废弃
  - VAD:轮询最近 1600 样本平均能量,静音 1.3s 自动截断;录音上限 3s(RAM 96KB int16)
  - 百度 ASR:token 缓存于 RAM;**识别请求走 HTTP 明文 80 端口**(板载 TLS 写 ~5KB/s,HTTPS 传 64KB+ 会被百度掐线);上传前做首尾静音裁剪
  - DeepSeek:`/v1/chat/completions`,HTTPS(DeepSeek 端点板子 TLS 握手 OK)
  - b64/HTTP 工具函数是模板(typename ClientT),同时服务 WiFiClient 和 WiFiClientSecure
- `cjk.h` + `font_hz16.h`/`font_index.h`:**中文渲染**。HZK16 16×16 点阵(区1-3 符号+全角标点、区16-55 一级汉字,共 4048 字形),UTF-8→GB2312 二分索引
  - 生成器:`tools/gen_font.py`(源字库 `tools/HZK16.bin`);**索引条目必须过滤非 3 字节 UTF-8 的字符**(区1 有 9 个 2 字节注音符号,曾撞歪整张表导致全是方块)
  - console/ 和 pet/ 各持一份拷贝(Arduino 会把 sketch 复制到临时目录编译,**跨目录 `../` 引用会断**,头文件间互相引用用本目录拷贝)
- `pet_face.h`:宠物几何外观(表情=眼睛/嘴变化)
- ⚠️ Arduino .ino 坑:函数原型会提升到文件顶,**自定义类型(enum/struct)不能出现在 .ino 函数签名里**(用 .h 承载,或 int 传参)

## 踩坑史(重要,别重蹈)

1. **小米 MiMo API 板子直连不可行**:MiMo 的 CDN 对板子无线固件的 TLS 1.2 握手静默丢弃(SNI/加密套件均排除,固件级无解)。已换百度+DeepSeek。MiMo Key 在 PC 中转模式下可用
2. **无线模块固件停更**:seeed-ambd-firmware 最终版 v2.1.3(2021-05)。旧固件会让 `WiFi.begin()` 永久卡死——用 `tools/ambd_flash_tool`(erase→flash)经 USB 刷新过(已刷最新)
3. **2.4G 信道 12/13**:板子扫得到但连不上(区域码),用 5G SSID 绕开
4. **百度 dev_pid**:15372 该账号不支持;**1537(普通话)实测可用**;音频必须 16bit 16kHz
5. **上传速度**:板载 TLS 写仅 ~5KB/s,大音频上传会被服务器掐线 → 明文 HTTP + 静音裁剪解决
6. **板载麦克风**:silence 时 ADC 偏离中点 80(直流偏置问题)→ 官方 DMA 库 + 高通滤波解决
7. 读 HTTP 响应:RTL8720 栈在 Connection:close 后 `connected()` 不会及时变 false → 用"数据停止增长 3 秒"判停

## 下一步路线(用户认可的优先级)

1. **验收响应读取修复**(见"当前状态")
2. 对话记忆:SQLite/文件存多轮上下文(板端只存最近 N 轮摘要,或 PC 端做)
3. 提醒功能:"三点提醒我开会" → 时间抽取 → 到点蜂鸣+气泡
4. 每日简报:天气 API + 待办推送
5. 表情丰富化:更多情绪映射(回答带情绪标签驱动表情)
6. 远期:SD 卡放 TTF + FreeType(更美的字体);HID 一键打字;游戏机模式共存入口

## 文件地图

```
pet/                 主产品:AI 桌宠(pet.ino 状态机, voice_pet.h 语音, cjk+font 中文, pet_face.h 外观)
console/             菜单版控制台(5 动作 + 语音Ask,串口协议接 host/)
game-console/        官方游戏机(原样保留, .ino 已改名 game-console.ino 并修复枚举名)
host/                PC 中转端(wio_console.py;test_mimo.py / test_baidu_asr.py 为接口自测脚本)
tools/               flash_and_log.sh(一键烧录+日志), gen_font.py(字体生成), HZK16.bin, ambd_flash_tool/
diag/tlsdiag/        TLS 连接诊断小品(上电自动测端点可达性,排查网络问题用)
README.md            用户向说明(略旧,以本文件为准)
```

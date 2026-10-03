# HANDOFF — Wio Terminal AI 桌宠「小维」交接文档

> 更新:2026-10-02。给下一个接手的会话/工程师:先读"当前状态"和"下一步",避免重复踩坑。

## 一句话

Wio Terminal(SAMD51 + 2.4" 彩屏 + WiFi + 板载麦克风)改造成的**离线语音 AI 桌宠「小维」**:
按一下 B 说话 → 自动截断 → 百度 ASR 转文字 → DeepSeek 回答 → 屏幕以汉字气泡显示。
主产品是 `pet/`(桌宠),公共能力已沉淀为标准 Arduino 库 `libraries/WioKit/`(2026-10-02 完成)。

## 当前状态(2026-10-04)✅ 视觉像素化重构完成 & 库化就绪

- **概念图 2 复古像素场景与小猫 100% 还原**:
  - 原几何色块简陋画风彻底替换为高质量 320x240 复古像素小屋（星空窗户、绿植、木地板、印花坐垫、底色状态栏）。
  - 小猫形象与 14 种情绪面部（86x32 切片：正常、眨眼、开心、兴奋、难过、听、想、惊讶、害羞、疑惑、犯困、沉睡、眩晕、哈欠）完美贴合概念图。
  - 架构：256 色全局共享调色板 + 字节索引场景底图 (75KB) + 14 个面部差分切片 (37.6KB)，总资源 113KB Flash，0 静态 RAM。
  - 性能：面部微小脏矩形局部刷新（SPI 事务 ~1.5ms 极速无闪烁）；气泡与装饰擦除直接根据索引图指针算行恢复，无需整屏重绘或全屏双缓冲。
  - 固件体积：Flash 430KB / 507KB (84%，余 77KB)，RAM 余量安全（麦克风 96KB DMA 缓冲不受影响）。
  - 宿主模拟器：`sim/build.bat` 全 12 帧场景跑通，`sim/out/*.png` 视觉验收通过。
- **WioKit 库已建成**, pet 迁移到库上, 语音全链路代码**编译与真机验证全部通过**
- **真机验收状态 (2026-10-04 实机通过)**:
  1. **L0 自检**: `sim/build.bat` 宿主 51 项测试全部 `SELFTEST PASS 51/51`。
  2. **pet 冒烟**: 自动烧录通过；开机序列 `V: mic init ok`、`S: imu ok`、`V: wifi OK`、`V: warmup ok ms=6334`；光线与 IMU 共享采样正常。
  3. **视觉与渲染**: 气泡框边缘严实闭合，无多余黑边残影，表情切换微秒级响应且 100% 还原概念图。
  4. **云端与模型**: 百度语音短语音转写与 DeepSeek 情绪对话链路调通。

## 硬件与账号

- 板子:Wio Terminal,串口名会变(COM3/COM4 都出现过),**以 VID_2886 自动查找为准,不要写死**
- 板子底部有两个 USB-C:一个连主控(串口/烧录用这个),另一个是无线模块固件下载口(插上电脑认不出串口)
- WiFi:用户路由器双频,`<路由器2.4G>`(2.4G,**信道 12,板子连不上——区域码限制**)→ 用 5G SSID(信道 44)
- 密钥位置(均已 gitignore,**不要提交、不要外发**):
  - `pet/wifi_secrets.h`:WiFi + 百度 ASR(API Key/Secret)+ DeepSeek Key(已实测有效)
  - `libraries/WioKit/examples/VoiceEcho/wifi_secrets.h`:示例用,拷 pet 的即可
  - `host/config.json`:PC 中转模式配置
- **库本身永不含密钥**:`wioNetBegin()/wioAsrBaiduBegin()/wioLlmDeepSeekBegin()` 参数注入,
  没有密钥时 pet/examples 也能编译出"离线宠物"(运行时提示没配网)

## 构建与调试

```bash
bash tools/flash_and_log.sh pet 600                     # 编译+烧录 pet + 挂 600s 实时日志
bash tools/flash_and_log.sh none 300                    # 只听日志不烧录
bash tools/flash_and_log.sh tests/pet_selftest 60       # L0 板上自检
bash tools/flash_and_log.sh console 600                 # 菜单版控制台
# 日志实时写:$TMPDIR/wio_serial.log(即 Windows 用户 Temp,逐行落盘)
```

- arduino-cli 在 `C:\Program Files\Arduino CLI\`,FQBN `Seeeduino:samd:seeed_wio_terminal`,
  板卡源 `files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
- **凡用到 WioKit 的 sketch,编译必须带 `--libraries libraries`**(flash_and_log.sh 已内置;
  手动命令照 README)。Arduino IDE 用户:把 `libraries/WioKit/` 软链/拷进 sketchbook libraries
- 串口独占是高频坑:**烧录/读日志前必须 kill 残留 PowerShell 监听**(脚本已内置)
- 体积参考(2026-10-02 编译):pet 316KB Flash / 169KB bss;selftest 65KB;
  CjkHello 274KB / bss 63.5KB(麦克风缓冲等未用模块确认被 --gc-sections 剔除)

## 软件架构

```
libraries/WioKit/            标准 Arduino 库(library.properties + src/ + examples/)
  src/WioKitLogic.h          L0 纯逻辑:HTTP 判停/chunked/情绪标签/光线动作探测器
                             (无 Arduino 依赖;唯一有自动化测试的层,tests/pet_selftest)
  src/WioKitCjk.h/.cpp       L1 中文渲染:UTF-8→GB2312→HZK16,行缓冲 + pushImage 批量推送
  src/WioKitFontHz16.h       字库数据(~150KB Flash;由 tools/gen_font.py 生成,勿手改)
  src/WioKitMic.h/.cpp       L1 录音:DMA 16bit 16kHz + 高通 + VAD 截断 + 静音裁剪
                             (96KB PCM 静态数组,wioRecBuffer() 零拷贝暴露)
  src/WioKitNet.h            L1 网络(header-only 模板):WiFi 连接/HTTP 收发/b64 流式/
                             WAV 头;HttpBuf 预分配收响应;等待循环走 wioNetYield()
  src/WioKitSense.h/.cpp     L1 传感器:光线(ADC1 共享读法,踩坑成果勿改 analogRead)+ LIS3DH
  src/WioKitAsrBaidu.h/.cpp  L2 百度 ASR:token 缓存/失效重取,WAV,明文 80 端口上传
  src/WioKitLlmDeepSeek.h/.cpp L2 DeepSeek chat
  src/WioKitTiming.h         计时账本(wioTiming(),"T:" 行数据源)
pet/                         应用层只剩:状态机、pet_face/pet_anim(表情动画)、
                             系统提示词、密钥(__has_include 门控)、语音编排 petProcessVoice()
sim/                         宿主模拟器(Windows/MSVC):真实 pet.ino/pet_face/pet_anim/WioKitCjk
                             编译成 PC 程序,屏幕出 PNG、按键脚本注入、云端走仿真桩。
                             bash sim/build.sh 跑场景 + L0 自检;README 首图即出自这里
console/                     不迁,拷贝保留原状
tests/pet_selftest/          L0 板上自检(直接 include 库头,不再有同步拷贝)
tools/gen_font.py            字体生成器 → 直接吐到 libraries/WioKit/src/WioKitFontHz16.h
```

**三个解耦点**(改代码时别绕回去):

1. display 注入:sketch 建 `Seeed_GFX display(...)` 后 `wioCjkBegin(display)`,库不引用全局
2. yield 回调:`wioNetSetYield(petAnimTick)`;库内等待统一 `wioNetYield()`(判空),
   网络层反向依赖应用动画的问题已根治
3. 密钥参数化:`wioNetBegin(WIFI_SSID, WIFI_PASS)` 等;`__has_include("wifi_secrets.h")`
   门控只在应用层(pet/examples)

**性能铁律**(验收状态):

- 热路径零堆分配 ✓ 录音回调/b64/HTTP 收发(HttpBuf 预分配)/字形渲染均无 malloc
- 零成本抽象 ✓ 模板+inline+函数指针,无虚函数;未用模块被 --gc-sections 剔除(CjkHello 已验证)
- 渲染批量化 ✓ drawPixel→行缓冲 pushImage(真机目测待确认,见验收清单 4)
- 时延不退化 ✗ 待真机 3 轮对比(见验收清单 3)

## 踩坑史(重要,别重蹈)

1. **小米 MiMo API 板子直连不可行**:MiMo 的 CDN 对板子无线固件的 TLS 1.2 握手静默丢弃(SNI/加密套件均排除,固件级无解)。已换百度+DeepSeek。MiMo Key 在 PC 中转模式下可用
2. **无线模块固件停更**:seeed-ambd-firmware 最终版 v2.1.3(2021-05)。旧固件会让 `WiFi.begin()` 永久卡死——用 `tools/ambd_flash_tool`(erase→flash)经 USB 刷新过(已刷最新)
3. **2.4G 信道 12/13**:板子扫得到但连不上(区域码),用 5G SSID 绕开
4. **百度 dev_pid**:15372 该账号不支持;**1537(普通话)实测可用**;音频必须 16bit 16kHz
5. **上传速度**:板载 TLS 写仅 ~5KB/s,大音频上传会被服务器掐线 → 明文 HTTP + 静音裁剪解决
6. **板载麦克风**:silence 时 ADC 偏离中点 80(直流偏置问题)→ 官方 DMA 库 + 高通滤波解决;
   光线传感器与麦克风共用 ADC1,**analogRead 会杀 DMA**,必须用 WioKitSense 里的共享读法
7. 读 HTTP 响应:RTL8720 栈在 Connection:close 后 `connected()` 不会及时变 false → 用"数据停止增长 3 秒"判停(现封装在 wioReadHttp)
8. **Arduino 跨目录 include 断链**:sketch 会被复制到临时目录编译,`../` 引用必断 → 共享代码进
   `libraries/WioKit/`,编译带 `--libraries libraries`(库文件不被复制,经 -I 直接引用)
9. **Arduino .ino 坑**:函数原型会提升到文件顶,自定义类型(enum/struct)不能出现在 .ino 函数
   签名里——库化后类型都在 .h 中,此坑自然规避,但 .ino 里新加函数仍要留意

## 远期路线(用户认可的优先级)

1. 真机验收(见清单)→ 留 `T:` 基线 A
2. 对话记忆:多轮上下文(板端最近 N 轮摘要,或 PC 端做)
3. 提醒功能:"三点提醒我开会" → 时间抽取 → 到点蜂鸣+气泡
4. 每日简报:天气 API + 待办推送
5. WioKit 后续:IMU/SD/蜂鸣器等新硬件封装按需进 L1;ASR/LLM 统一抽象接口(分层已留位)
6. 远期:SD 卡放 TTF + FreeType(更美的字体);HID 一键打字

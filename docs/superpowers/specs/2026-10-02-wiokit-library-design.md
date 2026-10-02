# WioKit — Wio Terminal 基础功能库设计

> 2026-10-02。目标:把 pet/(桌宠「小维」)沉淀的已验证能力抽成标准 Arduino 库,
> 在其上可快速开发/复刻各类 WIO 应用(桌宠、时钟、仪表盘等)。

## 背景与目标

仓库现状是"多个 sketch 各自为政":`pet/` 与 `console/` 间靠复制粘贴共享代码
(cjk.h / font_hz16.h / font_index.h 完全相同,voice.h 与 voice_pet.h 同源分叉),
根因是 Arduino 构建把 sketch 复制到临时目录编译,`../` 跨目录引用会断。

本设计用 **标准 Arduino 库格式** 根治:库文件不会被复制,编译器经 `-I` 直接引用,
`arduino-cli compile --libraries libraries` 即可让所有 sketch 共享一份源码。

### 已确认的决策

| 决策点 | 结论 |
|--------|------|
| 受众 | 先自用,结构按可发布标准留余地(library.properties + examples/) |
| 范围 | 第一版只抽已验证能力,不新增硬件封装(IMU/SD 等后续按需补) |
| 分层 | 底层通用能力(L0/L1)+ 云服务客户端(L2)都进库,L2 可选用 |
| 验证 | pet 迁移到库上作为首个验证应用;console/game-console 不动 |
| 物理形态 | 仓库内 `libraries/WioKit/`,编译加 `--libraries libraries` |
| 性能 | 时延、渲染流畅度、RAM/Flash 三个维度全部作为硬性设计约束 |

## 目录结构与分层

```
libraries/WioKit/
  library.properties        # 名称/版本/依赖(Seeed_GFX2, rpcWiFi, ArduinoJson, Seeed Mic, LIS3DHTR)
  src/
    # ── L0 纯逻辑层(无 Arduino 依赖,PC/板上均可测) ──
    WioKitLogic.h           # HTTP 判停/chunked 解码、情绪标签解析、光线/动作探测器(现 pet_logic.h)
    # ── L1 板级能力层(依赖硬件,模块间互不依赖,可单独 include) ──
    WioKitCjk.h/.cpp        # 中文渲染(UTF-8→GB2312→HZK16,混排折行)
    WioKitFontHz16.h        # 字库数据(现 font_hz16.h + font_index.h)
    WioKitMic.h/.cpp        # 麦克风 DMA 录音 + VAD 自动截断 + 静音裁剪
    WioKitNet.h             # WiFi 连接 + HTTP 收发 + base64 流式上传(模板,header-only)
    WioKitSense.h/.cpp      # 光线(ADC1 共享读法)+ IMU 轮询
    # ── L2 云服务层(绑定厂商,每家一个文件,用不用随应用) ──
    WioKitAsrBaidu.h/.cpp   # 百度 ASR(token 缓存/自动重取、WAV 头、明文 80 端口上传)
    WioKitLlmDeepSeek.h/.cpp# DeepSeek chat 客户端
  examples/
    CjkHello/               # 最小示例:屏幕画中文
    VoiceEcho/              # 录音→ASR→上屏(验证 L1+L2 链路)

pet/        # 迁移后只剩应用层:状态机、pet_face(表情)、pet_anim(动画)、系统提示词、密钥
console/    # 不动(其拷贝保留原状,不算新增债务)
tests/      # pet_selftest 直接 include 库头;删除 tools/sync_logic.sh 同步机制
```

**分层原则**:
- L0 一行 Arduino 代码都不依赖,是唯一有自动化测试(板上自检)的层,传统保持。
- L1 每模块独立可用:只想画中文就只 include WioKitCjk.h,不用的模块不进固件。
- L2 换厂商 = 加新文件,不动 L0/L1。

**刻意留在应用层的**(库提供机制,应用提供个性):pet_face.h(五官人设)、
pet_anim.h 的具体动画(眨眼/哼歌/张望)、状态机、系统提示词、密钥文件。

## 三个关键解耦点

### ① display 全局对象 → 显式注入

现 cjk.h 直接引用 sketch 的全局 `display` 变量。改为:

```cpp
Seeed_GFX display(Seeed_Product::Wio_Terminal);
wioCjkBegin(display);                              // setup() 注入一次
drawTextCJK("你好", x, y, maxX, color);            // 原签名不变,内部用保存的指针
```

### ② petAnimTick() 硬编码 → yield 回调

现 voice_pet.h 的等待循环(readHttpBody / b64OutPush / wifiPetConnected)硬编码调用
petAnimTick(),网络层反向依赖桌宠动画。改为:

```cpp
wioNetSetYield(petAnimTick);   // 应用注册;不注册则等待期间什么也不做
```

库内等待循环统一调用内部 `wioNetYield()`(判空)。函数指针而非虚函数:零开销、无堆分配。

### ③ 密钥 #include → 参数传入

现 voice_pet.h 直接 include wifi_secrets.h 并用 `__has_include` 做编译期整体开关。改为:

```cpp
wioNetBegin(WIFI_SSID, WIFI_PASS);                  // secrets 头仍在 pet/,由应用 include
wioAsrBaiduBegin(BAIDU_API_KEY, BAIDU_SECRET_KEY);
wioLlmDeepSeekBegin(DEEPSEEK_KEY, systemPrompt);
```

库本身永不含密钥;"没配密钥"从编译期静默消失变为运行时可提示的状态。
`__has_include` 开关逻辑移到 pet 应用层保留(无 secrets 也能编译出离线宠物)。

## 性能铁律(逐条验收)

1. **时延不退化**:pet 迁移前后真机各跑 3 轮语音对话,`T:` 行各分项
   (net/upload/asr/llm)及 total 不得变慢(±5% 容差)。
2. **热路径零堆分配**:录音回调、b64 编码、HTTP 收发循环、字形渲染中不得出现
   String 扩容 / malloc;收响应用预分配缓冲(HttpBuf)。
3. **零成本抽象**:模板 + inline + 函数指针,禁用虚函数;模块独立 .h/.cpp,
   不用的模块不链接进固件。
4. **渲染批量化**:CJK 字形改行缓冲 + pushImage 单次推送(迁移中唯一的
   "行为等价但实现升级"项,真机确认无视觉回归)。预期 5-10 倍提速:
   SPI 事务从每字最多 256 次(逐像素)降为 1 次。

已知热点清单(优化阶段落地):
- readHttpBody:`String += (char)` 逐字节追加(隐含 O(n²) realloc)→ 预分配缓冲 + 批量 read
- CJK 渲染:drawPixel 逐像素 → 行缓冲 + pushImage

## 各模块 API 草图

### L0 WioKitLogic.h(原样迁移)

```cpp
int  httpResponseState(const char* buf, size_t n);   // HTTP_NEED_MORE/DONE/NO_LENGTH
bool chunkedWalk(const char* body, size_t n, char* out, size_t* decodedLen);
int  parseEmotionTag(const char* s, size_t n, size_t* textStart);
struct LightDetector { ... };    // 双阈值迟滞
struct MotionDetector { ... };   // 摇晃/拿起判定
```

### L1 WioKitCjk

```cpp
void wioCjkBegin(Seeed_GFX& d);
int  drawTextCJK(const String& s, int x, int y, int maxX, uint16_t color);
// 内部:16x16 字形拼进行缓冲(512B 栈数组),pushImage 一次推送
```

### L1 WioKitMic

```cpp
bool wioMicBegin();                                  // DMA + FilterBuHp 高通,失败 false
void wioMicConfig(int silenceAvg, uint32_t trailingMs, uint32_t noSpeechMs);
void wioRecStart();
int  wioRecPoll(uint32_t& samples, uint32_t& hint);  // 0 录音中 / 1 完成 / 2 超时没说话
const int16_t* wioRecBuffer();                       // 暴露内部 PCM(零拷贝;下次 RecStart 前有效)
void wioRecTrim(uint32_t& lo, uint32_t& hi);         // 首尾静音裁剪(返回区间,不搬数据)
```

缓冲 96KB(int16 × 48000,3 秒 @16kHz)仍为库内静态数组——占 SAMD51 RAM 一半,
复制一份即爆内存,故 API 直接暴露。

### L1 WioKitNet(header-only 模板)

```cpp
void wioNetBegin(const char* ssid, const char* pass);
bool wioNetConnected(int attempts = 3);
void wioNetSetYield(void (*fn)());
template <typename ClientT>
bool wioReadHttp(ClientT& c, HttpBuf& out, uint32_t maxWaitMs, const char* label);
// HttpBuf:调用方预分配(ASR ~200B,LLM ~2KB,容量调用方定),库内不 malloc
template <typename ClientT> struct B64Stream { ... };  // 流式 base64(含 1KB 批量写出)
void wioMakeWavHeader(uint8_t h[44], uint32_t dataLen, uint32_t sampleRate);
```

保留现有判停语义:按 Content-Length / chunked 终止块立即收工,
无长度信息退回"3 秒无新数据"兜底(RTL8720 栈 connected() 不及时变 false 的坑)。

### L1 WioKitSense

```cpp
bool wioSenseBegin();                                // ADC1 共享读法 + LIS3DH @Wire1
void wioSenseConfig(int darkTh, int lightTh, int shakeMg, int pickupMg, uint32_t stillMs);
int  wioSensePoll();                                 // SE_NONE/DARK/LIGHT/SHAKE/PICKUP
```

ADC1 共享读法(麦克风 DMA 不中断的前提下临时切通道读光线)原样保留——这是踩坑成果。

### L2 WioKitAsrBaidu

```cpp
void wioAsrBaiduBegin(const char* apiKey, const char* secretKey);
bool wioAsrBaiduWarmup();                            // 预取 token(开机调,失败不阻塞)
bool wioAsrBaidu(const int16_t* pcm, uint32_t n, String& transcript, String& note);
// 内部:token 失效(110/111/3302)自动重取一次、WAV 头、明文 80 端口上传、err_no 语义
```

### L2 WioKitLlmDeepSeek

```cpp
void wioLlmDeepSeekBegin(const char* key, const char* systemPrompt);
bool wioLlmAsk(const String& question, String& reply, String& note);
```

情绪标签解析**不在 L2**:标签约定属于"小维人设",应用拿 reply 自行调 L0 的 parseEmotionTag。

### 计时

库各模块向公共 `WioKitTiming` 结构记账,`T:` 行打印格式不变,保证性能基线可对比。

## 迁移步骤(每步可编译、可烧录、可回退,独立提交)

1. **搭库骨架**:建 libraries/WioKit/(properties + 空 src);tools/flash_and_log.sh
   编译命令加 `--libraries libraries`;烧 pet 确认构建链路无影响。
2. **迁 L0**:pet_logic.h → WioKitLogic.h;tests/pet_selftest 改 include 库头;
   **删除 tools/sync_logic.sh**;板上自检全绿。
3. **迁 L1 逐模块**:Cjk(含字库)→ Mic → Net → Sense。每迁一个,pet 就地换用并烧录快测。
   此阶段**纯搬家不优化**(渲染仍 drawPixel、HTTP 仍 String),行为逐位等价。
4. **迁 L2**:百度 ASR、DeepSeek 进库,密钥改参数注入,__has_include 移到应用层;
   真机回归语音全链路 3 轮,记录 `T:` 基线 A。
5. **性能优化**(逐项独立提交,每项后真机对比基线 A):
   - readHttpBody:String → HttpBuf
   - CJK 渲染:drawPixel → 行缓冲 + pushImage(目测无视觉回归)
6. **写示例**:examples/CjkHello、examples/VoiceEcho 单独编译烧录跑通
   (检验库脱离 pet 可独立使用)。
7. **收尾**:更新 README / HANDOFF 文件地图与构建命令。

## 测试策略

| 层 | 手段 | 覆盖 |
|----|------|------|
| L0 纯逻辑 | 板上自检 sketch(现 pet_selftest,机制保留) | HTTP 判停/chunked/情绪标签/探测器 |
| L1/L2 | 真机冒烟:每步迁移后烧 pet 快测对应功能 | 编译通过 + 功能不变 |
| 全链路 | 3 轮语音对话 + `T:` 计时对比 | 时延不退化(±5%) |
| 库独立性 | examples 单独编译烧录 | 不依赖 pet 的任何文件 |

## 风险与对策

- **字库数据迁移**(~9400 行):纯数据搬家,但 tools/gen_font.py 输出路径需同步改,
  避免生成器仍往老位置吐。
- **迁移期间 pet/console 字库双份**:console 不迁、拷贝保留原状,不算新增债务。
- **Arduino IDE 用户**:cli 走 --libraries 参数;IDE 用户需把 WioKit 软链/拷贝到
  sketchbook libraries,README 写清。自用阶段只走 cli,无感。
- **.ino 函数原型提升坑**:自定义 enum/struct 不能出现在 .ino 函数签名里——
  库化后类型都在 .h 中,此坑自然规避,但 pet.ino 改造时仍需留意。

## 非目标(本期不做)

- IMU/SD/蜂鸣器/红外等新硬件封装
- ASR/LLM 统一抽象接口(换厂商不改应用代码)——分层已留好位置,将来再说
- console/ 迁移、独立仓库拆分、对外发布

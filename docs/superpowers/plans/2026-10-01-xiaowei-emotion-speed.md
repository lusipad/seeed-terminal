# 小维 v2:情绪性格 + 响应提速 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Wio Terminal 桌宠「小维」有活泼元气的情绪表现(情绪标签、等待动画、待机小动作、传感器互动),并把"说完 → 回答上屏"的耗时缩短 ≥5 秒。

**Architecture:** 纯逻辑(HTTP 响应判定、chunked 解码、情绪标签、传感器判定)放进无 Arduino 依赖的 `pet_logic.h`,由板上自检 sketch 做单元测试;动画由非阻塞调度器 `pet_anim.h` 驱动,`loop()` 与网络等待循环都调用 `petAnimTick()`;传感器在 `pet_sense.h` 采样并产出事件,由 `pet.ino` 状态机分发。

**Tech Stack:** Arduino (Seeeduino:samd 1.8.6, gnu++14)、Seeed_GFX、rpcWiFi、ArduinoJson 7、Seeed Arduino Mic、LIS3DHTR 库、Python 3 + pyserial(串口日志)。

**Spec:** `docs/superpowers/specs/2026-10-01-xiaowei-emotion-speed-design.md`

## Global Constraints

- 必须独立运行:不依赖 PC,板子自己完成全部网络请求
- AI 全部继续使用 Web API(百度 ASR + DeepSeek),不在本地跑模型
- 局部重绘,禁止动画中整屏刷新(`fillScreen` 只允许出现在 `drawPet()` 里,且只在状态切换时调用)
- 表情一律几何绘制,不用图片素材(RAM 192KB,录音缓冲已占 96KB)
- 不安装 PC 端 C++ 编译器;逻辑测试在板上自检(`tests/pet_selftest/`)
- 密钥文件 `pet/wifi_secrets.h`、`console/wifi_secrets.h`、`host/config.json` 永不提交、不外发
- 串口以 VID 0x2886 自动查找,不写死 COM 口
- Arduino 不支持跨目录 include:`tests/pet_selftest/pet_logic.h` 是 `pet/pet_logic.h` 的拷贝,由 `tools/sync_logic.sh` 同步
- 情绪白名单:`开心/兴奋/惊讶/害羞/疑惑/难过`,其余一律回退"开心"
- 回答正文 45 字以内;DeepSeek `max_tokens` = 120
- 静音截断 `PET_TRAILING_MS` = 900(实测可微调)
- 待机 3 分钟 → 犯困;5 分钟或关灯 10 秒 → 睡觉;亮灯 2 秒 → 醒
- 摇晃 → 晕 3 秒,之后冷却 5 秒

## Review Focus

1. **DeepSeek 不严格按格式输出标签**(全角括号【】、前导空格、只给标签没正文)→ 应正确解析或回退"开心",只有标签时视为空回复报错 —— Task 3 测试 + Task 7 空回复处理
2. **光线 `analogRead` 与麦克风 DMA ADC 冲突** → 开启传感器后录音必须仍正常 —— Task 9 Step 9 真机回归
3. **响应数据里恰好含 `0\r\n\r\n`,或响应头既无 Content-Length 也非 chunked** → 不得提前截断,退回 3 秒兜底 —— Task 2 测试
4. **开机时 WiFi 不可用** → 宠物 ≤20 秒内进入待机,按 B 时再联网 —— Task 5 Step 7
5. **百度 token 失效时返回 3302(而非 110/111)** → 自动重取 token 并重试一次 —— Task 5 Step 6(注:spec 只写了 110/111,本计划补上 3302)

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `.gitignore` | 改 | 增加 `game-console/`、`tools/ambd_flash_tool/`、`tests/pet_selftest/pet_logic.h` |
| `tools/serial_log.py` | 新 | Python 串口日志:逐行带时间戳落盘,板子重启自动重连 |
| `tools/flash_and_log.sh` | 改 | 日志改用 `serial_log.py`;清理残留日志进程 |
| `tools/wait_log.sh` | 新 | 等日志出现某模式并打印匹配行 |
| `tools/sync_logic.sh` | 新 | 把 `pet/pet_logic.h` 拷到自检 sketch |
| `docs/perf-log.md` | 新 | 记录基线与优化后的计时 |
| `pet/pet_logic.h` | 新 | 纯逻辑:HTTP 判定、chunked 解码、情绪标签、光线/动作判定 |
| `tests/pet_selftest/pet_selftest.ino` | 新 | 板上自检 |
| `pet/voice_pet.h` | 改 | 计时、S1–S5 提速、动画 tick、情绪标签 |
| `pet/pet_face.h` | 改 | 14 个表情枚举、局部重绘 `drawFeatures`/`drawEyesOnly`、装饰层 |
| `pet/pet_anim.h` | 新 | 动画调度器 |
| `pet/pet_sense.h` | 新 | 光线 + IMU 采样 → 事件 |
| `pet/pet.ino` | 改 | 状态机:动画、情绪、睡眠、传感器事件 |
| `HANDOFF.md`、`README.md` | 改 | 收尾更新 |

**常用命令(下文直接引用)**

- 编译烧录 + 挂日志:`bash tools/flash_and_log.sh <sketch目录> <秒数>`(sketch 目录如 `pet`、`tests/pet_selftest`)
- 只编译:`"/c/Program Files/Arduino CLI/arduino-cli.exe" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path build/<名> <目录>`
- 日志文件:`/c/<user>/AppData/Local/Temp/wio_serial.log`
- 等待日志:`bash tools/wait_log.sh '<正则>' <秒数>`(Claude Code 里用 `run_in_background` 运行)

---

### Task 0: 初始化 git 仓库

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 无
- Produces: 一个干净的 git 仓库,后续任务每步可提交

- [ ] **Step 1: 扩充 .gitignore**

在 `.gitignore` 末尾追加:

```gitignore

# 独立仓库 / 大体积工具 / 同步生成的拷贝
game-console/
tools/ambd_flash_tool/
tests/pet_selftest/pet_logic.h
```

- [ ] **Step 2: 初始化并确认密钥被忽略**

```bash
cd /d/Repos/seeed-terminal && git init && git add -A && git status --short | grep -E "wifi_secrets|config.json" && echo "STOP: 密钥被暂存了" || echo "OK: 密钥未暂存"
```
Expected: 最后一行输出 `OK: 密钥未暂存`。若出现 `STOP`,`git reset` 后检查 `.gitignore`,不要继续。

- [ ] **Step 3: 首次提交**

```bash
git commit -m "chore: initial snapshot of seeed-terminal"
```

---

### Task 1: 可靠的串口日志 + 每轮计时 + 采集基线

**Files:**
- Create: `tools/serial_log.py`、`tools/wait_log.sh`、`docs/perf-log.md`
- Modify: `tools/flash_and_log.sh`(第 1 步清理、第 4 步日志)
- Modify: `pet/voice_pet.h`(新增 `PetTiming`;`petProcessVoice` 内打点)
- Modify: `pet/pet.ino`(`ST_THINK` 里打印计时)

**Interfaces:**
- Consumes: 无
- Produces:
  - `struct PetTiming { uint32_t net, upload, asr, llmConn, llm; }; PetTiming petTm;`
  - `void petPrintTiming(uint32_t processMs);` —— 打印 `T: trail=… net=… upload=… asr=… llm_conn=… llm=… total=…`
  - `tools/wait_log.sh <正则> [秒数]`

- [ ] **Step 1: 写 Python 串口日志器**

Create `tools/serial_log.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wio Terminal 串口日志:按 VID 0x2886 自动找口,逐行带时间戳追加写文件(每行 flush)。
板子重启 / USB 重新枚举导致串口断开时,自动重新找口重连。

用法:python tools/serial_log.py <秒数> <日志路径>
"""
import sys
import time

import serial
import serial.tools.list_ports

SEEED_VID = 0x2886


def find_port():
    for p in serial.tools.list_ports.comports():
        if p.vid == SEEED_VID:
            return p.device
    return None


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    path = sys.argv[2]
    deadline = time.time() + dur
    with open(path, "a", encoding="utf-8") as f:
        while time.time() < deadline:
            port = find_port()
            if not port:
                time.sleep(0.5)
                continue
            try:
                with serial.Serial(port, 115200, timeout=0.4) as sp:
                    sp.dtr = True
                    f.write(f"# connected {port}\n")
                    f.flush()
                    while time.time() < deadline:
                        line = sp.readline()
                        if line:
                            text = line.decode("utf-8", "replace").rstrip()
                            f.write(time.strftime("%H:%M:%S ") + text + "\n")
                            f.flush()
            except serial.SerialException as e:  # 拔插/重启:重新找口
                f.write(f"# serial lost: {e}\n")
                f.flush()
                time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: flash_and_log.sh 改用 Python 日志器**

在 `tools/flash_and_log.sh` 第 1 步(清掉占用串口的残留进程)的 `powershell.exe ... | head -4` 那一行**之后**插入:

```bash
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'serial_log.py' } | ForEach-Object { 'KILL ' + \$_.ProcessId; Stop-Process -Id \$_.ProcessId -Force }" 2>&1 | head -4
```

把第 4 步(从 `# 4. 挂实时日志` 到文件末尾)整段替换为:

```bash
# 4. 挂实时日志(Python 逐行落盘;板子重启/USB 重枚举后自动重连)
rm -f "$LOG"
(python tools/serial_log.py "$DUR" "$(cygpath -w "$LOG")" > /dev/null 2>&1 &)
echo "logger armed (${DUR}s) -> $LOG"
```

- [ ] **Step 3: 写等待日志脚本**

Create `tools/wait_log.sh`:

```bash
#!/bin/bash
# 等日志里出现匹配正则的行(最多 N 秒),然后打印所有匹配行
# 用法: bash tools/wait_log.sh <正则> [秒数]
LOG=/c/<user>/AppData/Local/Temp/wio_serial.log
PAT="$1"
MAX="${2:-60}"
for _ in $(seq 1 "$MAX"); do
  grep -aqE "$PAT" "$LOG" 2>/dev/null && break
  sleep 1
done
grep -aE "$PAT" "$LOG" || { echo "TIMEOUT waiting for: $PAT"; exit 1; }
```

- [ ] **Step 4: 验证日志器能抓到开机行**

```bash
python -c "import serial; print('pyserial ok')" && bash tools/flash_and_log.sh none 120
```
然后(后台运行)`bash tools/wait_log.sh 'connected|HELLO' 30`。
Expected: 出现 `# connected COM3`(或 COM4);如板子刚好重启还会有 `HELLO pet 1.0`。

- [ ] **Step 5: 在 voice_pet.h 加计时结构**

在 `pet/voice_pet.h` 中 `const uint32_t PET_NO_SPEECH_MS = 8000;` 这一行之后插入:

```cpp

// 每轮对话各阶段耗时(ms);pet.ino 在每轮结束调用 petPrintTiming 打印 "T:" 行
struct PetTiming { uint32_t net, upload, asr, llmConn, llm; };
PetTiming petTm = {0, 0, 0, 0, 0};

void petPrintTiming(uint32_t processMs) {
  Serial.print("T: trail=");
  Serial.print(PET_TRAILING_MS);
  Serial.print(" net=");
  Serial.print(petTm.net);
  Serial.print(" upload=");
  Serial.print(petTm.upload);
  Serial.print(" asr=");
  Serial.print(petTm.asr);
  Serial.print(" llm_conn=");
  Serial.print(petTm.llmConn);
  Serial.print(" llm=");
  Serial.print(petTm.llm);
  Serial.print(" total=");
  Serial.println(PET_TRAILING_MS + processMs);
}
```

- [ ] **Step 6: 在 petProcessVoice 里打点**

在 `pet/voice_pet.h` 的 `petProcessVoice` 中:

1. 把开头的
```cpp
  if (!wifiPetConnected()) {
```
替换为
```cpp
  petTm = {0, 0, 0, 0, 0};
  const uint32_t tNet = millis();
  if (!wifiPetConnected()) {
```
2. 把
```cpp
  // ASR 走 HTTP 明文(80 端口)
```
所在注释行**之前**插入一行:
```cpp
  petTm.net = millis() - tNet;
```
3. 把
```cpp
  Serial.print("V: wav uploaded ms=");
  Serial.println(millis() - upT);

  String asrBody;
  if (!readHttpBody(client, asrBody, 60000, "asr")) {
```
替换为
```cpp
  petTm.upload = millis() - upT;
  Serial.print("V: wav uploaded ms=");
  Serial.println(petTm.upload);

  String asrBody;
  const uint32_t tAsr = millis();
  const bool asrOk = readHttpBody(client, asrBody, 60000, "asr");
  petTm.asr = millis() - tAsr;
  if (!asrOk) {
```
4. 把
```cpp
  WiFiClientSecure client2;
  if (!client2.connect("api.deepseek.com", 443, 20000)) {
```
替换为
```cpp
  const uint32_t tConn = millis();
  WiFiClientSecure client2;
  if (!client2.connect("api.deepseek.com", 443, 20000)) {
```
并在该 `if` 块结束的 `}` 之后插入:
```cpp
  petTm.llmConn = millis() - tConn;
  const uint32_t tLlm = millis();
```
5. 把
```cpp
  String llmBody;
  if (!readHttpBody(client2, llmBody, 30000, "llm")) {
```
替换为
```cpp
  String llmBody;
  const bool llmOk = readHttpBody(client2, llmBody, 30000, "llm");
  petTm.llm = millis() - tLlm;
  if (!llmOk) {
```

- [ ] **Step 7: pet.ino 打印计时**

在 `pet/pet.ino` 的 `case ST_THINK:` 中,把
```cpp
      const bool ok = petProcessVoice(recSamples, t, r, note);
```
替换为
```cpp
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, t, r, note);
      petPrintTiming(millis() - tProc);
```

- [ ] **Step 8: 烧录并采集基线(需用户配合)**

```bash
bash tools/flash_and_log.sh pet 900
```
请用户:按一下 B,说一句短话(如"今天星期几"),等回答上屏;**重复 3 次**。然后(后台)`bash tools/wait_log.sh '^.{9}T: ' 600`。
Expected: 3 行 `T: trail=1300 net=… upload=… asr=… llm_conn=… llm=… total=…`。若只有开机行没有 `V:`/`T:` 行,说明日志问题未解决 —— 停下来按 systematic-debugging 排查,不要继续。

- [ ] **Step 9: 记录基线**

Create `docs/perf-log.md`(把 Step 8 的三行数字填进表格,`中位 total` 取三者中位数):

```markdown
# 小维响应耗时记录

单位 ms。total = 静音截断等待 + 联网/识别/回答全过程("说完 → 上屏")。

## 基线(优化前,2026-10-01)

| 轮次 | trail | net | upload | asr | llm_conn | llm | total |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

中位 total:

## 优化后

(Task 4 / Task 5 / Task 10 后追加)
```

- [ ] **Step 10: 提交**

```bash
git add tools/serial_log.py tools/wait_log.sh tools/flash_and_log.sh pet/voice_pet.h pet/pet.ino docs/perf-log.md
git commit -m "feat(pet): reliable serial logger, per-round timing, baseline"
```

---

### Task 2: pet_logic.h —— HTTP 响应判定与 chunked 解码(TDD,板上自检)

**Files:**
- Create: `pet/pet_logic.h`、`tests/pet_selftest/pet_selftest.ino`、`tools/sync_logic.sh`

**Interfaces:**
- Consumes: 无(纯 C,无 Arduino 依赖)
- Produces:
  - `enum HttpState { HTTP_NEED_MORE = 0, HTTP_DONE = 1, HTTP_NO_LENGTH = 2 };`
  - `long httpHeaderEnd(const char* buf, size_t n);` —— `\r\n\r\n` 的位置,未找到返回 -1
  - `bool httpIsChunked(const char* buf, size_t headerLen);`
  - `bool chunkedWalk(const char* body, size_t n, char* out, size_t* decodedLen);` —— 完整返回 true;`out` 非空时写出解码数据(允许 `out == body` 原地解码)
  - `int httpResponseState(const char* buf, size_t n);`
  - 自检 sketch 的 `void check(bool ok, const char* name);`

- [ ] **Step 1: 写同步脚本**

Create `tools/sync_logic.sh`:

```bash
#!/bin/bash
# pet/pet_logic.h 是唯一源头;Arduino 不支持跨目录 include,自检 sketch 使用拷贝
cd "$(dirname "$0")/.." && cp pet/pet_logic.h tests/pet_selftest/pet_logic.h && echo "synced pet_logic.h"
```

- [ ] **Step 2: 写失败的自检(先写测试)**

Create `tests/pet_selftest/pet_selftest.ino`:

```cpp
// pet_logic.h 板上自检:等串口打开后跑全部断言,之后每 3 秒重复打印汇总
// 运行:bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60
#include <Arduino.h>
#include "pet_logic.h"

int passN = 0, failN = 0;

void check(bool ok, const char* name) {
  if (ok) {
    passN++;
    return;
  }
  failN++;
  Serial.print("FAIL ");
  Serial.println(name);
}

int st(const char* s) { return httpResponseState(s, strlen(s)); }

bool decodeEq(const char* in, const char* want) {
  char buf[96];
  strcpy(buf, in);
  size_t n = 0;
  if (!chunkedWalk(buf, strlen(buf), buf, &n)) return false;
  return n == strlen(want) && memcmp(buf, want, n) == 0;
}

void testHttp() {
  check(st("HTTP/1.1 200 OK\r\nContent-Le") == HTTP_NEED_MORE, "http: header partial");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhel") == HTTP_NEED_MORE, "http: cl short");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello") == HTTP_DONE, "http: cl full");
  check(st("HTTP/1.1 200 OK\r\ncontent-length:5\r\n\r\nhello") == HTTP_DONE, "http: cl lowercase no space");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n") == HTTP_DONE, "http: cl zero");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n") == HTTP_DONE,
        "http: chunked done");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n") == HTTP_NEED_MORE,
        "http: chunked no terminator");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\nx0\r\n\r\ny\r\n") == HTTP_NEED_MORE,
        "http: fake terminator inside data");
  check(st("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nabc") == HTTP_NO_LENGTH, "http: no length");
  const char* h = "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nX";
  check(httpHeaderEnd(h, strlen(h)) == 43, "http: header end pos");
  check(httpIsChunked(h, 43), "http: is chunked");
  check(!httpIsChunked("HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n", 34), "http: not chunked");
}

void testChunked() {
  check(decodeEq("5\r\nhello\r\n0\r\n\r\n", "hello"), "chunk: single");
  check(decodeEq("3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n", "abcde"), "chunk: multi");
  check(decodeEq("0\r\n\r\n", ""), "chunk: empty");
  check(decodeEq("A\r\n0123456789\r\n0\r\n\r\n", "0123456789"), "chunk: hex upper");
  check(decodeEq("3;ext=1\r\nabc\r\n0\r\n\r\n", "abc"), "chunk: extension");
  check(!decodeEq("5\r\nhel", "hel"), "chunk: truncated is incomplete");
}

void printSummary() {
  Serial.print(failN ? "SELFTEST FAIL " : "SELFTEST PASS ");
  Serial.print(passN);
  Serial.print("/");
  Serial.println(passN + failN);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
  }
  delay(300);
  testHttp();
  testChunked();
  printSummary();
}

void loop() {
  delay(3000);
  printSummary();
}
```

- [ ] **Step 3: 写只有声明的桩,确认测试会失败**

Create `pet/pet_logic.h`(桩版本):

```cpp
// ---- 纯逻辑(无 Arduino 依赖)----
#pragma once
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

enum HttpState { HTTP_NEED_MORE = 0, HTTP_DONE = 1, HTTP_NO_LENGTH = 2 };

inline long httpHeaderEnd(const char*, size_t) { return -1; }
inline bool httpIsChunked(const char*, size_t) { return false; }
inline bool chunkedWalk(const char*, size_t, char*, size_t*) { return false; }
inline int httpResponseState(const char*, size_t) { return HTTP_NEED_MORE; }
```

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,然后(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST FAIL …`,且有多行 `FAIL http: …` / `FAIL chunk: …`。

- [ ] **Step 4: 写实现**

把 `pet/pet_logic.h` 整个替换为:

```cpp
// ---- 纯逻辑(无 Arduino 依赖):HTTP 响应判定、chunked 解码 ----
// pet/ 是唯一源头;改完运行 tools/sync_logic.sh 同步到 tests/pet_selftest/,再跑板上自检
#pragma once
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

enum HttpState { HTTP_NEED_MORE = 0, HTTP_DONE = 1, HTTP_NO_LENGTH = 2 };

// 在 [h, h+n) 中不区分大小写地查找 needle,返回偏移;找不到返回 -1
inline long ciFind(const char* h, size_t n, const char* needle) {
  const size_t m = strlen(needle);
  if (m == 0 || m > n) return -1;
  for (size_t i = 0; i + m <= n; i++) {
    size_t j = 0;
    while (j < m && tolower((unsigned char)h[i + j]) == tolower((unsigned char)needle[j])) j++;
    if (j == m) return (long)i;
  }
  return -1;
}

inline long httpHeaderEnd(const char* buf, size_t n) { return ciFind(buf, n, "\r\n\r\n"); }

inline bool httpIsChunked(const char* buf, size_t headerLen) {
  return ciFind(buf, headerLen, "\ntransfer-encoding:") >= 0 && ciFind(buf, headerLen, "chunked") >= 0;
}

// 逐块走一遍 chunked 正文:遇到 0 长度块及其后的 CRLF 才算完整(数据里出现 "0\r\n\r\n" 不会误判)。
// out 非空时把数据依次写入 out(允许 out == body 原地解码,写指针永远不超过读指针)。
inline bool chunkedWalk(const char* body, size_t n, char* out, size_t* decodedLen) {
  size_t pos = 0, w = 0;
  while (true) {
    const long le = ciFind(body + pos, n - pos, "\r\n");
    if (le < 0) return false;
    size_t sz = 0;
    bool any = false;
    for (size_t k = pos; k < pos + (size_t)le; k++) {  // 十六进制长度,忽略 ";扩展"
      const char c = body[k];
      int v;
      if (c >= '0' && c <= '9') v = c - '0';
      else if (c >= 'a' && c <= 'f') v = c - 'a' + 10;
      else if (c >= 'A' && c <= 'F') v = c - 'A' + 10;
      else break;
      sz = sz * 16 + v;
      any = true;
    }
    if (!any) return false;
    pos += (size_t)le + 2;
    if (sz == 0) {
      if (n - pos < 2) return false;  // 末尾 CRLF 未到
      if (decodedLen) *decodedLen = w;
      return true;
    }
    if (n - pos < sz + 2) return false;
    if (out) memmove(out + w, body + pos, sz);
    w += sz;
    pos += sz + 2;
  }
}

// 判断已收到的响应是否完整:按 Content-Length 或 chunked 终止块;两者都没有返回 HTTP_NO_LENGTH(调用方兜底)
inline int httpResponseState(const char* buf, size_t n) {
  const long he = httpHeaderEnd(buf, n);
  if (he < 0) return HTTP_NEED_MORE;
  const size_t bodyStart = (size_t)he + 4;
  const size_t bodyLen = n - bodyStart;
  const long cl = ciFind(buf, (size_t)he, "\ncontent-length:");
  if (cl >= 0) {
    const long want = strtol(buf + cl + 16, NULL, 10);  // 数字后面紧跟 \r,strtol 会停下
    return (long)bodyLen >= want ? HTTP_DONE : HTTP_NEED_MORE;
  }
  if (httpIsChunked(buf, (size_t)he)) {
    return chunkedWalk(buf + bodyStart, bodyLen, NULL, NULL) ? HTTP_DONE : HTTP_NEED_MORE;
  }
  return HTTP_NO_LENGTH;
}
```

- [ ] **Step 5: 跑自检确认通过**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,然后(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST PASS 18/18`,无 `FAIL` 行。

- [ ] **Step 6: 提交**

```bash
git add pet/pet_logic.h tests/pet_selftest/pet_selftest.ino tools/sync_logic.sh
git commit -m "feat(pet): pure HTTP completeness + chunked decode logic with on-board selftest"
```

---

### Task 3: pet_logic.h —— 情绪标签解析(TDD)

**Files:**
- Modify: `pet/pet_logic.h`(追加)
- Modify: `tests/pet_selftest/pet_selftest.ino`(追加 `testEmotion`)

**Interfaces:**
- Consumes: Task 2 的 `check()`
- Produces:
  - `enum Emotion { EMO_HAPPY = 0, EMO_EXCITED, EMO_SURPRISED, EMO_SHY, EMO_CONFUSED, EMO_SAD };`
  - `int parseEmotionTag(const char* s, size_t n, size_t* textStart);` —— 返回情绪;`*textStart` 为正文起点;无标签/非法标签返回 `EMO_HAPPY` 且 `*textStart = 0`

- [ ] **Step 1: 写失败的测试**

在 `tests/pet_selftest/pet_selftest.ino` 的 `void printSummary()` **之前**插入:

```cpp
void emo(const char* s, int wantE, const char* wantText, const char* name) {
  size_t ts = 999;
  const int e = parseEmotionTag(s, strlen(s), &ts);
  check(ts <= strlen(s) && e == wantE && strcmp(s + ts, wantText) == 0, name);
}

void testEmotion() {
  emo("[开心]好呀", EMO_HAPPY, "好呀", "emo: happy");
  emo("[兴奋]冲!", EMO_EXCITED, "冲!", "emo: excited");
  emo("[惊讶]哇", EMO_SURPRISED, "哇", "emo: surprised");
  emo("[害羞]嘿嘿", EMO_SHY, "嘿嘿", "emo: shy");
  emo("[疑惑]嗯?", EMO_CONFUSED, "嗯?", "emo: confused");
  emo("[难过]呜", EMO_SAD, "呜", "emo: sad");
  emo("你好呀", EMO_HAPPY, "你好呀", "emo: no tag");
  emo("[生气]哼", EMO_HAPPY, "[生气]哼", "emo: unknown tag kept");
  emo("[开心哈哈", EMO_HAPPY, "[开心哈哈", "emo: no close bracket");
  emo("[兴奋] 哇", EMO_EXCITED, "哇", "emo: space after tag");
  emo("【惊讶】哇", EMO_SURPRISED, "哇", "emo: fullwidth brackets");
  emo(" [害羞]嗯", EMO_SHY, "嗯", "emo: leading space");
  emo("[开心]", EMO_HAPPY, "", "emo: tag only");
  emo("", EMO_HAPPY, "", "emo: empty");
}
```

在 `setup()` 中 `testChunked();` 之后加一行 `testEmotion();`。

在 `pet/pet_logic.h` 末尾追加桩:

```cpp

enum Emotion { EMO_HAPPY = 0, EMO_EXCITED, EMO_SURPRISED, EMO_SHY, EMO_CONFUSED, EMO_SAD };

inline int parseEmotionTag(const char*, size_t, size_t* textStart) {
  *textStart = 0;
  return EMO_HAPPY;
}
```

- [ ] **Step 2: 跑自检确认失败**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,然后(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST FAIL`,含 `FAIL emo: excited` 等(桩只对"无标签/非法/空"几条碰巧正确)。

- [ ] **Step 3: 写实现**

把 Step 1 追加的桩 `parseEmotionTag` 替换为:

```cpp
// 解析回答开头的情绪标签:支持 [情绪] 与全角【情绪】,允许前导空白,剥掉标签及其后空白。
// 无标签 / 不在白名单 / 缺右括号 → EMO_HAPPY,*textStart = 0(原文完整显示)
inline int parseEmotionTag(const char* s, size_t n, size_t* textStart) {
  *textStart = 0;
  size_t b = 0;
  while (b < n && (s[b] == ' ' || s[b] == '\t' || s[b] == '\r' || s[b] == '\n')) b++;
  size_t open = 0;
  if (b < n && s[b] == '[') open = 1;
  else if (b + 3 <= n && memcmp(s + b, "\xE3\x80\x90", 3) == 0) open = 3;  // 【
  if (!open) return EMO_HAPPY;
  const size_t tagStart = b + open;
  size_t close = 0, closeLen = 0;
  for (size_t i = tagStart; i < n && i <= tagStart + 16; i++) {
    if (s[i] == ']') { close = i; closeLen = 1; break; }
    if (i + 3 <= n && memcmp(s + i, "\xE3\x80\x91", 3) == 0) { close = i; closeLen = 3; break; }  // 】
  }
  if (!closeLen) return EMO_HAPPY;
  static const char* const NAMES[6] = {"开心", "兴奋", "惊讶", "害羞", "疑惑", "难过"};
  const size_t tagLen = close - tagStart;
  for (int e = 0; e < 6; e++) {
    if (strlen(NAMES[e]) == tagLen && memcmp(s + tagStart, NAMES[e], tagLen) == 0) {
      size_t p = close + closeLen;
      while (p < n && (s[p] == ' ' || s[p] == '\t' || s[p] == '\r' || s[p] == '\n')) p++;
      *textStart = p;
      return e;
    }
  }
  return EMO_HAPPY;
}
```

- [ ] **Step 4: 跑自检确认通过**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,然后(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST PASS 32/32`。

- [ ] **Step 5: 提交**

```bash
git add pet/pet_logic.h tests/pet_selftest/pet_selftest.ino
git commit -m "feat(pet): emotion tag parser with fullwidth/whitespace tolerance"
```

---

### Task 4: 提速 S1 + S3 + S4 —— 按协议收工、缩短静音截断、限制 token

**Files:**
- Modify: `pet/voice_pet.h`(include、`readHttpBody` 整体替换、两个常量、`max_tokens`)
- Modify: `docs/perf-log.md`

**Interfaces:**
- Consumes: `httpResponseState`、`httpHeaderEnd`、`httpIsChunked`、`chunkedWalk`(Task 2)
- Produces: `template <typename ClientT> bool readHttpBody(ClientT& client, String& body, uint32_t maxWaitMs, const char* label, bool keepOpen = false);` —— `keepOpen=true` 且响应完整时不关闭连接(Task 10 用)

- [ ] **Step 1: 引入 pet_logic.h**

在 `pet/voice_pet.h` 中 `#include <ArduinoJson.h>` 之后加一行:

```cpp
#include "pet_logic.h"
```

- [ ] **Step 2: 替换 readHttpBody**

把 `pet/voice_pet.h` 中整个 `readHttpBody` 模板函数(从 `template <typename ClientT>\nbool readHttpBody(` 到其结尾 `return true;\n}`)替换为:

```cpp
// 读一个 HTTP 响应:按 Content-Length / chunked 终止块判断收完立即返回;
// 无长度信息或异常时退回"3 秒无新数据即收工"兜底。成功(200 且头完整)返回 true,body 为解码后的正文。
template <typename ClientT>
bool readHttpBody(ClientT& client, String& body, uint32_t maxWaitMs, const char* label, bool keepOpen = false) {
  String payload;
  const unsigned long start = millis();
  size_t lastLen = 0;
  unsigned long lastGrowth = millis();
  int hs = HTTP_NEED_MORE;
  while ((client.connected() || client.available()) && payload.length() < 16000) {
    bool got = false;
    while (client.available()) {
      payload += (char)client.read();
      got = true;
    }
    if (got) {
      hs = httpResponseState(payload.c_str(), payload.length());
      if (hs == HTTP_DONE) break;  // 按协议收满,立即收工
    }
    if (payload.length() != lastLen) {
      lastLen = payload.length();
      lastGrowth = millis();
    }
    if (payload.length() > 0 && millis() - lastGrowth > 3000) break;  // 兜底
    if (millis() - start > maxWaitMs) break;
    delay(5);
  }
  if (!keepOpen || hs != HTTP_DONE) client.stop();
  const long headerEnd = httpHeaderEnd(payload.c_str(), payload.length());
  if (payload.length() && headerEnd < 0) {
    Serial.print("V: http raw=");
    Serial.println(payload.substring(0, 170));  // 不完整响应:原样打印排查
  }
  Serial.print("V: http[");
  Serial.print(label);
  Serial.print("] wait=");
  Serial.print(millis() - start);
  Serial.print("ms len=");
  Serial.print(payload.length());
  Serial.print(" done=");
  Serial.println(hs);
  if (headerEnd < 0) return false;
  if (!payload.startsWith("HTTP/1.1 200") && !payload.startsWith("HTTP/1.0 200")) return false;
  body = payload.substring(headerEnd + 4);
  if (httpIsChunked(payload.c_str(), (size_t)headerEnd)) {
    size_t decoded = 0;
    if (!body.length() || !chunkedWalk(body.begin(), body.length(), body.begin(), &decoded)) return false;
    body.remove(decoded);
  }
  return true;
}
```

- [ ] **Step 3: S3 / S4 常量**

在 `pet/voice_pet.h`:
- 把 `const uint32_t PET_TRAILING_MS = 1300;  // 说完静音多久自动停` 改为 `const uint32_t PET_TRAILING_MS = 900;  // 说完静音多久自动停(实测可调)`
- 把 `req2["max_tokens"] = 300;` 改为 `req2["max_tokens"] = 120;  // 回答 45 字以内,够用且限制最坏耗时`

- [ ] **Step 4: 编译**

Run: `"/c/Program Files/Arduino CLI/arduino-cli.exe" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path build/pet pet 2>&1 | tail -3`
Expected: 输出 `Sketch uses … bytes`,无 `error`。

- [ ] **Step 5: 真机测 3 轮(需用户配合)**

```bash
bash tools/flash_and_log.sh pet 900
```
请用户按 B 说话 3 次。然后(后台)`bash tools/wait_log.sh 'T: |done=' 600`。
Expected: 每个 `http[…]` 行 `done=1`;`asr`、`llm` 的 wait 不再有约 3000ms 的尾巴;回答正常上屏。若某行 `done=2`(无长度)或 `done=0`,记下 label,属于兜底路径,不算失败。

- [ ] **Step 6: 记录并提交**

在 `docs/perf-log.md` 的"优化后"下追加一节 `### S1+S3+S4(Task 4)`,用与基线相同的表格填入 3 轮数字和中位 total。

```bash
git add pet/voice_pet.h docs/perf-log.md
git commit -m "perf(pet): stop reading HTTP at protocol end, trailing 900ms, max_tokens 120"
```

---

### Task 5: 提速 S2 —— 开机预连 + token 失效自动重取

**Files:**
- Modify: `pet/voice_pet.h`(`wifiPetConnected` 加参数、新增 `petNetWarmup`、拆出 `baiduAsrOnce` / `petAskLlm`、重写 `petProcessVoice`)
- Modify: `pet/pet.ino`(`setup()`)
- Modify: `docs/perf-log.md`

**Interfaces:**
- Consumes: `readHttpBody`(Task 4)、`petTm`(Task 1)
- Produces:
  - `bool wifiPetConnected(int attempts = 3);`
  - `void petNetWarmup();`
  - `int baiduAsrOnce(uint32_t lo, uint32_t n, String& transcript, String& note);` —— 返回百度 `err_no`;传输失败返回 -1;响应缺 err_no 返回 -2
  - `bool petAskLlm(const String& question, String& reply, String& note);`
  - `bool petProcessVoice(uint32_t samples, String& transcript, String& reply, String& note);`(签名不变)
  - 常量 `const char* const PET_SYSTEM_PROMPT`

- [ ] **Step 1: wifiPetConnected 支持重试次数**

在 `pet/voice_pet.h` 中:
- `bool wifiPetConnected() {` 改为 `bool wifiPetConnected(int attempts = 3) {`
- `for (int attempt = 1; attempt <= 3; attempt++) {` 改为 `for (int attempt = 1; attempt <= attempts; attempt++) {`

- [ ] **Step 2: 新增开机预连**

在 `fetchBaiduToken()` 函数结束的 `}` 之后插入:

```cpp

// 开机预连:WiFi(只试 1 次,≤15s)+ 百度 token。失败不阻止开机:离线照常做宠物,按 B 时再连
void petNetWarmup() {
  const uint32_t t0 = millis();
#if PET_TEST_OFFLINE
  const bool ok = false;  // 测试:模拟开机时无网
#else
  const bool ok = wifiPetConnected(1) && fetchBaiduToken();
#endif
  Serial.print("V: warmup ");
  Serial.print(ok ? "ok" : "failed");
  Serial.print(" ms=");
  Serial.println(millis() - t0);
}
```

并在文件顶部 `#include <Arduino.h>` 之后加:

```cpp
#ifndef PET_TEST_OFFLINE
#define PET_TEST_OFFLINE 0   // 1 = 开机预连直接失败(测试离线开机)
#endif
#ifndef PET_TEST_BAD_TOKEN
#define PET_TEST_BAD_TOKEN 0 // 1 = 预连后把 token 改坏(测试失效自动重取)
#endif
```

- [ ] **Step 3: 拆分并重写 petProcessVoice**

把 `pet/voice_pet.h` 中从 `// 识别 + 回答(阻塞,数秒)` 注释开始、到 `#endif  // PET_HAS_WIFI` **之前**的全部内容(即整个 `petProcessVoice`)替换为:

```cpp
const char* const PET_SYSTEM_PROMPT =
    "你是电子桌宠\"小维\",说话风格:活泼、简短、口语化。"
    "用简体中文回答用户(45字以内),直接输出回答,不要任何前缀或解释。";

// 上传一次识别请求。返回百度 err_no;传输层失败返回 -1(note 填原因);响应缺 err_no 返回 -2
int baiduAsrOnce(uint32_t lo, uint32_t n, String& transcript, String& note) {
  // ASR 走 HTTP 明文(80 端口):板载 TLS 写入只有 ~5KB/s,上传大音频会被服务器掐线;
  // 明文 TCP 快数倍。令牌仍走 HTTPS,音频本身在家庭网络内明文传输(玩具可接受)。
  WiFiClient client;
  if (!client.connect("vop.baidu.com", 80, 15000)) {
    note = "asr connect failed";
    return -1;
  }
  const uint32_t wavLen = 44 + 2 * n;
  const uint32_t b64Len = ((wavLen + 2) / 3) * 4;
  const String head = String("{\"format\":\"wav\",\"rate\":16000,\"dev_pid\":1537,") +
                      "\"channel\":1,\"cuid\":\"wioterminal001\",\"token\":\"" + baiduToken +
                      "\",\"len\":" + String(wavLen) + ",\"speech\":\"";
  const char* tail = "\"}";
  String req = "POST /server_api HTTP/1.1\r\n"
               "Host: vop.baidu.com\r\n"
               "Content-Type: application/json\r\n"
               "Connection: close\r\nContent-Length: ";
  req += String(head.length() + b64Len + strlen(tail));
  req += "\r\n\r\n";
  client.print(req);
  client.print(head);
  B64State st = {{0, 0}, 0};
  const uint32_t upT = millis();
  // WAV 头 + int16 小端 PCM,必须 flush,否则实际字节数少于 Content-Length,服务器会一直等
  uint8_t wavHead[44];
  makeWavHeader(wavHead, 2 * n);
  b64Write(client, st, wavHead, 44);
  b64Write(client, st, (const uint8_t*)(petPcm + lo), 2 * n);
  b64Flush(client, st);
  client.print(tail);
  petTm.upload = millis() - upT;
  Serial.print("V: wav uploaded ms=");
  Serial.println(petTm.upload);

  String asrBody;
  const uint32_t tAsr = millis();
  const bool ok = readHttpBody(client, asrBody, 60000, "asr");
  petTm.asr = millis() - tAsr;
  if (!ok) {
    note = "asr http error";
    return -1;
  }
  JsonDocument adoc;
  if (deserializeJson(adoc, asrBody)) {
    note = "asr bad json";
    return -1;
  }
  const int errNo = adoc["err_no"] | -2;
  transcript = String(adoc["result"][0] | "");
  Serial.print("V: baidu err_no=");
  Serial.print(errNo);
  Serial.print(" transcript=");
  Serial.println(transcript);
  return errNo;
}

// 问 DeepSeek,reply 为回答原文
bool petAskLlm(const String& question, String& reply, String& note) {
  const uint32_t tConn = millis();
  WiFiClientSecure client2;
  if (!client2.connect("api.deepseek.com", 443, 20000)) {
    note = "llm connect failed";
    return false;
  }
  petTm.llmConn = millis() - tConn;
  const uint32_t tLlm = millis();
  JsonDocument req2;
  req2["model"] = "deepseek-chat";
  JsonArray msgs = req2["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = PET_SYSTEM_PROMPT;
  JsonObject user = msgs.add<JsonObject>();
  user["role"] = "user";
  user["content"] = question;
  req2["max_tokens"] = 120;  // 回答 45 字以内,够用且限制最坏耗时

  String body2;
  serializeJson(req2, body2);
  String req2s = "POST /v1/chat/completions HTTP/1.1\r\n"
                 "Host: api.deepseek.com\r\n"
                 "Authorization: Bearer " DEEPSEEK_KEY "\r\n"
                 "Content-Type: application/json\r\n"
                 "Connection: close\r\nContent-Length: ";
  req2s += String(body2.length());
  req2s += "\r\n\r\n";
  req2s += body2;
  client2.print(req2s);

  String llmBody;
  const bool ok = readHttpBody(client2, llmBody, 30000, "llm");
  petTm.llm = millis() - tLlm;
  if (!ok) {
    note = "llm http error";
    return false;
  }
  JsonDocument ldoc;
  if (deserializeJson(ldoc, llmBody)) {
    note = "llm bad json";
    return false;
  }
  reply = String(ldoc["choices"][0]["message"]["content"] | "");
  Serial.print("V: reply=");
  Serial.println(reply);
  if (!reply.length()) {
    note = "llm empty reply";
    return false;
  }
  return true;
}

// 识别 + 回答(阻塞,数秒):成功 true;transcript/reply/note 填充
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, String& note) {
  transcript = "";
  reply = "";
  note = "";
  petTm = {0, 0, 0, 0, 0};

  const uint32_t tNet = millis();
  if (!wifiPetConnected()) {
    note = "wifi failed";
    return false;
  }
  if (!fetchBaiduToken()) {
    note = "baidu token failed";
    return false;
  }
  petTm.net = millis() - tNet;

  // 静音裁剪:去掉首尾低于阈值的段,只留有效语音(+100ms 余量)
  uint32_t lo = 0, hi = samples;
  while (lo < hi && abs(petPcm[lo]) < 400) lo++;
  while (hi > lo + 1600 && abs(petPcm[hi - 1]) < 400) hi--;
  if (hi - lo < 3200) { lo = 0; hi = samples; }  // 太短就整段
  const uint32_t n = hi - lo;
  Serial.print("V: trimmed ");
  Serial.print(samples);
  Serial.print(" -> ");
  Serial.println(n);

  int errNo = baiduAsrOnce(lo, n, transcript, note);
  if (errNo == 110 || errNo == 111 || errNo == 3302) {  // token 失效/鉴权失败:重取一次再试
    Serial.print("V: token rejected err_no=");
    Serial.println(errNo);
    baiduToken = "";
    if (!fetchBaiduToken()) {
      note = "baidu token failed";
      return false;
    }
    errNo = baiduAsrOnce(lo, n, transcript, note);
  }
  if (errNo == -1) return false;
  if (errNo != 0 || !transcript.length()) {
    note = "asr rejected";
    return false;
  }

  if (strlen(DEEPSEEK_KEY) < 5) {
    return true;  // 只识别,无回答
  }
  return petAskLlm(transcript, reply, note);
}
```

- [ ] **Step 4: setup() 开机预连**

在 `pet/pet.ino` 的 `setup()` 中,把
```cpp
  petMicBegin();
  Serial.println("HELLO pet 1.0");
  enterIdle();
```
替换为
```cpp
  petMicBegin();
  Serial.println("HELLO pet 1.1");
  drawPet(0, F_NORMAL);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
  petNetWarmup();
#if PET_TEST_BAD_TOKEN
  baiduToken = "invalid_token_for_selftest_0000";
#endif
  enterIdle();
```

- [ ] **Step 5: 编译 + 真机测首轮耗时(需用户配合)**

Run: `bash tools/flash_and_log.sh pet 900`
Expected 日志:`V: warmup ok ms=…`。请用户**开机后第一次**按 B 说话,然后(后台)`bash tools/wait_log.sh 'T: ' 300`。
Expected: 首轮 `net=` 接近 0(< 100ms),不再包含连 WiFi 和取 token 的几秒。

- [ ] **Step 6: 测 token 失效自动重取(需用户配合)**

在 `pet/voice_pet.h` 顶部把 `#define PET_TEST_BAD_TOKEN 0` 临时改为 `1`,运行 `bash tools/flash_and_log.sh pet 600`,请用户说一句话,然后(后台)`bash tools/wait_log.sh 'token rejected|T: ' 300`。
Expected: 出现 `V: token rejected err_no=3302`(或 110/111),随后 `V: baidu err_no=0 transcript=…`,回答正常上屏。
若出现的是其他 err_no 且识别失败:把该值加进 Step 3 的判断条件后重测。
**测完把 `PET_TEST_BAD_TOKEN` 改回 0。**

- [ ] **Step 7: 测开机无网(需用户配合)**

把 `PET_TEST_OFFLINE` 临时改为 `1`,运行 `bash tools/flash_and_log.sh pet 600`。
Expected: 日志 `V: warmup failed ms=0`;屏幕进入待机(显示"按一下 B 说话");用户按 B 说话后照常联网、回答上屏(`net=` 为若干秒)。
**测完把 `PET_TEST_OFFLINE` 改回 0,再烧录一次正式版:`bash tools/flash_and_log.sh pet 60`。**

- [ ] **Step 8: 记录并提交**

`docs/perf-log.md` 追加 `### S2 开机预连(Task 5)`:记录首轮 `net` 前后对比。

```bash
git add pet/voice_pet.h pet/pet.ino docs/perf-log.md
git commit -m "perf(pet): warm up WiFi+token at boot, auto-refresh expired Baidu token"
```

---

### Task 6: 表情扩充 + 动画调度器 + 网络等待中的动画

**Files:**
- Modify: `pet/pet_face.h`(整体替换)
- Create: `pet/pet_anim.h`
- Modify: `pet/voice_pet.h`(三处插入 `petAnimTick()`)
- Modify: `pet/pet.ino`(整体替换)

**Interfaces:**
- Consumes: `petProcessVoice`、`petNetWarmup`、`petPrintTiming`(Task 1/5)
- Produces:
  - `enum Face { F_NORMAL, F_BLINK, F_HAPPY, F_SAD, F_LISTEN, F_THINK, F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SLEEPY, F_SLEEP, F_DIZZY, F_YAWN };`
  - `void drawPet(int f);`(**去掉了 dx 参数**)、`void drawFeatures(int f, int look = 0);`、`void drawEyesOnly(int f, int look);`、`void clearDeco();`、`void drawEmoteDeco(int f, int phase);`、`void drawSoundBars(int phase);`、`void drawThinkDots(int count);`、`void drawZzz(int phase);`、`void drawNote(int x, int y, uint16_t c);`
  - `enum Anim { A_NONE, A_IDLE, A_LISTEN, A_THINK, A_EMOTE, A_WAKE, A_DROWSY, A_SLEEP, A_DIZZY };`
  - `void petAnimSet(int anim, int face = F_NORMAL);`、`void petAnimTick();`、`int petAnimCurrent();`
  - pet.ino:`unsigned long showUntil;`、`void enterShow(int face, const String& t1, uint16_t c1, const String& t2, uint32_t durMs);`

- [ ] **Step 1: 替换 pet_face.h**

把 `pet/pet_face.h` 整个替换为:

```cpp
// ---- 宠物外观:几何像素风 + 表情 ----
// 依赖宿主先声明 Seeed_GFX display 并包含 cjk.h
// 整只宠物只在 drawPet() 里整画一次(状态切换时);表情/动画只用 drawFeatures/drawEyesOnly/装饰层局部重绘,防闪烁
#pragma once

enum Face {
  F_NORMAL, F_BLINK, F_HAPPY, F_SAD, F_LISTEN, F_THINK,
  F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SLEEPY, F_SLEEP, F_DIZZY, F_YAWN
};

const int CX = 160, CY = 152, R = 40;          // 脸中心与半径
const uint16_t C_BODY = 0xFDEF;                // 暖灰白
const uint16_t C_EDGE = 0x8410;                // 描边
const uint16_t C_BLUSH = 0xFB60;               // 腮红
const uint16_t C_BUBBLE = 0xFFFF;
const uint16_t C_WATER = 0x5DFF;               // 泪滴/声波
const uint16_t C_GOLD = 0xFEA0;                // 星光/音符

// 装饰层:脸两侧黑底区域,不与气泡(y<=116)、耳朵、提示区(y>=212)重叠
const int DECO_LX = CX - 84, DECO_RX = CX + 44, DECO_Y = CY - 36, DECO_W = 40, DECO_H = 56;

// look:眼睛整体水平偏移(张望/歪头)
void drawEyes(int look, int f, uint16_t color) {
  const int ex[2] = {CX + look - 19, CX + look + 13};
  const int ey = CY - 12;
  switch (f) {
    case F_BLINK:
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey + 3, 6, 3, color);
      break;
    case F_HAPPY:
      for (int i = 0; i < 2; i++) {
        display.drawLine(ex[i] - 1, ey + 4, ex[i] + 2, ey - 2, color);
        display.drawLine(ex[i] + 2, ey - 2, ex[i] + 5, ey + 4, color);
      }
      break;
    case F_EXCITED:  // 加粗的 ^ ^
      for (int i = 0; i < 2; i++) {
        for (int k = 0; k < 2; k++) {
          display.drawLine(ex[i] - 1, ey + 4 - k, ex[i] + 2, ey - 2 - k, color);
          display.drawLine(ex[i] + 2, ey - 2 - k, ex[i] + 5, ey + 4 - k, color);
        }
      }
      break;
    case F_SAD:
      for (int i = 0; i < 2; i++) display.drawLine(ex[i] - 1, ey - 2, ex[i] - 1, ey + 5, color);
      display.fillCircle(ex[0] + 1, ey + 8, 2, C_WATER);  // 泪滴(在眼区内,擦除时会一起擦掉)
      break;
    case F_THINK:
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey, 6, 3, color);
      break;
    case F_SURPRISED:
      for (int i = 0; i < 2; i++) {
        display.drawCircle(ex[i] + 3, ey + 2, 5, color);
        display.fillCircle(ex[i] + 3, ey + 2, 2, color);
      }
      break;
    case F_SHY:  // > <
      display.drawLine(ex[0], ey - 2, ex[0] + 5, ey + 2, color);
      display.drawLine(ex[0] + 5, ey + 2, ex[0], ey + 6, color);
      display.drawLine(ex[1] + 5, ey - 2, ex[1], ey + 2, color);
      display.drawLine(ex[1], ey + 2, ex[1] + 5, ey + 6, color);
      break;
    case F_CONFUSED:  // 一只睁一只眯
      display.fillRect(ex[0], ey - 3, 6, 10, color);
      display.fillRect(ex[1], ey + 2, 6, 3, color);
      break;
    case F_SLEEPY:  // 半眯
      for (int i = 0; i < 2; i++) {
        display.drawFastHLine(ex[i] - 1, ey + 1, 8, color);
        display.fillRect(ex[i], ey + 2, 6, 4, color);
      }
      break;
    case F_SLEEP:
    case F_YAWN:  // 闭眼 ︶
      for (int i = 0; i < 2; i++) {
        display.drawLine(ex[i] - 1, ey + 2, ex[i] + 2, ey + 5, color);
        display.drawLine(ex[i] + 2, ey + 5, ex[i] + 5, ey + 2, color);
      }
      break;
    case F_DIZZY:  // 蚊香眼
      for (int i = 0; i < 2; i++) {
        display.drawCircle(ex[i] + 3, ey + 2, 5, color);
        display.drawCircle(ex[i] + 3, ey + 2, 2, color);
      }
      break;
    default:  // 睁眼(F_NORMAL / F_LISTEN)
      for (int i = 0; i < 2; i++) display.fillRect(ex[i], ey - 3, 6, 10, color);
      break;
  }
}

void drawMouth(int f) {
  const int mx = CX, my = CY + 20;
  switch (f) {
    case F_HAPPY:
      display.drawLine(mx - 7, my - 2, mx, my + 3, TFT_BLACK);
      display.drawLine(mx, my + 3, mx + 7, my - 2, TFT_BLACK);
      break;
    case F_EXCITED:  // 张嘴大笑:下半圆 + 小舌头
      display.fillCircle(mx, my, 6, TFT_BLACK);
      display.fillRect(mx - 6, my - 6, 13, 6, C_BODY);
      display.fillCircle(mx, my + 3, 2, C_BLUSH);
      break;
    case F_SAD:
      display.drawLine(mx - 6, my + 2, mx, my - 3, TFT_BLACK);
      display.drawLine(mx, my - 3, mx + 6, my + 2, TFT_BLACK);
      break;
    case F_LISTEN:
      display.fillCircle(mx, my, 4, TFT_BLACK);
      break;
    case F_THINK:
      display.drawLine(mx - 6, my, mx + 6, my, TFT_BLACK);
      break;
    case F_SURPRISED:
      display.drawCircle(mx, my, 4, TFT_BLACK);
      display.drawCircle(mx, my, 3, TFT_BLACK);
      break;
    case F_SHY:
    case F_DIZZY:  // 波浪嘴
      display.drawLine(mx - 6, my, mx - 3, my - 2, TFT_BLACK);
      display.drawLine(mx - 3, my - 2, mx, my, TFT_BLACK);
      display.drawLine(mx, my, mx + 3, my - 2, TFT_BLACK);
      display.drawLine(mx + 3, my - 2, mx + 6, my, TFT_BLACK);
      break;
    case F_CONFUSED:
      display.drawLine(mx - 5, my + 1, mx + 5, my - 2, TFT_BLACK);
      break;
    case F_SLEEPY:
      display.drawFastHLine(mx - 3, my, 7, TFT_BLACK);
      break;
    case F_SLEEP:
      display.fillCircle(mx, my, 2, TFT_BLACK);
      break;
    case F_YAWN:
      display.fillCircle(mx, my + 1, 6, TFT_BLACK);
      break;
    default:
      display.fillCircle(mx - 1, my, 1, TFT_BLACK);
      display.fillCircle(mx + 3, my, 1, TFT_BLACK);
      break;
  }
}

// 只重画眼区(眨眼/张望/思考转眼)
void drawEyesOnly(int f, int look) {
  display.fillRect(CX - 26, CY - 17, 52, 17, C_BODY);
  drawEyes(look, f, TFT_BLACK);
}

// 重画五官(眼 + 嘴 + 腮红),不动轮廓
void drawFeatures(int f, int look = 0) {
  display.fillRect(CX - 26, CY - 17, 52, 17, C_BODY);  // 眼区
  display.fillRect(CX - 12, CY + 12, 25, 18, C_BODY);  // 嘴区
  display.fillCircle(CX - 27, CY + 8, 9, C_BODY);      // 腮红区
  display.fillCircle(CX + 27, CY + 8, 9, C_BODY);
  const int br = (f == F_SHY) ? 9 : 6;                  // 害羞:腮红变大
  display.fillCircle(CX - 27, CY + 8, br, C_BLUSH);
  display.fillCircle(CX + 27, CY + 8, br, C_BLUSH);
  drawEyes(look, f, TFT_BLACK);
  drawMouth(f);
}

// 整画:清屏 + 耳朵 + 脸 + 五官(只在状态切换时调用)
void drawPet(int f) {
  display.fillScreen(TFT_BLACK);
  display.fillTriangle(CX - 34, CY - 26, CX - 8, CY - 38, CX - 26, CY - 52, C_BODY);
  display.fillTriangle(CX + 8, CY - 38, CX + 34, CY - 26, CX + 26, CY - 52, C_BODY);
  display.drawLine(CX - 34, CY - 26, CX - 8, CY - 38, C_EDGE);
  display.drawLine(CX - 8, CY - 38, CX - 26, CY - 52, C_EDGE);
  display.drawLine(CX + 8, CY - 38, CX + 34, CY - 26, C_EDGE);
  display.drawLine(CX + 34, CY - 26, CX + 26, CY - 52, C_EDGE);
  display.fillCircle(CX, CY, R, C_BODY);
  display.drawCircle(CX, CY, R, C_EDGE);
  drawFeatures(f, 0);
}

// ---- 装饰层 ----
void clearDeco() {
  display.fillRect(DECO_LX, DECO_Y, DECO_W, DECO_H, TFT_BLACK);
  display.fillRect(DECO_RX, DECO_Y, DECO_W, DECO_H, TFT_BLACK);
}

void drawSparkle(int x, int y, int r, uint16_t c) {
  display.drawFastHLine(x - r, y, 2 * r + 1, c);
  display.drawFastVLine(x, y - r, 2 * r + 1, c);
  display.drawLine(x - r / 2, y - r / 2, x + r / 2, y + r / 2, c);
  display.drawLine(x - r / 2, y + r / 2, x + r / 2, y - r / 2, c);
}

void drawNote(int x, int y, uint16_t c) {  // ♪
  display.fillCircle(x, y, 3, c);
  display.drawFastVLine(x + 3, y - 12, 12, c);
  display.drawLine(x + 3, y - 12, x + 8, y - 8, c);
}

void drawGlyph(const char* s, int x, int y, int size, uint16_t c) {
  display.setTextSize(size);
  display.setTextColor(c);
  display.drawString(s, x, y);
}

void drawEmoteDeco(int f, int phase) {
  clearDeco();
  switch (f) {
    case F_EXCITED:  // 星光闪烁(两组位置交替)
      if (phase % 2 == 0) {
        drawSparkle(DECO_RX + 12, DECO_Y + 14, 5, C_GOLD);
        drawSparkle(DECO_LX + 26, DECO_Y + 36, 4, C_GOLD);
      } else {
        drawSparkle(DECO_RX + 24, DECO_Y + 36, 4, C_GOLD);
        drawSparkle(DECO_LX + 14, DECO_Y + 14, 5, C_GOLD);
      }
      break;
    case F_SURPRISED:
      drawGlyph("!", DECO_RX + 12, DECO_Y + 8, 3, TFT_YELLOW);
      break;
    case F_CONFUSED:
      drawGlyph("?", DECO_RX + 12, DECO_Y + 8, 3, C_WATER);
      break;
    default:
      break;
  }
}

void drawSoundBars(int phase) {  // 聆听:两侧声波条轮流起伏
  clearDeco();
  static const int H[3][3] = {{8, 16, 24}, {16, 24, 8}, {24, 8, 16}};
  for (int k = 0; k < 3; k++) {
    const int h = H[phase % 3][k];
    const int y = DECO_Y + 28 - h / 2;
    display.fillRect(DECO_RX + 4 + 10 * k, y, 5, h, C_WATER);
    display.fillRect(DECO_LX + 26 - 10 * k, y, 5, h, C_WATER);
  }
}

void drawThinkDots(int count) {  // 思考:右侧 1~3 个点
  display.fillRect(DECO_RX, DECO_Y + 34, DECO_W, 12, TFT_BLACK);
  for (int k = 0; k < count; k++) display.fillCircle(DECO_RX + 8 + 10 * k, DECO_Y + 40, 3, TFT_WHITE);
}

void drawZzz(int phase) {  // 睡觉:右侧 z 依次变大
  clearDeco();
  const int n = phase % 4;
  if (n >= 1) drawGlyph("z", DECO_RX + 4, DECO_Y + 38, 1, TFT_LIGHTGREY);
  if (n >= 2) drawGlyph("z", DECO_RX + 12, DECO_Y + 22, 2, TFT_LIGHTGREY);
  if (n >= 3) drawGlyph("Z", DECO_RX + 22, DECO_Y + 2, 3, TFT_LIGHTGREY);
}

void drawBubbleHead() {  // 气泡尾巴指向宠物
  display.fillTriangle(150, 104, 172, 104, 160, 116, C_BUBBLE);
}

void drawBubbleText(const String& t1, uint16_t c1, const String& t2, uint16_t c2) {
  display.fillRoundRect(14, 6, 292, 98, 10, C_BUBBLE);
  display.drawRoundRect(14, 6, 292, 98, 10, TFT_BLACK);
  drawBubbleHead();
  const int y = drawTextCJK(t1, 26, 14, 290, c1);
  if (t2.length()) {
    if (y < 56) {
      display.drawFastHLine(26, 52, 268, 0xBDF7);
      drawTextCJK(t2, 26, 58, 290, c2);
    } else {
      drawTextCJK(t2, 26, y + 2, 290, c2);
    }
  }
}
```

- [ ] **Step 2: 新建动画调度器**

Create `pet/pet_anim.h`:

```cpp
// ---- 动画调度器:非阻塞,按 millis() 推进,每次 tick 最多画一帧 ----
// loop() 与网络等待循环(readHttpBody / 上传 / 连 WiFi)都调用 petAnimTick(),阻塞请求期间画面照样动
#pragma once

enum Anim { A_NONE, A_IDLE, A_LISTEN, A_THINK, A_EMOTE, A_WAKE, A_DROWSY, A_SLEEP, A_DIZZY };

int animCur = A_NONE;
int animFace = F_NORMAL;
int animStep = 0;
unsigned long animNext = 0;

// A_IDLE 内部:眨眼 + 随机小动作(1=张望 2=哼歌 3=歪头)
bool idleBlinking = false;
unsigned long idleBlinkAt = 0;
int idleAct = 0;
int idleStep = 0;
unsigned long idleActAt = 0;

void petAnimSet(int anim, int face = F_NORMAL) {
  animCur = anim;
  animFace = face;
  animStep = 0;
  animNext = 0;  // 下一次 tick 立即画第一帧
  const unsigned long now = millis();
  idleBlinking = false;
  idleBlinkAt = now + random(2500, 5000);
  idleAct = 0;
  idleStep = 0;
  idleActAt = now + random(8000, 20000);
}

int petAnimCurrent() { return animCur; }

void endIdleAct(unsigned long now) {
  idleAct = 0;
  idleStep = 0;
  idleActAt = now + random(8000, 20000);
  animNext = now + 100;
}

void tickIdle(unsigned long now) {
  if (animStep == 0) {  // 进入待机:复位五官与装饰
    clearDeco();
    drawFeatures(F_NORMAL);
    animStep = 1;
  }
  if (idleAct == 1) {  // 张望:左 → 中 → 右 → 中
    static const int LOOK[4] = {-4, 0, 4, 0};
    drawEyesOnly(F_NORMAL, LOOK[idleStep]);
    if (++idleStep >= 4) endIdleAct(now);
    else animNext = now + 350;
    return;
  }
  if (idleAct == 2) {  // 哼歌:开心嘴 + ♪ 从右侧往上飘
    if (idleStep == 0) drawFeatures(F_HAPPY);
    clearDeco();
    if (idleStep < 4) drawNote(DECO_RX + 10 + 4 * idleStep, DECO_Y + 48 - 10 * idleStep, C_GOLD);
    if (++idleStep >= 5) {
      drawFeatures(F_NORMAL);
      endIdleAct(now);
    } else {
      animNext = now + 300;
    }
    return;
  }
  if (idleAct == 3) {  // 歪头:眼睛偏一侧 + 疑惑嘴,停 1 秒
    if (idleStep == 0) {
      drawFeatures(F_CONFUSED, 3);
      idleStep = 1;
      animNext = now + 1000;
      return;
    }
    drawFeatures(F_NORMAL);
    endIdleAct(now);
    return;
  }
  if (idleBlinking) {  // 眨眼的第二帧:睁眼
    drawEyesOnly(F_NORMAL, 0);
    idleBlinking = false;
    idleBlinkAt = now + random(2500, 5000);
  } else if (now >= idleActAt) {
    idleAct = random(1, 4);
    idleStep = 0;
    animNext = now;
    return;
  } else if (now >= idleBlinkAt) {
    drawEyesOnly(F_BLINK, 0);
    idleBlinking = true;
    animNext = now + 160;
    return;
  }
  animNext = (idleBlinkAt < idleActAt) ? idleBlinkAt : idleActAt;
}

void petAnimTick() {
  const unsigned long now = millis();
  if (animCur == A_NONE || now < animNext) return;
  switch (animCur) {
    case A_IDLE:
      tickIdle(now);
      break;
    case A_LISTEN:
      if (animStep == 0) drawFeatures(F_LISTEN);
      drawSoundBars(animStep);
      animStep++;
      animNext = now + 150;
      break;
    case A_THINK: {  // 眼睛左右看 + 三个点循环
      static const int LOOK[4] = {0, -4, 0, 4};
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_THINK);
      }
      drawEyesOnly(F_NORMAL, LOOK[animStep % 4]);
      drawThinkDots(animStep % 3 + 1);
      animStep++;
      animNext = now + 300;
      break;
    }
    case A_EMOTE:  // 表情 + 装饰;兴奋时星光闪烁,其余静止
      if (animStep == 0) drawFeatures(animFace);
      drawEmoteDeco(animFace, animStep);
      animStep++;
      animNext = now + (animFace == F_EXCITED ? 400 : 60000);
      break;
    case A_WAKE: {  // 慢慢睁眼,结束后自动转待机
      static const int SEQ[4] = {F_SLEEP, F_SLEEPY, F_SLEEPY, F_NORMAL};
      if (animStep == 0) clearDeco();
      drawEyesOnly(SEQ[animStep], 0);
      if (++animStep >= 4) {
        petAnimSet(A_IDLE);
        return;
      }
      animNext = now + 250;
      break;
    }
    case A_DROWSY:  // 半眯眼;每 6 秒打一次哈欠(0.8 秒)
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_SLEEPY);
        animStep = 1;
        animNext = now + 6000;
      } else if (animStep == 1) {
        drawFeatures(F_YAWN);
        animStep = 2;
        animNext = now + 800;
      } else {
        drawFeatures(F_SLEEPY);
        animStep = 1;
        animNext = now + 6000;
      }
      break;
    case A_SLEEP:
      if (animStep == 0) drawFeatures(F_SLEEP);
      drawZzz(animStep);
      animStep++;
      animNext = now + 500;
      break;
    case A_DIZZY:  // 蚊香眼左右晃
      if (animStep == 0) {
        clearDeco();
        drawFeatures(F_DIZZY);
      }
      drawEyesOnly(F_DIZZY, (animStep % 2) ? 2 : -2);
      animStep++;
      animNext = now + 100;
      break;
    default:
      break;
  }
}
```

- [ ] **Step 3: 网络等待循环里调用 petAnimTick**

在 `pet/voice_pet.h`:
1. `b64OutPush` 中,把
```cpp
    client.write((const uint8_t*)b64Out, b64OutLen);
    b64OutLen = 0;
  }
  memcpy(b64Out + b64OutLen, g, 4);
```
替换为
```cpp
    client.write((const uint8_t*)b64Out, b64OutLen);
    b64OutLen = 0;
    petAnimTick();  // 每写出 1KB 让动画走一帧
  }
  memcpy(b64Out + b64OutLen, g, 4);
```
2. `readHttpBody` 循环末尾,把
```cpp
    if (millis() - start > maxWaitMs) break;
    delay(5);
```
替换为
```cpp
    if (millis() - start > maxWaitMs) break;
    petAnimTick();
    delay(5);
```
3. `wifiPetConnected` 中,把
```cpp
      if (millis() - start > 15000) break;
      delay(500);
```
替换为
```cpp
      if (millis() - start > 15000) break;
      for (int k = 0; k < 50; k++) {  // 等 500ms,期间动画照常
        petAnimTick();
        delay(10);
      }
```

- [ ] **Step 4: 替换 pet.ino**

把 `pet/pet.ino` 整个替换为:

```cpp
// 小维(Wio)—— AI 电子桌宠
// 开机即宠物:待机会眨眼、张望、哼歌;按一下 B 开始听,说完自动发送;
// 语音 → 百度ASR → DeepSeek → 对话气泡(汉字);摇杆左右 = 摸头。

#include <Arduino.h>
#include <Seeed_GFX.h>

Seeed_GFX display(Seeed_Product::Wio_Terminal);
#include "cjk.h"
#include "pet_face.h"
#include "pet_anim.h"

const int PIN_KEY_B = WIO_KEY_B;
const int PIN_KEY_C = WIO_KEY_C;
const int PIN_JOY_L = WIO_5S_LEFT;
const int PIN_JOY_R = WIO_5S_RIGHT;

void beep(int freq, int dur) {
  tone(WIO_BUZZER, freq, dur);
}

#include "voice_pet.h"  // 语音链路(麦克风 DMA/百度ASR/DeepSeek)

// ============================================================
// 状态机
// ============================================================

enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW };
PetState state = ST_IDLE;
unsigned long stateStart = 0;
unsigned long showUntil = 0;
uint32_t recSamples = 0;

void drawIdleHint() {
  drawTextCJK("按一下 B 说话,说完我自己停", 62, 220, 320, TFT_DARKGREY);
}

void enterIdle() {
  state = ST_IDLE;
  stateStart = millis();
  drawPet(F_NORMAL);
  drawIdleHint();
  petAnimSet(A_IDLE);
}

// 显示一段表情 + 气泡,durMs 后自动回待机(期间按键也可提前返回)
void enterShow(int face, const String& t1, uint16_t c1, const String& t2, uint32_t durMs) {
  state = ST_SHOW;
  stateStart = millis();
  showUntil = millis() + durMs;
  drawPet(face);
  if (t1.length()) drawBubbleText(t1, c1, t2, TFT_BLACK);
  petAnimSet(A_EMOTE, face);
}

void setup() {
  pinMode(PIN_KEY_B, INPUT_PULLUP);
  pinMode(PIN_KEY_C, INPUT_PULLUP);
  pinMode(PIN_JOY_L, INPUT_PULLUP);
  pinMode(PIN_JOY_R, INPUT_PULLUP);

  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2500) {
  }

  if (!display.begin()) {
    Serial.print("ERR display: ");
    Serial.println(display.lastResult().message);
    while (true) delay(1000);
  }
  randomSeed(analogRead(A0) ^ micros());
  petMicBegin();
  Serial.println("HELLO pet 1.2");
  drawPet(F_SLEEP);
  drawTextCJK("小维醒来中…正在连网", 84, 220, 320, TFT_DARKGREY);
  petAnimSet(A_WAKE);
  petNetWarmup();
#if PET_TEST_BAD_TOKEN
  baiduToken = "invalid_token_for_selftest_0000";
#endif
  enterIdle();
}

bool pressed(int pin) {
  static unsigned long lastMs = 0;
  if (digitalRead(pin) != LOW) return false;
  if (millis() - lastMs < 200) return false;
  lastMs = millis();
  return true;
}

bool anyKeyDown() {
  return digitalRead(PIN_KEY_B) == LOW || digitalRead(PIN_KEY_C) == LOW ||
         digitalRead(PIN_JOY_L) == LOW || digitalRead(PIN_JOY_R) == LOW;
}

void loop() {
  petAnimTick();
  switch (state) {
    case ST_IDLE: {
      if (pressed(PIN_JOY_L) || pressed(PIN_JOY_R)) {  // 摸头
        beep(1568, 80);
        enterShow(F_HAPPY, "", TFT_BLACK, "", 1200);
        break;
      }
      if (pressed(PIN_KEY_B)) {
        petRecStart();
        state = ST_RECORD;
        stateStart = millis();
        drawPet(F_LISTEN);
        drawBubbleText("在听…说完我会自己停", TFT_BLACK, "", TFT_BLACK);
        petAnimSet(A_LISTEN);
        beep(988, 60);
      }
      break;
    }

    case ST_RECORD: {
      uint32_t samples = 0, hint = 0;
      const int st = petRecPoll(samples, hint);
      if (st == 2) {  // 超时没说话
        beep(196, 250);
        enterShow(F_SAD, "你还没说话呢~", TFT_BLACK, "按一下 B 再开口就好", 15000);
        break;
      }
      if (st == 1) {  // 录完
        recSamples = samples;
        beep(880, 50);
        state = ST_THINK;
        stateStart = millis();
        drawPet(F_THINK);
        drawBubbleText("让我想想…", TFT_BLACK, "", TFT_BLACK);
        petAnimSet(A_THINK);
      }
      break;
    }

    case ST_THINK: {
      // 识别 + 回答(阻塞数秒;等待期间 petAnimTick 由网络循环驱动)
      String t, r, note;
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, t, r, note);
      petPrintTiming(millis() - tProc);
      if (ok) {
        beep(1319, 90);
        enterShow(F_HAPPY, "你:" + t, 0x8410,
                  r.length() ? "小维:" + r : String("(还没配置 DeepSeek Key,我不会说话呀)"), 15000);
      } else {
        beep(196, 250);
        enterShow(F_SAD, "呜…出问题了", 0x8410, note, 15000);
      }
      break;
    }

    case ST_SHOW: {
      const bool keyAfterGrace = millis() - stateStart > 400 && anyKeyDown();
      if (millis() > showUntil || keyAfterGrace) {
        while (anyKeyDown()) petAnimTick();  // 等松手,避免同一次按键在待机里又触发
        enterIdle();
      }
      break;
    }
  }
}
```

注:`pet.ino` 不再定义 `blinkEyes`、`lastBlink`、`showFace`、`showT1/2`、`anyKeyPressed`;`drawPet` 现在只有一个参数。

- [ ] **Step 5: 编译**

Run: `"/c/Program Files/Arduino CLI/arduino-cli.exe" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path build/pet pet 2>&1 | tail -3`
Expected: `Sketch uses … bytes`,无 `error`。若报 `drawString` 签名不匹配,改用 `display.drawString(String(s), x, y)`。

- [ ] **Step 6: 真机目视验收(需用户配合)**

Run: `bash tools/flash_and_log.sh pet 900`。请用户观察并逐条确认:
1. 开机:闭眼 → 慢慢睁眼,同时提示"小维醒来中…"
2. 待机 1 分钟内:随机眨眼;至少看到一次张望/哼歌(♪ 上飘)/歪头之一
3. 按 B:两侧蓝色声波条起伏
4. 说完:眼睛左右看 + 右侧"· ·· ···"循环,**整个等待过程中画面一直在动**(TLS 握手时短暂停顿可接受)
5. 回答:开心脸 + 气泡;15 秒或按键回待机
6. 摇杆左右:开心脸约 1 秒
7. 全程无整屏闪烁、动画不覆盖气泡

任何一条不符:记录现象,修复后重测;全部通过再继续。

- [ ] **Step 7: 提交**

```bash
git add pet/pet_face.h pet/pet_anim.h pet/voice_pet.h pet/pet.ino
git commit -m "feat(pet): 14 expressions, non-blocking animation scheduler, animate during network waits"
```

---

### Task 7: 回答带情绪 —— 提示词 + 标签解析 + 表情映射 + 小维口吻报错

**Files:**
- Modify: `pet/voice_pet.h`(`PET_SYSTEM_PROMPT`、`petAskLlm`、`petProcessVoice` 签名)
- Modify: `pet/pet.ino`(`ST_THINK` 分支、新增 `EMO_FACE`、`friendlyNote`)

**Interfaces:**
- Consumes: `parseEmotionTag`、`Emotion`(Task 3);`enterShow`(Task 6)
- Produces:
  - `bool petAskLlm(const String& question, String& reply, int& emotion, String& note);`
  - `bool petProcessVoice(uint32_t samples, String& transcript, String& reply, int& emotion, String& note);`
  - pet.ino:`const int EMO_FACE[6]`、`String friendlyNote(const String& note);`

- [ ] **Step 1: 改提示词**

把 `pet/voice_pet.h` 中的 `PET_SYSTEM_PROMPT` 定义替换为:

```cpp
const char* const PET_SYSTEM_PROMPT =
    "你是电子桌宠\"小维\",性格活泼元气,说话简短、口语化、爱用感叹号。"
    "回答必须以情绪标签开头,格式如 [开心],情绪只能从 开心/兴奋/惊讶/害羞/疑惑/难过 里选一个;"
    "标签后直接是回答正文,用简体中文,45字以内,不要任何其他前缀或解释。";
```

- [ ] **Step 2: petAskLlm 解析情绪**

在 `pet/voice_pet.h`:
1. `bool petAskLlm(const String& question, String& reply, String& note) {` 改为
```cpp
bool petAskLlm(const String& question, String& reply, int& emotion, String& note) {
```
2. 把
```cpp
  reply = String(ldoc["choices"][0]["message"]["content"] | "");
  Serial.print("V: reply=");
  Serial.println(reply);
  if (!reply.length()) {
```
替换为
```cpp
  reply = String(ldoc["choices"][0]["message"]["content"] | "");
  Serial.print("V: reply=");
  Serial.println(reply);
  size_t textStart = 0;
  emotion = parseEmotionTag(reply.c_str(), reply.length(), &textStart);
  reply = reply.substring(textStart);  // 标签不上屏
  if (!reply.length()) {  // 空回复,或只给了标签没有正文
```

- [ ] **Step 3: petProcessVoice 透传情绪**

在 `pet/voice_pet.h`:
1. `bool petProcessVoice(uint32_t samples, String& transcript, String& reply, String& note) {` 改为
```cpp
bool petProcessVoice(uint32_t samples, String& transcript, String& reply, int& emotion, String& note) {
```
2. 在函数体开头 `note = "";` 之后加 `emotion = EMO_HAPPY;`
3. 最后一行 `return petAskLlm(transcript, reply, note);` 改为 `return petAskLlm(transcript, reply, emotion, note);`

- [ ] **Step 4: pet.ino 映射表情 + 小维口吻报错**

在 `pet/pet.ino` 的 `void drawIdleHint() {` **之前**插入:

```cpp
// Emotion(pet_logic.h)→ 表情;顺序必须与 enum Emotion 一致:开心 兴奋 惊讶 害羞 疑惑 难过
const int EMO_FACE[6] = {F_HAPPY, F_EXCITED, F_SURPRISED, F_SHY, F_CONFUSED, F_SAD};

// 把技术性 note 翻成小维口吻(原 note 仍显示在第二行,方便排查)
String friendlyNote(const String& note) {
  if (note.startsWith("wifi")) return "我连不上 WiFi 啦…";
  if (note.startsWith("asr rejected")) return "没听清,再说一遍嘛~";
  if (note.startsWith("asr")) return "耳朵(语音识别)出故障了";
  if (note.startsWith("baidu")) return "语音服务登录失败了";
  if (note.startsWith("llm")) return "脑袋(DeepSeek)卡住了";
  return "出了点小状况";
}
```

把 `case ST_THINK:` 整个分支替换为:

```cpp
    case ST_THINK: {
      // 识别 + 回答(阻塞数秒;等待期间 petAnimTick 由网络循环驱动)
      String t, r, note;
      int emo = EMO_HAPPY;
      const uint32_t tProc = millis();
      const bool ok = petProcessVoice(recSamples, t, r, emo, note);
      petPrintTiming(millis() - tProc);
      if (ok) {
        beep(1319, 90);
        const int face = (emo >= 0 && emo < 6) ? EMO_FACE[emo] : F_HAPPY;
        enterShow(face, "你:" + t, 0x8410,
                  r.length() ? "小维:" + r : String("(还没配置 DeepSeek Key,我不会说话呀)"), 15000);
      } else {
        beep(196, 250);
        enterShow(F_SAD, "呜…" + friendlyNote(note), 0x8410, note, 15000);
      }
      break;
    }
```

- [ ] **Step 5: 编译**

Run: `"/c/Program Files/Arduino CLI/arduino-cli.exe" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path build/pet pet 2>&1 | tail -3`
Expected: 无 `error`。

- [ ] **Step 6: 真机验收情绪(需用户配合)**

Run: `bash tools/flash_and_log.sh pet 900`。请用户依次说(引导出不同情绪):
- "我今天中彩票了!"(期望 兴奋/惊讶)
- "你好可爱呀"(期望 害羞)
- "我失恋了"(期望 难过)
- "一加一等于几"(期望 开心/疑惑)

然后(后台)`bash tools/wait_log.sh 'V: reply=' 600`。
Expected: 每条 `V: reply=` 以 `[情绪]` 或 `【情绪】` 开头;屏幕气泡里**不出现**标签;表情与情绪对应(兴奋有星光、惊讶有 !、疑惑有 ?、害羞腮红变大、难过有泪滴)。若模型持续不给标签,检查提示词是否生效(`V: reply=` 原文)。

- [ ] **Step 7: 提交**

```bash
git add pet/voice_pet.h pet/pet.ino
git commit -m "feat(pet): emotion-tagged replies drive expressions; friendly error text"
```

---

### Task 8: 犯困、睡觉、唤醒 + 背光调暗

**Files:**
- Modify: `pet/pet.ino`(新增 `ST_SLEEP`、`lastInteract`、`setBacklight`、`enterSleep`、`wakeUp`)

**Interfaces:**
- Consumes: `A_DROWSY`、`A_SLEEP`、`A_WAKE`、`petAnimCurrent()`(Task 6)
- Produces:
  - `enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW, ST_SLEEP };`
  - `unsigned long lastInteract;`、`void enterSleep();`、`void wakeUp();`、`void setBacklight(bool dim);`
  - 常量 `PET_DROWSY_MS = 180000`、`PET_SLEEP_MS = 300000`、`PET_DIM_LEVEL = 40`

- [ ] **Step 1: 状态与常量**

在 `pet/pet.ino`:
1. `enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW };` 改为
```cpp
enum PetState { ST_IDLE, ST_RECORD, ST_THINK, ST_SHOW, ST_SLEEP };
```
2. 在 `uint32_t recSamples = 0;` 之后插入:
```cpp
unsigned long lastInteract = 0;              // 最近一次有人互动(按键/摸头/拿起)
const unsigned long PET_DROWSY_MS = 180000;  // 3 分钟没人理 → 犯困
const unsigned long PET_SLEEP_MS = 300000;   // 5 分钟 → 睡觉
const int PET_DIM_LEVEL = 40;                // 睡觉时背光 PWM(0-255)

// 背光:若 LCD_BACKLIGHT 不支持 PWM,analogWrite 会退化成全亮/全灭 —— 实测见 Task 8 Step 4
void setBacklight(bool dim) {
  analogWrite(LCD_BACKLIGHT, dim ? PET_DIM_LEVEL : 255);
}
```

- [ ] **Step 2: 睡觉 / 唤醒函数**

在 `enterShow` 函数之后插入:

```cpp
void enterSleep() {
  state = ST_SLEEP;
  stateStart = millis();
  drawPet(F_SLEEP);
  petAnimSet(A_SLEEP);
  setBacklight(true);
}

void wakeUp() {
  setBacklight(false);
  lastInteract = millis();
  state = ST_IDLE;
  stateStart = millis();
  drawPet(F_SLEEP);
  drawIdleHint();
  petAnimSet(A_WAKE);  // 睁眼动画结束后自动转 A_IDLE
}
```

- [ ] **Step 3: 接入状态机**

在 `pet/pet.ino`:
1. `setup()` 末尾 `enterIdle();` 之前加 `lastInteract = millis();`
2. `case ST_IDLE: {` 之后、摸头判断之前插入:
```cpp
      const unsigned long idleFor = millis() - lastInteract;
      if (idleFor > PET_SLEEP_MS) {
        enterSleep();
        break;
      }
      if (idleFor > PET_DROWSY_MS && petAnimCurrent() == A_IDLE) petAnimSet(A_DROWSY);
      if (pressed(PIN_KEY_C)) {  // C 键:叫醒犯困的小维
        lastInteract = millis();
        petAnimSet(A_IDLE);
        break;
      }
```
3. 摸头分支 `beep(1568, 80);` 之前加 `lastInteract = millis();`
4. B 键分支 `petRecStart();` 之前加 `lastInteract = millis();`
5. 在 `case ST_SHOW:` 整个分支之后(`switch` 结束前)加入:
```cpp
    case ST_SLEEP: {
      if (anyKeyDown()) {
        wakeUp();
        while (anyKeyDown()) petAnimTick();  // 等松手,避免叫醒的那一下又触发录音
      }
      break;
    }
```

- [ ] **Step 4: 临时缩短时间做真机验收(需用户配合)**

临时把 `PET_DROWSY_MS` 改为 `20000`、`PET_SLEEP_MS` 改为 `40000`,运行 `bash tools/flash_and_log.sh pet 600`。请用户不碰板子,观察:
1. 约 20 秒:半眯眼,每 6 秒打一次哈欠
2. 约 40 秒:闭眼 + Zzz 依次变大;**屏幕变暗**
3. 按任意键:亮度恢复,慢慢睁眼回待机;刚才那一下**不会**触发录音

若第 2 步屏幕**完全黑掉**(背光不支持 PWM):把 `setBacklight` 函数体改为 `(void)dim;  // 背光不支持 PWM:睡觉时保持亮度`,重测确认睡觉画面可见。
**测完把两个常量改回 `180000` / `300000`。**

- [ ] **Step 5: 编译 + 提交**

Run: 编译命令(同 Task 7 Step 5),Expected 无 `error`。

```bash
git add pet/pet.ino
git commit -m "feat(pet): drowsy after 3min, sleep after 5min with dimmed backlight, wake on key"
```

---

### Task 9: 传感器 —— 关灯睡觉、亮灯醒、摇晃晕、拿起醒

**Files:**
- Modify: `pet/pet_logic.h`(追加 `LightDetector`、`MotionDetector`)
- Modify: `tests/pet_selftest/pet_selftest.ino`(追加 `testSense`)
- Create: `pet/pet_sense.h`
- Modify: `pet/pet.ino`(`handleSense`、`startDizzy`、初始化)

**Interfaces:**
- Consumes: `enterSleep`、`wakeUp`、`lastInteract`(Task 8)、`A_DIZZY`(Task 6)
- Produces:
  - `struct LightDetector { LightDetector(int darkTh, int lightTh, uint32_t darkHoldMs, uint32_t lightHoldMs); int update(int v, uint32_t now); bool isDark; };` —— `update` 返回 0 无 / 1 刚变暗 / 2 刚变亮
  - `enum MotionEvent { MOTION_NONE = 0, MOTION_SHAKE = 1, MOTION_PICKUP = 2 };`
  - `struct MotionDetector { MotionDetector(int shakeMg, int pickupMg, uint32_t stillMs); int update(int x, int y, int z, uint32_t now); };`(单位 mg)
  - `enum SenseEvent { SE_NONE, SE_DARK, SE_LIGHT, SE_SHAKE, SE_PICKUP };`、`void petSenseBegin();`、`int petSensePoll();`
  - pet.ino:`void handleSense();`、`void startDizzy();`

- [ ] **Step 1: 写失败的测试**

在 `tests/pet_selftest/pet_selftest.ino` 的 `void printSummary()` 之前插入:

```cpp
void testSense() {
  // 光线:暗阈值 60,亮阈值 120;变暗需持续 10s,变亮需持续 2s
  LightDetector ld(60, 120, 10000, 2000);
  check(ld.update(30, 0) == 0, "light: dark pending");
  check(ld.update(30, 9999) == 0, "light: dark not yet");
  check(ld.update(30, 10000) == 1, "light: became dark");
  check(ld.update(100, 11000) == 0, "light: hysteresis keeps dark");
  check(ld.update(200, 12000) == 0, "light: bright pending");
  check(ld.update(30, 13000) == 0, "light: flicker resets");
  check(ld.update(200, 14000) == 0, "light: bright pending again");
  check(ld.update(200, 16000) == 2, "light: became bright");

  // 动作:摇晃阈值 800mg,拿起阈值 300mg,静止 3s 才算放稳
  MotionDetector md(800, 300, 3000);
  int ev = 0;
  for (uint32_t t = 0; t <= 3500; t += 50) ev |= md.update(0, 0, 1000, t);
  check(ev == MOTION_NONE, "motion: still no event");
  check(md.update(300, 0, 900, 3550) == MOTION_PICKUP, "motion: pickup after still");
  check(md.update(300, 0, 900, 3600) == MOTION_NONE, "motion: no repeat pickup");
  check(md.update(0, 0, 2000, 5000) == MOTION_NONE, "motion: shake hit 1");
  check(md.update(0, 0, 2000, 5100) == MOTION_NONE, "motion: shake hit 2");
  check(md.update(0, 0, 2000, 5200) == MOTION_SHAKE, "motion: shake hit 3");
  check(md.update(0, 0, 2000, 5300) == MOTION_NONE, "motion: shake cooldown");
  check(md.update(0, 0, 2000, 5400) == MOTION_NONE, "motion: shake cooldown 2");
  md.update(0, 0, 2000, 14000);
  md.update(0, 0, 2000, 14100);
  check(md.update(0, 0, 2000, 14200) == MOTION_SHAKE, "motion: shake again after cooldown");
  MotionDetector md2(800, 300, 3000);
  check(md2.update(0, 0, 1000, 0) == MOTION_NONE, "motion: fresh");
  check(md2.update(400, 0, 1000, 100) == MOTION_NONE, "motion: move without prior still");
}
```

在 `setup()` 中 `testEmotion();` 之后加 `testSense();`。

在 `pet/pet_logic.h` 末尾追加桩:

```cpp

struct LightDetector {
  bool isDark;
  LightDetector(int, int, uint32_t, uint32_t) : isDark(false) {}
  int update(int, uint32_t) { return 0; }
};

enum MotionEvent { MOTION_NONE = 0, MOTION_SHAKE = 1, MOTION_PICKUP = 2 };

struct MotionDetector {
  MotionDetector(int, int, uint32_t) {}
  int update(int, int, int, uint32_t) { return MOTION_NONE; }
};
```
并在 `pet/pet_logic.h` 顶部 include 区加 `#include <stdint.h>`。

- [ ] **Step 2: 跑自检确认失败**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST FAIL`,含 `FAIL light: became dark`、`FAIL motion: pickup after still` 等。

- [ ] **Step 3: 写实现**

把 Step 1 追加的两个桩结构体(保留 `enum MotionEvent`)替换为:

```cpp
// 光线判定:双阈值迟滞 + 持续时间。暗于 darkTh 持续 darkHoldMs → 1(变暗);亮于等于 lightTh 持续 lightHoldMs → 2(变亮)
struct LightDetector {
  int darkTh, lightTh;
  uint32_t darkHoldMs, lightHoldMs;
  bool isDark, pending;
  uint32_t since;
  LightDetector(int darkTh_, int lightTh_, uint32_t darkHoldMs_, uint32_t lightHoldMs_)
      : darkTh(darkTh_), lightTh(lightTh_), darkHoldMs(darkHoldMs_), lightHoldMs(lightHoldMs_),
        isDark(false), pending(false), since(0) {}
  int update(int v, uint32_t now) {
    const bool wantDark = isDark ? (v < lightTh) : (v < darkTh);
    if (wantDark == isDark) {  // 回到当前状态:取消待定(防闪烁)
      pending = false;
      return 0;
    }
    if (!pending) {
      pending = true;
      since = now;
      return 0;
    }
    if (now - since >= (wantDark ? darkHoldMs : lightHoldMs)) {
      isDark = wantDark;
      pending = false;
      return isDark ? 1 : 2;
    }
    return 0;
  }
};

// 动作判定(输入三轴加速度,单位 mg):
// 摇晃:|a| 偏离 1g 超过 shakeMg 记一次,1 秒内 3 次触发;触发后 8 秒冷却(晕 3s + 冷却 5s)
// 拿起:先静止 stillMs,之后三轴变化之和超过 pickupMg
struct MotionDetector {
  int shakeMg, pickupMg;
  uint32_t stillMs;
  int hits;
  uint32_t hitWindowStart, cooldownUntil;
  int refX, refY, refZ;
  uint32_t stillSince;
  bool still;
  MotionDetector(int shakeMg_, int pickupMg_, uint32_t stillMs_)
      : shakeMg(shakeMg_), pickupMg(pickupMg_), stillMs(stillMs_), hits(0), hitWindowStart(0),
        cooldownUntil(0), refX(0), refY(0), refZ(1000), stillSince(0), still(false) {}
  int update(int x, int y, int z, uint32_t now) {
    const long mag2 = (long)x * x + (long)y * y + (long)z * z;
    const long hiMag = 1000L + shakeMg;
    const long loMag = (1000L - shakeMg) > 0 ? (1000L - shakeMg) : 0;
    if (mag2 > hiMag * hiMag || mag2 < loMag * loMag) {
      if (hits == 0 || now - hitWindowStart > 1000) {
        hits = 0;
        hitWindowStart = now;
      }
      hits++;
      still = false;
      stillSince = now;
      refX = x; refY = y; refZ = z;
      if (hits >= 3 && now >= cooldownUntil) {
        hits = 0;
        cooldownUntil = now + 8000;
        return MOTION_SHAKE;
      }
      return MOTION_NONE;
    }
    const long d = labs((long)x - refX) + labs((long)y - refY) + labs((long)z - refZ);
    if (d < pickupMg / 3) {  // 基本没动:累计静止
      if (!still && now - stillSince >= stillMs) still = true;
      return MOTION_NONE;
    }
    const bool fire = still && d > pickupMg;
    still = false;
    stillSince = now;
    refX = x; refY = y; refZ = z;
    return fire ? MOTION_PICKUP : MOTION_NONE;
  }
};
```

- [ ] **Step 4: 跑自检确认通过**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST PASS 51/51`。

- [ ] **Step 5: 安装 IMU 库**

Run: `"/c/Program Files/Arduino CLI/arduino-cli.exe" lib install "Grove-3-Axis-Digital-Accelerometer-2g-to-16g-LIS3DHTR"`
Expected: `Installed Grove-3-Axis-Digital-Accelerometer-2g-to-16g-LIS3DHTR@…`

- [ ] **Step 6: 新建 pet_sense.h**

Create `pet/pet_sense.h`:

```cpp
// ---- 传感器:光线(关灯睡觉)+ IMU(摇晃/拿起);判定逻辑在 pet_logic.h ----
// 只在 IDLE / SHOW / SLEEP 状态调用 petSensePoll(录音时不碰 ADC,避免干扰麦克风 DMA)
#pragma once
#include <LIS3DHTR.h>

enum SenseEvent { SE_NONE, SE_DARK, SE_LIGHT, SE_SHAKE, SE_PICKUP };

// 光线阈值(0-1023,越小越暗):把 PET_SENSE_DEBUG 设 1,看日志 "S: light=" 实测后改
const int PET_DARK_TH = 60;
const int PET_LIGHT_TH = 120;
#ifndef PET_SENSE_DEBUG
#define PET_SENSE_DEBUG 0  // 1 = 每 2 秒打印光线与加速度,用于标定
#endif

LIS3DHTR<TwoWire> lis;
bool imuOk = false;
LightDetector lightDet(PET_DARK_TH, PET_LIGHT_TH, 10000, 2000);
MotionDetector motionDet(800, 300, 3000);
unsigned long lightNext = 0, imuNext = 0, senseDbgNext = 0;
long lightAvg = -1;
int lastAx = 0, lastAy = 0, lastAz = 0;

void petSenseBegin() {
  pinMode(WIO_LIGHT, INPUT);
  lis.begin(Wire1);
  imuOk = lis.isConnection();
  if (imuOk) {
    lis.setOutputDataRate(LIS3DHTR_DATARATE_50HZ);
    lis.setFullScaleRange(LIS3DHTR_RANGE_2G);
  }
  Serial.println(imuOk ? "S: imu ok" : "S: imu FAIL (shake/pickup disabled)");
}

// 非阻塞:到采样时间才读;每次最多返回一个事件
int petSensePoll() {
  const unsigned long now = millis();
  int ev = SE_NONE;
  if (now >= lightNext) {
    lightNext = now + 500;
    const int raw = analogRead(WIO_LIGHT);
    lightAvg = (lightAvg < 0) ? raw : (lightAvg * 3 + raw) / 4;
    const int r = lightDet.update((int)lightAvg, (uint32_t)now);
    if (r == 1) ev = SE_DARK;
    else if (r == 2) ev = SE_LIGHT;
  }
  if (imuOk && now >= imuNext) {
    imuNext = now + 50;
    lastAx = (int)(lis.getAccelerationX() * 1000);
    lastAy = (int)(lis.getAccelerationY() * 1000);
    lastAz = (int)(lis.getAccelerationZ() * 1000);
    const int m = motionDet.update(lastAx, lastAy, lastAz, (uint32_t)now);
    if (m == MOTION_SHAKE) ev = SE_SHAKE;
    else if (m == MOTION_PICKUP && ev == SE_NONE) ev = SE_PICKUP;
  }
#if PET_SENSE_DEBUG
  if (now >= senseDbgNext) {
    senseDbgNext = now + 2000;
    Serial.print("S: light=");
    Serial.print(lightAvg);
    Serial.print(" a=");
    Serial.print(lastAx);
    Serial.print(",");
    Serial.print(lastAy);
    Serial.print(",");
    Serial.println(lastAz);
  }
#endif
  return ev;
}
```

- [ ] **Step 7: 接入 pet.ino**

在 `pet/pet.ino`:
1. 在 `#include "voice_pet.h"` 之后加一行 `#include "pet_sense.h"`(`pet_logic.h` 已由 voice_pet.h 引入)
2. 在 `wakeUp()` 函数之后插入:
```cpp
void startDizzy() {
  lastInteract = millis();
  state = ST_SHOW;
  stateStart = millis();
  showUntil = millis() + 3000;
  drawPet(F_DIZZY);
  petAnimSet(A_DIZZY);
}

// 传感器事件:只在 IDLE / SHOW / SLEEP 处理;录音、思考时不采样
void handleSense() {
  if (state != ST_IDLE && state != ST_SHOW && state != ST_SLEEP) return;
  const int ev = petSensePoll();
  if (ev == SE_NONE) return;
  Serial.print("S: event=");
  Serial.println(ev);
  if (state == ST_SLEEP) {
    if (ev == SE_LIGHT || ev == SE_PICKUP || ev == SE_SHAKE) wakeUp();
    return;
  }
  if (ev == SE_DARK) {
    enterSleep();
    return;
  }
  if (ev == SE_SHAKE) {
    beep(523, 60);
    startDizzy();
    return;
  }
  if (ev == SE_PICKUP) {
    lastInteract = millis();
    if (petAnimCurrent() == A_DROWSY) petAnimSet(A_IDLE);
  }
}
```
3. `setup()` 中 `petMicBegin();` 之后加 `petSenseBegin();`
4. `loop()` 开头 `petAnimTick();` 之后加 `handleSense();`

- [ ] **Step 8: 标定光线阈值(需用户配合)**

在 `pet/pet_sense.h` 把 `#define PET_SENSE_DEBUG 0` 临时改为 `1`,运行 `bash tools/flash_and_log.sh pet 300`。请用户:正常开灯放置 20 秒 → 用手完全遮住屏幕下方的光线传感器 20 秒 → 关掉房间灯 20 秒(若方便)。然后 `grep -a "S: light=" /c/<user>/AppData/Local/Temp/wio_serial.log`。
据此设定:`PET_DARK_TH` = 关灯/遮住时读数上沿 + 20;`PET_LIGHT_TH` = 正常亮度读数下沿 − 20(必须满足 `PET_DARK_TH < PET_LIGHT_TH`)。把两个值写回 `pet_sense.h`,`PET_SENSE_DEBUG` 改回 `0`。

- [ ] **Step 9: 真机验收 + 麦克风回归(需用户配合)**

Run: `bash tools/flash_and_log.sh pet 900`。请用户:
1. 遮住光线传感器(或关灯)约 10 秒 → 进入睡觉;移开 2 秒 → 醒来
2. 待机时用力摇几下 → 蚊香眼晕 3 秒后回待机;冷却期内再摇不触发
3. 睡觉时把板子拿起来 → 醒来
4. **麦克风回归**:做完以上之后,按 B 说话 3 次,识别与回答必须正常
然后 `bash tools/wait_log.sh 'S: event=|T: |trimmed' 600`。
Expected: 1–3 有对应 `S: event=` 行(1=DARK 2=LIGHT 3=SHAKE 4=PICKUP);第 4 项 3 次 `T:` 行且回答正常。
**若第 4 项识别异常(例如全是 `asr rejected`、`trimmed` 后长度异常),说明 `analogRead(WIO_LIGHT)` 与麦克风 DMA 冲突 —— 停下来按 systematic-debugging 排查,不要继续。**

- [ ] **Step 10: 提交**

```bash
git add pet/pet_logic.h tests/pet_selftest/pet_selftest.ino pet/pet_sense.h pet/pet.ino
git commit -m "feat(pet): light sensor sleep/wake, IMU shake-dizzy and pickup-wake"
```

---

### Task 10(条件任务):S5 —— DeepSeek 连接复用

**前置判断:** 查看 `docs/perf-log.md` 中 Task 4/5 之后的 `llm_conn`。**中位数 ≤ 1500ms 则跳过本任务**,在 perf-log 记一句"llm_conn 中位 X ms,S5 不做",直接进入 Task 11。

**Files:**
- Modify: `pet/voice_pet.h`(`petAskLlm`)
- Modify: `docs/perf-log.md`

**Interfaces:**
- Consumes: `readHttpBody(..., keepOpen)`(Task 4)
- Produces: 全局 `WiFiClientSecure llmClient;`,`petAskLlm` 签名不变

- [ ] **Step 1: 改为复用连接 + 失败重连一次**

在 `pet/voice_pet.h` 中 `petAskLlm` 之前插入:

```cpp
// DeepSeek 长连接:TLS 握手在板子上很慢,能复用就复用;服务器断开后自动重连
WiFiClientSecure llmClient;

bool llmEnsureConnected(bool forceNew) {
  if (!forceNew && llmClient.connected()) return true;
  llmClient.stop();
  return llmClient.connect("api.deepseek.com", 443, 20000);
}
```

把 `petAskLlm` 中从 `const uint32_t tConn = millis();` 到 `petTm.llm = millis() - tLlm;` 之间的连接、发送、读取部分替换为(组装 `req2`/`body2` 的代码保持不变,移到循环之前):

```cpp
  JsonDocument req2;
  req2["model"] = "deepseek-chat";
  JsonArray msgs = req2["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = PET_SYSTEM_PROMPT;
  JsonObject user = msgs.add<JsonObject>();
  user["role"] = "user";
  user["content"] = question;
  req2["max_tokens"] = 120;  // 回答 45 字以内,够用且限制最坏耗时
  String body2;
  serializeJson(req2, body2);
  String req2s = "POST /v1/chat/completions HTTP/1.1\r\n"
                 "Host: api.deepseek.com\r\n"
                 "Authorization: Bearer " DEEPSEEK_KEY "\r\n"
                 "Content-Type: application/json\r\n"
                 "Connection: keep-alive\r\nContent-Length: ";
  req2s += String(body2.length());
  req2s += "\r\n\r\n";
  req2s += body2;

  String llmBody;
  bool ok = false;
  for (int attempt = 0; attempt < 2 && !ok; attempt++) {  // 旧连接可能已被服务器关掉:失败就新建连接重试一次
    const uint32_t tConn = millis();
    if (!llmEnsureConnected(attempt > 0)) {
      note = "llm connect failed";
      return false;
    }
    petTm.llmConn = millis() - tConn;
    const uint32_t tLlm = millis();
    llmClient.print(req2s);
    ok = readHttpBody(llmClient, llmBody, 30000, "llm", true);
    petTm.llm = millis() - tLlm;
  }
```

并删除原先函数里的 `WiFiClientSecure client2;` 声明及对 `client2` 的所有引用(已被上面代码取代)。

- [ ] **Step 2: 编译 + 真机测(需用户配合)**

编译(同 Task 7 Step 5)。运行 `bash tools/flash_and_log.sh pet 900`,请用户**间隔 10 秒内**连续问 3 句,再**等 2 分钟**问第 4 句。然后 `bash tools/wait_log.sh 'T: ' 600`。
Expected: 第 2、3 轮 `llm_conn` 接近 0;第 4 轮即使服务器已断开也能成功(可能出现一次失败后重连,`llm_conn` 为正常握手耗时)。任何一轮失败 → 回退本任务改动(`git checkout pet/voice_pet.h`)并在 perf-log 记录原因。

- [ ] **Step 3: 记录并提交**

`docs/perf-log.md` 追加 `### S5 连接复用(Task 10)`,记录 4 轮数字。

```bash
git add pet/voice_pet.h docs/perf-log.md
git commit -m "perf(pet): reuse DeepSeek TLS connection with reconnect fallback"
```

---

### Task 11: 总验收 + 文档

**Files:**
- Modify: `docs/perf-log.md`、`HANDOFF.md`、`README.md`

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 验收结论与更新后的文档

- [ ] **Step 1: 自检回归**

Run: `bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60`,(后台)`bash tools/wait_log.sh 'SELFTEST' 40`。
Expected: `SELFTEST PASS 51/51`。

- [ ] **Step 2: 10 轮稳定性 + 最终耗时(需用户配合)**

Run: `bash tools/flash_and_log.sh pet 1800`。请用户连续对话 10 轮(内容随意)。然后 `grep -a "T: \|呜\|note" /c/<user>/AppData/Local/Temp/wio_serial.log` 统计。
Expected:
- 10 轮中成功轮数 ≥ 基线时期的成功率(基线时期全部成功则要求 10/10)
- 成功轮的中位 `total` 比基线中位 **至少少 5000ms**
不满足任何一条:记录数据,回到对应任务排查,不要宣称完成。

- [ ] **Step 3: 填写 perf-log 结论**

在 `docs/perf-log.md` 末尾追加:

```markdown
## 结论

| 指标 | 基线 | 最终 | 变化 |
|---|---|---|---|
| 中位 total(ms) | | | |
| 10 轮成功率 | | | |
```
用 Step 2 的数据填表。

- [ ] **Step 4: 更新 HANDOFF.md 与 README.md**

`HANDOFF.md`:
- "当前状态"一节改为本次结果(版本 `pet 1.2`、提速数据、情绪与传感器功能清单)
- "软件架构(pet/)"一节补充 `pet_logic.h`(纯逻辑 + 板上自检)、`pet_anim.h`(动画调度,网络等待中 tick)、`pet_sense.h`(光线/IMU);更新 `pet_face.h` 描述(14 个表情枚举、`drawFeatures` 局部重绘)
- "构建与调试"一节加入:`tools/serial_log.py`、`tools/wait_log.sh`、`tools/sync_logic.sh`、自检运行命令
- "踩坑史"追加:漏写 WAV 头 + 漏 flush 导致百度 60s 零响应;按协议判断响应结束替代"3 秒无数据"
- "下一步路线":去掉已完成的"表情丰富化",保留对话记忆、提醒、每日简报等

`README.md`:在"桌面 AI 控制台"之前增加一节"AI 桌宠「小维」(pet/)",写明操作(B 说话、摇杆摸头、C 叫醒、遮光睡觉、摇晃会晕)与烧录命令 `bash tools/flash_and_log.sh pet 600`。

- [ ] **Step 5: 提交**

```bash
git add docs/perf-log.md HANDOFF.md README.md
git commit -m "docs: v2 acceptance results, handoff and readme for emotion+speed"
```

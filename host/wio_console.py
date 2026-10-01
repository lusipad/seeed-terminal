#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wio Console PC 端(host)— 板子的"大脑"

职责:监听 Wio Terminal 串口,收到 ACT <id> 后执行对应动作
(读剪贴板 → 调 LLM → 结果写回剪贴板),并把结果逐行回传到屏幕。

协议(行分隔):
  设备→PC: HELLO <ver> / PING / ACT <id>
  PC→设备: PONG / BUSY / TEXT|<UTF-8行> / DONE|<ASCII备注> / FAIL|<ASCII原因>

用法:python wio_console.py   (Ctrl+C 退出)
配置:同目录 config.json;api_key 也可用环境变量 GLM_API_KEY
"""

import json
import os
import sys
import textwrap
import time
from pathlib import Path

import pyperclip
import requests
import serial
import serial.tools.list_ports

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
DEFAULT_CONFIG = {
    "_help": "api_key 填智谱/DeepSeek 等 OpenAI 兼容接口的 Key;留空则 LLM 动作不可用(Hello Test 不需要)。api_key 优先读环境变量 GLM_API_KEY。",
    "port": "auto",
    "baud": 115200,
    "api_base": "https://open.bigmodel.cn/api/paas/v4",
    "model": "glm-4-flash",
    "api_key": "",
}
SEEED_VID = 0x2886
WRAP_WIDTH = 48      # 回传给屏幕的每行字符数(设备端按 52 缓冲)
MAX_TEXT_LINES = 30  # 回传的最大行数,超出截断


class ActionError(Exception):
    """动作失败,消息会回传到板子(ASCII)。"""


class NoKeyError(ActionError):
    def __init__(self):
        super().__init__("no api key - edit host/config.json")


# ---------------------------------------------------------------- config

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    env_key = os.environ.get("GLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def find_port(cfg: dict) -> str | None:
    if cfg["port"] and cfg["port"] != "auto":
        return cfg["port"]
    for p in serial.tools.list_ports.comports():
        if p.vid == SEEED_VID:
            return p.device
    return None


# ---------------------------------------------------------------- LLM

def llm_chat(cfg: dict, prompt: str) -> str:
    if not cfg["api_key"]:
        raise NoKeyError()
    url = cfg["api_base"].rstrip("/") + "/chat/completions"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {cfg['api_key']}"},
            json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=80,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ActionError(f"llm request failed: {exc.__class__.__name__}") from exc
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise ActionError("unexpected llm response") from exc


def clipboard() -> str:
    try:
        return pyperclip.paste() or ""
    except pyperclip.PyperclipException:
        raise ActionError("clipboard unavailable")


# ---------------------------------------------------------------- 动作(与固件 ACTIONS 表一致)

def is_mostly_cjk(text: str) -> bool:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return cjk > latin


def act_hello(cfg: dict) -> tuple[str, str]:
    # 不需要 API Key,用于验证 板子<->PC 链路
    return "WIO Console link OK - pipeline works!", "pipeline ok (no key needed)"


def act_translate(cfg: dict) -> tuple[str, str]:
    src = clipboard()
    if not src.strip():
        raise ActionError("clipboard empty - copy some text first")
    target = "英文" if is_mostly_cjk(src) else "简体中文"
    prompt = f"把下面内容翻译成{target},只输出译文,不要解释:\n\n{src[:6000]}"
    out = llm_chat(cfg, prompt)
    pyperclip.copy(out)
    return out, f"{len(out.encode('utf-8'))}B -> clipboard"


def act_summarize(cfg: dict) -> tuple[str, str]:
    src = clipboard()
    if not src.strip():
        raise ActionError("clipboard empty - copy some text first")
    prompt = f"用简体中文把下面的内容总结成 3~5 条要点,每条一行,以'- '开头,不要输出其他内容:\n\n{src[:6000]}"
    out = llm_chat(cfg, prompt)
    pyperclip.copy(out)
    return out, f"{len(out.encode('utf-8'))}B -> clipboard"


def act_commit(cfg: dict) -> tuple[str, str]:
    src = clipboard()
    if not src.strip():
        raise ActionError("clipboard empty - paste diff or change description")
    prompt = (
        "根据下面的改动说明或 git diff 生成一条 Conventional Commits 风格的 "
        "commit message(单行,类型前缀 + 简体中文描述),只输出这一行:\n\n"
        f"{src[:6000]}"
    )
    out = llm_chat(cfg, prompt)
    pyperclip.copy(out)
    return out, "commit msg -> clipboard"


def act_inspire(cfg: dict) -> tuple[str, str]:
    out = llm_chat(cfg, "随机来一句不超过 30 字的简体中文毒鸡汤或程序员灵感,只输出这一句。")
    pyperclip.copy(out)
    return out, "copied"


ACTIONS = {
    "hello": act_hello,
    "translate": act_translate,
    "summarize": act_summarize,
    "commit": act_commit,
    "inspire": act_inspire,
}

# ---------------------------------------------------------------- 串口收发

def ascii_only(text: str) -> str:
    return text.encode("ascii", "ignore").decode().strip() or "action error"


def send_text(ser: serial.Serial, text: str) -> None:
    sent = 0
    for raw in text.splitlines() or [text]:
        chunks = textwrap.wrap(raw, WRAP_WIDTH) or [""]
        for chunk in chunks:
            if sent >= MAX_TEXT_LINES:
                return
            ser.write(f"TEXT|{chunk}\n".encode("utf-8"))
            sent += 1


def run_action(ser: serial.Serial, action_id: str) -> None:
    handler = ACTIONS.get(action_id)
    if handler is None:
        ser.write(b"FAIL|unknown action\n")
        return
    ser.write(b"BUSY\n")
    started = time.time()
    try:
        text, note = handler(cfg_global)
        send_text(ser, text)
        ser.write(f"DONE|{ascii_only(note)}\n".encode("utf-8"))
        print(f"  [ok] {action_id} -> {ascii_only(note)}  ({time.time() - started:.1f}s)")
    except ActionError as exc:
        ser.write(f"FAIL|{ascii_only(str(exc))}\n".encode("utf-8"))
        print(f"  [fail] {action_id}: {ascii_only(str(exc))}")
    except Exception as exc:  # 兜底:任何异常都回传,别让板子等到超时
        ser.write(f"FAIL|internal: {ascii_only(str(exc))[:60]}\n".encode("utf-8"))
        print(f"  [fail] {action_id}: unexpected {exc!r}")


def handle_line(ser: serial.Serial, line: str) -> None:
    if line in ("PING",) or line.startswith("HELLO"):
        ser.write(b"PONG\n")
        if line.startswith("HELLO"):
            print(f"  board online: {line}")
        return
    if line.startswith("ACT "):
        run_action(ser, line[4:].strip())
        return
    if line.strip():
        print(f"  [board] {line}")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = load_config()
    global cfg_global
    cfg_global = cfg

    port = find_port(cfg)
    if port is None:
        print("未找到 Wio Terminal(VID 0x2886)。确认板子已插 USB,或在 config.json 里指定 port。")
        return 1

    print(f"Wio Console host | port={port} @ {cfg['baud']} | model={cfg['model']}"
          + ("" if cfg["api_key"] else " | (未配置 api_key,LLM 动作不可用)"))

    ser = serial.Serial(port, cfg["baud"], timeout=0.25)
    ser.write(b"PONG\n")  # 立即握手,让板子点亮 link 指示

    buf = b""
    try:
        while True:
            chunk = ser.read(256)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    line_bytes, buf = buf.split(b"\n", 1)
                    handle_line(ser, line_bytes.decode("utf-8", errors="replace").strip())
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nbye")
        return 0
    finally:
        ser.close()


cfg_global: dict = {}

if __name__ == "__main__":
    sys.exit(main())

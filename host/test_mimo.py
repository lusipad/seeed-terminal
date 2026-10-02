#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MiMo API 连通性自测:1) 大模型对话 2) TTS合成语音 -> ASR转写(模拟板子链路)
用法:先导出环境变量 MIMO_API_KEY,再运行本脚本。"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import wave

import requests

BASE = "https://api.xiaomimimo.com/v1"
KEY = os.environ.get("MIMO_API_KEY", "")
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def test_chat():
    print("== 1) chat completions (mimo-v2.6-flash) ==")
    r = requests.post(
        f"{BASE}/chat/completions",
        headers=HDR,
        json={
            "model": "mimo-v2.6-flash",
            "messages": [{"role": "user", "content": "用一句不超过15字的简体中文夸夸Wio Terminal"}],
            "max_completion_tokens": 100,
        },
        timeout=60,
    )
    print("  HTTP", r.status_code)
    if r.ok:
        print("  reply:", r.json()["choices"][0]["message"]["content"])
    else:
        print("  body:", r.text[:300])
    return r.ok


def make_test_wav(path):
    # 用 Windows SAPI 合成一段英文语音,模拟板子录的 WAV
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SetOutputToWaveFile('" + path.replace("\\", "/") + "'); "
        "$s.Speak('What is the weather like today, do I need an umbrella'); "
        "$s.Dispose()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], check=True, capture_output=True)


def test_asr(wav_path):
    print("== 2) ASR (mimo-v2.5-asr) ==")
    with open(wav_path, "rb") as f:
        pcm = f.read()
    with wave.open(wav_path, "rb") as w:
        print(f"  wav: {w.getframerate()}Hz {w.getsampwidth()*8}bit ch={w.getnchannels()} {w.getnframes()/w.getframerate():.1f}s")
    audio_b64 = base64.b64encode(pcm).decode()
    r = requests.post(
        f"{BASE}/chat/completions",
        headers=HDR,
        json={
            "model": "mimo-v2.5-asr",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": f"data:audio/wav;base64,{audio_b64}"},
                        }
                    ],
                }
            ],
            "asr_options": {"language": "en"},
        },
        timeout=120,
    )
    print("  HTTP", r.status_code)
    if r.ok:
        print("  transcript:", r.json()["choices"][0]["message"]["content"])
    else:
        print("  body:", r.text[:300])
    return r.ok


if __name__ == "__main__":
    if not KEY:
        sys.exit("缺少 MIMO_API_KEY 环境变量")
    wav = os.path.join(tempfile.gettempdir(), "mimo_test.wav")
    make_test_wav(wav)
    ok1 = test_chat()
    ok2 = test_asr(wav)
    print("== result ==")
    print("chat:", "OK" if ok1 else "FAIL", "| asr:", "OK" if ok2 else "FAIL")
    sys.exit(0 if ok1 and ok2 else 1)

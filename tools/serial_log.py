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

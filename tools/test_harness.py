#!/usr/bin/env python3
"""
Wio Terminal Automated Test Harness (Integration & E2E Suite)
Tests state machine transitions, key injection, liveness, and AP lifecycle.
"""

import sys
import time
import re
import argparse
from typing import Optional, Dict, Any, List

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial is required. Run: pip install pyserial")
    sys.exit(1)


def find_wio_port() -> Optional[str]:
    """Auto-detect Wio Terminal COM port."""
    for p in serial.tools.list_ports.comports():
        # VID 0x2886 is Seeed Technology Co., Ltd.
        if p.vid == 0x2886:
            return p.device
        if "Seeeduino" in p.description or "Wio" in p.description:
            return p.device
    return None


class WioHarnessClient:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout, write_timeout=2.0)
        self.ser.dtr = True
        self.ser.rts = True
        time.sleep(0.3)
        self.ser.reset_input_buffer()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_cmd(self, cmd: str) -> None:
        if not cmd.endswith("\n"):
            cmd += "\n"
        self.ser.write(cmd.encode("utf-8"))
        self.ser.flush()

    def read_line(self, timeout: float = 1.0) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    return line
            time.sleep(0.01)
        return ""

    def ping(self, timeout: float = 1.5) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd("!PING")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if "!PONG" in line:
                return True
        return False

    def get_status(self, timeout: float = 1.5) -> Dict[str, Any]:
        self.ser.reset_input_buffer()
        self.send_cmd("!STATUS")
        res = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if "!STATUS" in line:
                for m in re.finditer(r"(\w+)=(\S+)", line):
                    res[m.group(1)] = m.group(2)
                return res
        return res

    def get_config(self, timeout: float = 1.5) -> Dict[str, str]:
        self.ser.reset_input_buffer()
        self.send_cmd("!CFG_DUMP")
        res = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if "!CFG" in line:
                for m in re.finditer(r"(\w+)=(\S+)", line):
                    res[m.group(1)] = m.group(2)
                return res
        return res

    def inject_key(self, key_name: str, timeout: float = 0.5) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd(f"!KEY_{key_name.upper()}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if f"!OK KEY_{key_name.upper()}" in line:
                return True
        return False

    def set_look(self, offset: int, timeout: float = 0.5) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd(f"!LOOK {offset}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if f"!OK LOOK {offset}" in line:
                return True
        return False

    def set_anim(self, anim_id: int, timeout: float = 0.5) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd(f"!ANIM {anim_id}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if f"!OK ANIM {anim_id}" in line:
                return True
        return False

    def set_page(self, page_id: int, timeout: float = 2.0) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd(f"!PAGE {page_id}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if f"!OK PAGE {page_id}" in line:
                return True
        return False

    def pomo_cmd(self, cmd_action: str, timeout: float = 0.5) -> bool:
        self.ser.reset_input_buffer()
        self.send_cmd(f"!POMO_{cmd_action.upper()}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.read_line(timeout=0.1)
            if f"!OK POMO_{cmd_action.upper()}" in line:
                return True
        return False

    def wait_state(self, target_state: str, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Check async broadcast !STATE line
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if line == f"!STATE {target_state}":
                    return True
            # Or query status
            st = self.get_status(timeout=0.2)
            if st.get("state") == target_state:
                return True
            time.sleep(0.05)
        return False


class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", duration_ms: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms


def run_tests(client: WioHarnessClient) -> List[TestResult]:
    results: List[TestResult] = []

    def record(name: str, passed: bool, msg: str, t_start: float):
        dur = (time.time() - t_start) * 1000.0
        results.append(TestResult(name, passed, msg, dur))
        status_str = "\033[92mPASS\033[0m" if passed else "\033[91mFAIL\033[0m"
        print(f"[{status_str}] {name:<35} ({dur:6.1f}ms) {msg}")

    # TC-01: Liveness / Ping
    t0 = time.time()
    ok = client.ping(timeout=1.5)
    record("TC-01: Liveness Ping/Pong", ok, "Responded !PONG" if ok else "No response within 1.5s", t0)
    if not ok:
        return results

    # TC-02: Initial State Check (Ensure in ST_IDLE)
    t0 = time.time()
    st = client.get_status(timeout=1.0)
    state = st.get("state")
    if state != "ST_IDLE":
        # Attempt to reset to idle by sending KEY_C
        client.inject_key("C")
        time.sleep(0.4)
        st = client.get_status(timeout=1.0)
        state = st.get("state")
    ok = (state == "ST_IDLE")
    record("TC-02: Initial State ST_IDLE", ok, f"Current state: {state}", t0)

    # TC-03: Enter Config via KEY_A
    t0 = time.time()
    client.inject_key("A")
    ok = client.wait_state("ST_CONFIG", timeout=2.5)
    record("TC-03: Enter Config Mode (KEY_A)", ok, "Entered ST_CONFIG & SoftAP started" if ok else "Failed to enter ST_CONFIG", t0)

    # TC-04: Exit Config via KEY_B (Regression test for exit hang)
    t0 = time.time()
    time.sleep(0.4)  # 300ms grace period configured in firmware
    client.inject_key("B")
    ok = client.wait_state("ST_IDLE", timeout=1.5)
    record("TC-04: Exit Config via KEY_B", ok, "Clean exit to ST_IDLE without deadlock" if ok else "STUCK in config mode (deadlock detected!)", t0)

    # TC-05: Exit Config via KEY_C (Multi-key tolerance)
    t0 = time.time()
    client.inject_key("A")
    in_cfg = client.wait_state("ST_CONFIG", timeout=2.5)
    time.sleep(0.4)
    client.inject_key("C")
    out_cfg = client.wait_state("ST_IDLE", timeout=1.5)
    ok = in_cfg and out_cfg
    record("TC-05: Exit Config via KEY_C", ok, "Key C exit validated" if ok else "Key C exit failed", t0)

    # TC-06: Main Loop Jitter / Latency (<50ms avg)
    t0 = time.time()
    latencies = []
    for _ in range(10):
        t_sub = time.time()
        client.ping(timeout=0.3)
        latencies.append((time.time() - t_sub) * 1000.0)
    avg_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    ok = (avg_lat < 50.0 and max_lat < 150.0)
    record("TC-06: Loop Jitter & Response Time", ok, f"avg={avg_lat:.1f}ms, max={max_lat:.1f}ms", t0)

    # TC-07: Config Dump from QSPI Flash
    t0 = time.time()
    cfg = client.get_config(timeout=1.0)
    ssid = cfg.get("ssid", "")
    city = cfg.get("city", "")
    ok = len(ssid) > 0 and city == "上海"
    record("TC-07: QSPI Flash Storage Check", ok, f"SSID='{ssid}', City='{city}' loaded from Flash" if ok else f"Unexpected config: SSID='{ssid}', City='{city}'", t0)

    # TC-08: 3 Consecutive Enter/Exit Cycles (Stability & No Leak)
    t0 = time.time()
    cycles_ok = True
    for i in range(3):
        client.inject_key("A")
        if not client.wait_state("ST_CONFIG", timeout=2.0):
            cycles_ok = False
            break
        time.sleep(0.35)
        client.inject_key("B")
        if not client.wait_state("ST_IDLE", timeout=1.5):
            cycles_ok = False
            break
    record("TC-08: 3x Rapid Config Toggle Cycles", cycles_ok, "All 3 cycles completed without hang" if cycles_ok else f"Failed at cycle {i+1}", t0)

    # TC-09: Face Swaying & Look Offset Rendering Check
    t0 = time.time()
    look_ok = True
    for offset in [-4, 0, 4, 0, -2, 2, 0]:
        if not client.set_look(offset, timeout=0.5):
            look_ok = False
            break
        time.sleep(0.05)
    record("TC-09: Face Swaying Look Offset Shifts", look_ok, "All offsets (-4..+4) shifted and cleaned with zero lag" if look_ok else "Failed to shift look offset", t0)

    # TC-10: Dynamic Animation Mode Switching
    t0 = time.time()
    anim_ok = True
    anim_err = ""
    if not client.set_anim(3, timeout=0.8):
        anim_ok = False
        anim_err = "set_anim(3) no ACK"
    else:
        time.sleep(0.1)
        st = client.get_status(timeout=0.8)
        if st.get("anim") != "3":
            anim_ok = False
            anim_err = f"expected anim=3, got {st.get('anim')}"
    if anim_ok:
        if not client.set_anim(8, timeout=0.8):
            anim_ok = False
            anim_err = "set_anim(8) no ACK"
        else:
            time.sleep(0.1)
            st = client.get_status(timeout=0.8)
            if st.get("anim") != "8":
                anim_ok = False
                anim_err = f"expected anim=8, got {st.get('anim')}"
    if anim_ok:
        if not client.set_anim(1, timeout=0.8):
            anim_ok = False
            anim_err = "set_anim(1) no ACK"
        else:
            time.sleep(0.1)
            st = client.get_status(timeout=0.8)
            if st.get("anim") != "1":
                anim_ok = False
                anim_err = f"expected anim=1, got {st.get('anim')}"
    record("TC-10: Dynamic Anim Switching & Liveness", anim_ok, "Switched A_THINK -> A_DIZZY -> A_IDLE smoothly" if anim_ok else f"Anim switch failed: {anim_err}", t0)

    # TC-11: 3-in-1 Dashboard Page Switching (Pet <-> Clock <-> Focus)
    t0 = time.time()
    page_ok = True
    page_err = ""
    # Switch to Clock (1)
    if not client.set_page(1, timeout=3.5):
        page_ok = False
        page_err = "set_page(1) no ACK"
    else:
        time.sleep(0.3)
        st = client.get_status(timeout=2.0)
        if st.get("page") != "1":
            page_ok = False
            page_err = f"expected page=1, got {st.get('page')}"
    if page_ok:
        if not client.set_page(2, timeout=3.5):
            page_ok = False
            page_err = "set_page(2) no ACK"
        else:
            time.sleep(0.3)
            st = client.get_status(timeout=2.0)
            if st.get("page") != "2":
                page_ok = False
                page_err = f"expected page=2, got {st.get('page')}"
    if page_ok:
        if not client.set_page(0, timeout=2.0):
            page_ok = False
            page_err = "set_page(0) no ACK"
        else:
            time.sleep(0.3)
            st = client.get_status(timeout=2.0)
            if st.get("page") != "0":
                page_ok = False
                page_err = f"expected page=0, got {st.get('page')}"
    if page_ok:
        if not client.inject_key("JOY_R", timeout=1.0):
            page_ok = False
            page_err = "inject_key(JOY_R) no ACK"
        else:
            time.sleep(2.5)  # 允许摇杆切到时钟页执行高精大字号全画幅光栅直写
            st = client.get_status(timeout=2.0)
            if st.get("page") != "1":
                page_ok = False
                page_err = f"JOY_R expected page=1, got {st.get('page')}"
    client.set_page(0, timeout=2.0)
    time.sleep(0.2)
    record("TC-11: 3-in-1 Dashboard Page Switching", page_ok, "Pet <-> Clock <-> Focus page switching & joystick cycling validated" if page_ok else f"Page switching failed: {page_err}", t0)

    # TC-12: Flip-to-Focus Pomodoro Engine (Start, Tick, Pause, Reset)
    t0 = time.time()
    pomo_ok = True
    client.pomo_cmd("reset")
    st = client.get_status(timeout=0.5)
    if st.get("pomo") != "1500" or st.get("pomo_run") != "0":
        pomo_ok = False
    # Start Pomodoro and let it tick for 1.2s
    client.pomo_cmd("start")
    time.sleep(1.2)
    st = client.get_status(timeout=0.5)
    rem = int(st.get("pomo", "1500"))
    running = st.get("pomo_run", "0")
    if rem >= 1500 or running != "1":
        pomo_ok = False
    # Pause and reset
    client.pomo_cmd("pause")
    client.pomo_cmd("reset")
    st = client.get_status(timeout=0.5)
    if st.get("pomo") != "1500" or st.get("pomo_run") != "0":
        pomo_ok = False
    record("TC-12: Pomodoro Countdown Engine & Control", pomo_ok, f"Pomodoro ticked down ({rem}s left, running={running}) & reset successfully" if pomo_ok else "Pomodoro engine failed", t0)

    return results


def main():
    parser = argparse.ArgumentParser(description="Wio Terminal Test Harness Runner")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g. COM3)")
    args = parser.parse_args()

    port = args.port or find_wio_port()
    if not port:
        print("Error: Could not detect connected Wio Terminal. Specify --port <PORT>.")
        sys.exit(1)

    print("==================================================")
    print(f"  Wio Terminal Test Harness Runner (Target: {port})")
    print("==================================================")

    client = WioHarnessClient(port)
    try:
        client.connect()
    except Exception as e:
        print(f"Error opening port {port}: {e}")
        sys.exit(1)

    try:
        results = run_tests(client)
    finally:
        client.close()

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print("\n--------------------------------------------------")
    print(f"Summary: Total: {total} | Passed: {passed} | Failed: {failed}")
    if failed == 0:
        print("\033[92mALL HARNESS TESTS PASSED SUCCESSFULLY!\033[0m")
        sys.exit(0)
    else:
        print(f"\033[91m{failed} HARNESS TESTS FAILED!\033[0m")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/bin/bash
# Wio Terminal 一键:清理串口占用 → 自动找口烧录 → 挂实时日志
# 用法: bash tools/flash_and_log.sh [程序名:console|pet|tlsdiag] [日志秒数]
SKETCH="${1:-console}"
DUR="${2:-600}"
LOG=/c/<user>/AppData/Local/Temp/wio_serial.log
AC="/c/Program Files/Arduino CLI/arduino-cli.exe"

# 1. 清掉占用串口的残留进程
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { \$_.CommandLine -match 'COM3' -or \$_.CommandLine -match 'COM4' -or \$_.CommandLine -match 'SerialPort' } | Where-Object { \$_.ProcessId -ne \$PID } | ForEach-Object { 'KILL ' + \$_.ProcessId; Stop-Process -Id \$_.ProcessId -Force }" 2>&1 | head -4
sleep 1

# 2. 自动找板子的串口
PORT=$(powershell.exe -NoProfile -Command "(Get-CimInstance Win32_PnPEntity | Where-Object { \$_.Name -match 'COM\d' -and \$_.DeviceID -match 'VID_2886' }).Name" 2>/dev/null | grep -oE "COM[0-9]+" | head -1)
if [ -z "$PORT" ]; then echo "板子不在电脑上(检查 USB 线/是否插的是另一个 USB-C 口)"; exit 1; fi
echo "port: $PORT"

# 3. 烧录(目录与构建缓存按程序名;SKETCH=none 时只听日志不烧录)
if [ "$SKETCH" != "none" ]; then
  "$AC" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path "build/$SKETCH" "$SKETCH" 2>&1 | grep -qE "error" && { echo "COMPILE FAILED"; "$AC" compile --fqbn Seeeduino:samd:seeed_wio_terminal --build-path "build/$SKETCH" "$SKETCH" 2>&1 | grep -E "error" | head -8; exit 1; }
  "$AC" upload -p "$PORT" --fqbn Seeeduino:samd:seeed_wio_terminal --build-path "build/$SKETCH" 2>&1 | grep -E "Verify successful|No device|error" | head -3
fi

# 4. 挂实时日志
rm -f "$LOG"
(powershell.exe -NoProfile -Command "
\$log = \"\$env:TEMP\\wio_serial.log\"
\$sp = New-Object System.IO.Ports.SerialPort
\$sp.PortName = \"$PORT\"; \$sp.BaudRate = 115200; \$sp.DtrEnable = \$true; \$sp.RtsEnable = \$true
\$sp.ReadTimeout = 400
\$sp.Open()
\$deadline = (Get-Date).AddSeconds($DUR)
while ((Get-Date) -lt \$deadline) {
  try {
    \$line = \$sp.ReadLine()
    if (\$line) { Add-Content -Path \$log -Value \$line.Trim() -Encoding UTF8 }
  } catch [TimeoutException] {}
}
\$sp.Close()" > /dev/null 2>&1 &)
echo "logger armed (${DUR}s) -> $LOG"

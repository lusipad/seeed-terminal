#!/bin/bash
# 等日志里出现匹配正则的行(最多 N 秒),然后打印所有匹配行
# 用法: bash tools/wait_log.sh <正则> [秒数]
LOG="${WIO_LOG:-${TMPDIR:-/tmp}/wio_serial.log}"
PAT="$1"
MAX="${2:-60}"
for _ in $(seq 1 "$MAX"); do
  grep -aqE "$PAT" "$LOG" 2>/dev/null && break
  sleep 1
done
grep -aE "$PAT" "$LOG" || { echo "TIMEOUT waiting for: $PAT"; exit 1; }

#!/bin/bash
# 小维宿主模拟器构建与运行(Windows + MSVC;固件构建不受影响)
# 用法: bash sim/build.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p sim/out
MSYS2_ARG_CONV_EXCL="*" cmd.exe /C "$(cygpath -w sim/build.bat)"

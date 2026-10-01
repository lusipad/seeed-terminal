#!/bin/bash
# pet/pet_logic.h 是唯一源头;Arduino 不支持跨目录 include,自检 sketch 使用拷贝
cd "$(dirname "$0")/.." && cp pet/pet_logic.h tests/pet_selftest/pet_logic.h && echo "synced pet_logic.h"

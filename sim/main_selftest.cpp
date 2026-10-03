// WioKit L0 纯逻辑在宿主机上直接跑板上自检(同一份断言,无需硬件)
#include "Arduino.h"
#include "../tests/pet_selftest/pet_selftest.ino"  // 真实自检代码

int main() {
  printf("=== WioKitLogic L0 selftest on host ===\n");
  setup();
  return failN ? 1 : 0;
}

// 模拟器后端:虚拟时钟、按键、确定性随机、帧缓冲导出、台词/事件队列
#include "Arduino.h"
#include "Seeed_GFX.h"
#include "rpcWiFi.h"
#include <vector>

namespace sim {

static unsigned long g_ms = 0;
static unsigned long g_rng = 0x20261003;
// 按键按下后只维持 N 次"被读到 LOW"——pet.ino 里有 while(anyKeyDown()) 的松手等待,
// 真机靠人手松开,模拟器靠读次数自动回弹,否则虚拟时钟不前进会死循环
static bool g_keyDown[256] = {false};
static int g_keyReads[256] = {0};

struct SenseEvent { unsigned long at; int ev; };
struct Dialog { const char* transcript; const char* reply; };

static std::vector<SenseEvent> g_senseEvents;
static std::vector<Dialog> g_dialogs;
static size_t g_dialogIdx = 0;

unsigned long nowMs() { return g_ms; }
void advanceMs(unsigned long ms) { g_ms += ms; }

void setKey(int pin, bool down) {
  if (pin >= 0 && pin < 256) {
    g_keyDown[pin] = down;
    if (down) g_keyReads[pin] = 5;
  }
}
void clearKeys() {
  for (int i = 0; i < 256; i++) { g_keyDown[i] = false; g_keyReads[i] = 0; }
}

int digitalReadImpl(int pin) {
  if (pin < 0 || pin >= 256 || !g_keyDown[pin]) return HIGH;
  if (g_keyReads[pin] > 0) {
    g_keyReads[pin]--;
    return LOW;
  }
  return HIGH;
}

void simSeed(unsigned long s) { g_rng = s ^ 0x9E3779B9UL; }
long simRandom(long lo, long hi) {
  if (hi <= lo) return lo;
  g_rng = g_rng * 1103515245UL + 12345UL;
  return lo + (long)((g_rng >> 8) % (unsigned long)(hi - lo));
}

void senseEventAt(unsigned long atMs, int event) {
  g_senseEvents.push_back({atMs, event});
}
bool nextSenseEvent(int& ev) {
  static size_t idx = 0;
  while (idx < g_senseEvents.size()) {
    if (g_ms >= g_senseEvents[idx].at) {
      ev = g_senseEvents[idx++].ev;
      return true;
    }
    return false;  // 最近的一个还没到时(队列按时间排序)
  }
  return false;
}
void pushDialog(const char* transcript, const char* reply) {
  g_dialogs.push_back({transcript, reply});
}

const char* nextTranscript() {
  if (g_dialogIdx < g_dialogs.size()) return g_dialogs[g_dialogIdx].transcript;
  return "(模拟器台词用完了)";
}
const char* nextReply() {
  if (g_dialogIdx < g_dialogs.size()) {
    const char* r = g_dialogs[g_dialogIdx].reply;
    g_dialogIdx++;
    return r;
  }
  g_dialogIdx++;
  return "[开心]台词用完啦,再说一次!";
}

void dumpFrame(const char* path) {
  FILE* f = fopen(path, "wb");
  if (!f) return;
  fprintf(f, "P6\n320 240\n255\n");
  for (int y = 0; y < 240; y++) {
    for (int x = 0; x < 320; x++) {
      const uint16_t rgb = fb[y][x];
      const uint8_t r = (uint8_t)(((rgb >> 11) & 0x1F) * 255 / 31);
      const uint8_t g = (uint8_t)(((rgb >> 5) & 0x3F) * 255 / 63);
      const uint8_t b = (uint8_t)((rgb & 0x1F) * 255 / 31);
      fwrite(&r, 1, 1, f);
      fwrite(&g, 1, 1, f);
      fwrite(&b, 1, 1, f);
    }
  }
  fclose(f);
}

}  // namespace sim

SimSerial Serial;
SimWiFiClass WiFi;
uint16_t sim::fb[240][320];

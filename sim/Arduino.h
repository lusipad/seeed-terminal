// 宿主模拟器专用 Arduino 兼容层(固件编译不用此文件)
// 提供:虚拟时钟、虚拟按键、Arduino String、Serial(打印到 stdout)、确定性随机数
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

// ---- 虚拟时钟与后端(sim_backend.cpp 实现) ----
namespace sim {
unsigned long nowMs();
void advanceMs(unsigned long ms);
void setKey(int pin, bool down);      // digitalRead 视角:down=true 时引脚为 LOW
void clearKeys();
void dumpFrame(const char* path);     // 把帧缓冲写成 PPM(sim/out/*.ppm,脚本再转 PNG)
void senseEventAt(unsigned long atMs, int event);  // 预约 wioSensePoll 返回的事件
void pushDialog(const char* transcript, const char* reply);  // 预约一轮"识别+回答"
int digitalReadImpl(int pin);
void simSeed(unsigned long s);
long simRandom(long lo, long hi);
}  // namespace sim

inline unsigned long millis() { return sim::nowMs(); }
inline unsigned long micros() { return sim::nowMs() * 1000UL; }
inline void delay(unsigned long ms) { sim::advanceMs(ms); }
inline void delayMicroseconds(unsigned long us) { sim::advanceMs(us / 1000); }

// ---- 引脚/数字量 ----
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define LOW 0
#define HIGH 1
inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline int analogRead(int) { return 42; }

#define WIO_KEY_A 100
#define WIO_KEY_B 101
#define WIO_KEY_C 102
#define WIO_5S_UP 103
#define WIO_5S_DOWN 104
#define WIO_5S_LEFT 105
#define WIO_5S_RIGHT 106
#define WIO_5S_PRESS 107
#define WIO_BUZZER 108
#define A0 0
#define LED_LED 109
#define LED_BUILTIN LED_LED

inline int digitalRead(int pin) { return sim::digitalReadImpl(pin); }
inline void tone(int, int, int) {}
inline void noTone(int) {}

// ---- 确定性随机(LCG) ----
inline void randomSeed(unsigned long s) { sim::simSeed(s); }
inline long random(long lo, long hi) { return sim::simRandom(lo, hi); }
inline long random(long hi) { return sim::simRandom(0, hi); }

#define PROGMEM
#define pgm_read_byte(p) (*(const unsigned char*)(p))
#define F(x) (x)

// ---- String(够 pet/WioKitCjk 使用的最小子集) ----
class String {
 public:
  String() {}
  String(const char* p) : s_(p ? p : "") {}
  explicit String(char c) : s_(1, c) {}
  bool operator==(const char* p) const { return s_ == p; }
  bool operator!=(const char* p) const { return s_ != p; }
  const char* c_str() const { return s_.c_str(); }
  unsigned length() const { return (unsigned)s_.size(); }
  char charAt(unsigned i) const { return s_[i]; }
  char operator[](unsigned i) const { return s_[i]; }
  bool startsWith(const char* p) const { return s_.rfind(p, 0) == 0; }
  String substring(unsigned from) const {
    return from < s_.size() ? String(s_.substr(from)) : String();
  }
  void replace(const char*, const char*) {}
  int toInt() const { return atoi(s_.c_str()); }
  String& operator=(const char* p) { s_ = p ? p : ""; return *this; }
  String& operator+=(const char* p) { s_ += p; return *this; }

 private:
  friend String operator+(const String& a, const String& b) { return String(a.s_ + b.s_); }
  friend String operator+(const String& a, const char* b) { return String(a.s_ + b); }
  friend String operator+(const char* a, const String& b) { return String(std::string(a) + b.s_); }
  explicit String(const std::string& s) : s_(s) {}
  std::string s_;
};

// ---- Serial → stdout ----
struct SimSerial {
  void begin(unsigned long) { setvbuf(stdout, NULL, _IONBF, 0); }
  operator bool() const { return true; }
  void print(const char* p) { fputs(p, stdout); }
  void print(char c) { fputc(c, stdout); }
  void print(int v) { printf("%d", v); }
  void print(unsigned int v) { printf("%u", v); }
  void print(long v) { printf("%ld", v); }
  void print(unsigned long v) { printf("%lu", v); }
  // 任何带 c_str() 的类型(String、IPAddress 等)
  template <typename T>
  auto print(const T& v) -> decltype((void)v.c_str(), void()) {
    fputs(v.c_str(), stdout);
  }
  void println() { fputc('\n', stdout); }
  template <typename T>
  void println(const T& v) {
    print(v);
    fputc('\n', stdout);
  }
  size_t write(const uint8_t* buf, size_t n) {
    fwrite(buf, 1, n, stdout);
    return n;
  }
};
extern SimSerial Serial;

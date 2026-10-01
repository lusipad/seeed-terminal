// pet_logic.h 板上自检:等串口打开后跑全部断言,之后每 3 秒重复打印汇总
// 运行:bash tools/sync_logic.sh && bash tools/flash_and_log.sh tests/pet_selftest 60
#include <Arduino.h>
#include "pet_logic.h"

int passN = 0, failN = 0;

void check(bool ok, const char* name) {
  if (ok) {
    passN++;
    return;
  }
  failN++;
  Serial.print("FAIL ");
  Serial.println(name);
}

int st(const char* s) { return httpResponseState(s, strlen(s)); }

bool decodeEq(const char* in, const char* want) {
  char buf[96];
  strcpy(buf, in);
  size_t n = 0;
  if (!chunkedWalk(buf, strlen(buf), buf, &n)) return false;
  return n == strlen(want) && memcmp(buf, want, n) == 0;
}

void testHttp() {
  check(st("HTTP/1.1 200 OK\r\nContent-Le") == HTTP_NEED_MORE, "http: header partial");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhel") == HTTP_NEED_MORE, "http: cl short");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello") == HTTP_DONE, "http: cl full");
  check(st("HTTP/1.1 200 OK\r\ncontent-length:5\r\n\r\nhello") == HTTP_DONE, "http: cl lowercase no space");
  check(st("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n") == HTTP_DONE, "http: cl zero");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n") == HTTP_DONE,
        "http: chunked done");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n") == HTTP_NEED_MORE,
        "http: chunked no terminator");
  check(st("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\nx0\r\n\r\ny\r\n") == HTTP_NEED_MORE,
        "http: fake terminator inside data");
  check(st("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nabc") == HTTP_NO_LENGTH, "http: no length");
  const char* h = "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nX";
  check(httpHeaderEnd(h, strlen(h)) == 43, "http: header end pos");
  check(httpIsChunked(h, 43), "http: is chunked");
  check(!httpIsChunked("HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n", 34), "http: not chunked");
}

void testChunked() {
  check(decodeEq("5\r\nhello\r\n0\r\n\r\n", "hello"), "chunk: single");
  check(decodeEq("3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n", "abcde"), "chunk: multi");
  check(decodeEq("0\r\n\r\n", ""), "chunk: empty");
  check(decodeEq("A\r\n0123456789\r\n0\r\n\r\n", "0123456789"), "chunk: hex upper");
  check(decodeEq("3;ext=1\r\nabc\r\n0\r\n\r\n", "abc"), "chunk: extension");
  check(!decodeEq("5\r\nhel", "hel"), "chunk: truncated is incomplete");
}

void printSummary() {
  Serial.print(failN ? "SELFTEST FAIL " : "SELFTEST PASS ");
  Serial.print(passN);
  Serial.print("/");
  Serial.println(passN + failN);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
  }
  delay(300);
  testHttp();
  testChunked();
  printSummary();
}

void loop() {
  delay(3000);
  printSummary();
}

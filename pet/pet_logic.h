// ---- 纯逻辑(无 Arduino 依赖):HTTP 响应判定、chunked 解码 ----
// pet/ 是唯一源头;改完运行 tools/sync_logic.sh 同步到 tests/pet_selftest/,再跑板上自检
#pragma once
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

enum HttpState { HTTP_NEED_MORE = 0, HTTP_DONE = 1, HTTP_NO_LENGTH = 2 };

// 在 [h, h+n) 中不区分大小写地查找 needle,返回偏移;找不到返回 -1
inline long ciFind(const char* h, size_t n, const char* needle) {
  const size_t m = strlen(needle);
  if (m == 0 || m > n) return -1;
  for (size_t i = 0; i + m <= n; i++) {
    size_t j = 0;
    while (j < m && tolower((unsigned char)h[i + j]) == tolower((unsigned char)needle[j])) j++;
    if (j == m) return (long)i;
  }
  return -1;
}

inline long httpHeaderEnd(const char* buf, size_t n) { return ciFind(buf, n, "\r\n\r\n"); }

inline bool httpIsChunked(const char* buf, size_t headerLen) {
  return ciFind(buf, headerLen, "\ntransfer-encoding:") >= 0 && ciFind(buf, headerLen, "chunked") >= 0;
}

// 逐块走一遍 chunked 正文:遇到 0 长度块及其后的 CRLF 才算完整(数据里出现 "0\r\n\r\n" 不会误判)。
// out 非空时把数据依次写入 out(允许 out == body 原地解码,写指针永远不超过读指针)。
inline bool chunkedWalk(const char* body, size_t n, char* out, size_t* decodedLen) {
  size_t pos = 0, w = 0;
  while (true) {
    const long le = ciFind(body + pos, n - pos, "\r\n");
    if (le < 0) return false;
    size_t sz = 0;
    bool any = false;
    for (size_t k = pos; k < pos + (size_t)le; k++) {  // 十六进制长度,忽略 ";扩展"
      const char c = body[k];
      int v;
      if (c >= '0' && c <= '9') v = c - '0';
      else if (c >= 'a' && c <= 'f') v = c - 'a' + 10;
      else if (c >= 'A' && c <= 'F') v = c - 'A' + 10;
      else break;
      sz = sz * 16 + v;
      any = true;
    }
    if (!any) return false;
    pos += (size_t)le + 2;
    if (sz == 0) {
      if (n - pos < 2) return false;  // 末尾 CRLF 未到
      if (decodedLen) *decodedLen = w;
      return true;
    }
    if (n - pos < sz + 2) return false;
    if (out) memmove(out + w, body + pos, sz);
    w += sz;
    pos += sz + 2;
  }
}

// 判断已收到的响应是否完整:按 Content-Length 或 chunked 终止块;两者都没有返回 HTTP_NO_LENGTH(调用方兜底)
inline int httpResponseState(const char* buf, size_t n) {
  const long he = httpHeaderEnd(buf, n);
  if (he < 0) return HTTP_NEED_MORE;
  const size_t bodyStart = (size_t)he + 4;
  const size_t bodyLen = n - bodyStart;
  const long cl = ciFind(buf, (size_t)he, "\ncontent-length:");
  if (cl >= 0) {
    const long want = strtol(buf + cl + 16, NULL, 10);  // 数字后面紧跟 \r,strtol 会停下
    return (long)bodyLen >= want ? HTTP_DONE : HTTP_NEED_MORE;
  }
  if (httpIsChunked(buf, (size_t)he)) {
    return chunkedWalk(buf + bodyStart, bodyLen, NULL, NULL) ? HTTP_DONE : HTTP_NEED_MORE;
  }
  return HTTP_NO_LENGTH;
}

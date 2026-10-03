#include "WioKitConfig.h"
#include <sfud.h>
#include <rpcWiFi.h>
#include <DNSServer.h>
#include <WebServer.h>

static const uint32_t WIO_CONFIG_MAGIC = 0x57494F32;       // "WIO2"
static const uint32_t WIO_CONFIG_ADDR  = 0x003FF000;       // 4MB Flash 最后一个 4KB 扇区

static DNSServer* pDnsServer = nullptr;
static WebServer* pWebServer = nullptr;
static bool portalSaved = false;
static WioConfig portalResultCfg;
static WioConfig currentPresetCfg;
static String cachedScanOptions = "";

static uint32_t calcChecksum(const WioConfig& cfg) {
  const uint8_t* p = (const uint8_t*)&cfg;
  const size_t len = offsetof(WioConfig, crc);
  uint32_t sum = 0x12345678;
  for (size_t i = 0; i < len; i++) {
    sum = ((sum << 5) | (sum >> 27)) ^ p[i];
  }
  return sum;
}

bool wioConfigInit() {
  static bool inited = false;
  if (inited) return true;
  if (sfud_init() == SFUD_SUCCESS) {
    inited = true;
    Serial.println("V: QSPI flash init ok");
    return true;
  }
  Serial.println("V: QSPI flash init FAIL");
  return false;
}

bool wioConfigLoad(WioConfig& cfg) {
  if (!wioConfigInit()) return false;
  const sfud_flash* flash = sfud_get_device(0);
  if (!flash) return false;

  WioConfig tmp;
  if (sfud_read(flash, WIO_CONFIG_ADDR, sizeof(tmp), (uint8_t*)&tmp) != SFUD_SUCCESS) {
    return false;
  }
  if (tmp.magic != WIO_CONFIG_MAGIC) return false;
  if (tmp.crc != calcChecksum(tmp)) return false;
  if (strlen(tmp.ssid) == 0) return false;

  cfg = tmp;
  Serial.print("V: loaded config from flash, ssid=");
  Serial.print(cfg.ssid);
  Serial.print(" city=");
  Serial.println(cfg.city);
  return true;
}

bool wioConfigSave(const WioConfig& cfg) {
  if (!wioConfigInit()) return false;
  const sfud_flash* flash = sfud_get_device(0);
  if (!flash) return false;

  WioConfig toWrite = cfg;
  toWrite.magic = WIO_CONFIG_MAGIC;
  toWrite.crc = calcChecksum(toWrite);

  if (sfud_erase_write(flash, WIO_CONFIG_ADDR, sizeof(toWrite), (uint8_t*)&toWrite) != SFUD_SUCCESS) {
    Serial.println("V: save config FAIL");
    return false;
  }
  Serial.println("V: save config ok");
  return true;
}

bool wioConfigClear() {
  if (!wioConfigInit()) return false;
  const sfud_flash* flash = sfud_get_device(0);
  if (!flash) return false;
  return sfud_erase(flash, WIO_CONFIG_ADDR, 4096) == SFUD_SUCCESS;
}

// ---- 配网 HTML 页面渲染 ----
static void handlePortalRoot() {
  String html = F("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                  "<meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1'>"
                  "<title>小维桌宠 - 网络配置</title><style>"
                  "body{font-family:-apple-system,sans-serif;background:#fff5ea;color:#333;margin:0;padding:16px;display:flex;justify-content:center;}"
                  ".card{background:#fff;border-radius:18px;box-shadow:0 8px 24px rgba(0,0,0,0.08);max-width:380px;width:100%;padding:24px 20px;box-sizing:border-box;border:2px solid #ffcc80;}"
                  "h2{margin:0 0 4px;font-size:20px;color:#d85a00;text-align:center;}"
                  "p.sub{margin:0 0 18px;font-size:12px;color:#888;text-align:center;}"
                  "label{display:block;font-size:13px;font-weight:bold;margin:12px 0 4px;color:#555;}"
                  "input,select{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ddd;border-radius:10px;font-size:14px;outline:none;background:#fafafa;}"
                  "input:focus,select:focus{border-color:#ff9800;background:#fff;}"
                  "details{margin-top:16px;background:#fdfdfd;border:1px dashed #ccc;border-radius:10px;padding:10px;}"
                  "summary{font-size:13px;color:#777;cursor:pointer;font-weight:bold;}"
                  "button{width:100%;margin-top:22px;padding:12px;background:linear-gradient(135deg,#ff9800,#f57c00);color:#fff;border:none;border-radius:12px;font-size:16px;font-weight:bold;cursor:pointer;box-shadow:0 4px 12px rgba(245,124,0,0.3);}"
                  "button:active{transform:scale(0.98);}"
                  ".tip{font-size:11px;color:#aaa;margin-top:4px;}"
                  "</style></head><body><div class='card'>"
                  "<h2>🐱 小维桌宠配网</h2>"
                  "<p class='sub'>设置 WiFi 与小维常驻城市</p>"
                  "<form action='/save' method='POST'>");

  html += F("<label>WiFi 名称 (SSID)</label>");
  html += F("<select name='ssid_sel' onchange='if(this.value===\"__custom__\"){document.getElementById(\"c_ssid\").style.display=\"block\";document.getElementById(\"c_ssid\").value=\"\";}else{document.getElementById(\"c_ssid\").style.display=\"none\";document.getElementById(\"c_ssid\").value=this.value;}'>");
  html += cachedScanOptions;
  html += F("<option value='__custom__'>➕ 手动输入其它网络...</option></select>");
  html += F("<input type='text' id='c_ssid' name='ssid_custom' style='display:none;margin-top:6px;' placeholder='输入 WiFi 名称'>");

  html += F("<label>WiFi 密码</label><input type='password' name='pass' placeholder='无密码可留空'>");

  html += F("<label>常驻城市 (查天气用)</label><input type='text' name='city' value='");
  html += (strlen(currentPresetCfg.city) ? currentPresetCfg.city : "深圳");
  html += F("' placeholder='例如：深圳 / 北京 / 上海'>");

  html += F("<details><summary>🔑 自定义 API Key (可选)</summary>"
            "<label>DeepSeek API Key</label><input type='password' name='ds_key' placeholder='留空保留原配置'>"
            "<label>Baidu API Key</label><input type='password' name='bd_key' placeholder='留空保留原配置'>"
            "<label>Baidu Secret Key</label><input type='password' name='bd_sec' placeholder='留空保留原配置'>"
            "<div class='tip'>如未变更密钥，留空即可继续使用预置 Key</div></details>");

  html += F("<button type='submit'>💾 保存并连接</button></form></div>"
            "<script>var s=document.querySelector('select');if(s&&s.value!=='__custom__'){document.getElementById('c_ssid').value=s.value;}</script>"
            "</body></html>");

  pWebServer->send(200, "text/html", html);
}

static void handlePortalSave() {
  String ssid = pWebServer->arg("ssid_custom");
  if (!ssid.length()) ssid = pWebServer->arg("ssid_sel");
  if (ssid == "__custom__") ssid = "";
  ssid.trim();

  String pass = pWebServer->arg("pass");
  pass.trim();

  String city = pWebServer->arg("city");
  city.trim();
  if (!city.length()) city = "深圳";

  String dsKey = pWebServer->arg("ds_key");
  dsKey.trim();
  String bdKey = pWebServer->arg("bd_key");
  bdKey.trim();
  String bdSec = pWebServer->arg("bd_sec");
  bdSec.trim();

  memset(&portalResultCfg, 0, sizeof(portalResultCfg));
  strncpy(portalResultCfg.ssid, ssid.c_str(), sizeof(portalResultCfg.ssid) - 1);
  strncpy(portalResultCfg.pass, pass.c_str(), sizeof(portalResultCfg.pass) - 1);
  strncpy(portalResultCfg.city, city.c_str(), sizeof(portalResultCfg.city) - 1);

  // 若填写了新 Key 则采用新 Key，否则沿用预置
  if (dsKey.length() > 5) {
    strncpy(portalResultCfg.deepseekKey, dsKey.c_str(), sizeof(portalResultCfg.deepseekKey) - 1);
  } else {
    strncpy(portalResultCfg.deepseekKey, currentPresetCfg.deepseekKey, sizeof(portalResultCfg.deepseekKey) - 1);
  }

  if (bdKey.length() > 5) {
    strncpy(portalResultCfg.baiduApiKey, bdKey.c_str(), sizeof(portalResultCfg.baiduApiKey) - 1);
  } else {
    strncpy(portalResultCfg.baiduApiKey, currentPresetCfg.baiduApiKey, sizeof(portalResultCfg.baiduApiKey) - 1);
  }

  if (bdSec.length() > 5) {
    strncpy(portalResultCfg.baiduSecret, bdSec.c_str(), sizeof(portalResultCfg.baiduSecret) - 1);
  } else {
    strncpy(portalResultCfg.baiduSecret, currentPresetCfg.baiduSecret, sizeof(portalResultCfg.baiduSecret) - 1);
  }

  wioConfigSave(portalResultCfg);
  portalSaved = true;

  String resp = F("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                  "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                  "<title>保存成功</title><style>"
                  "body{font-family:sans-serif;background:#e8f5e9;color:#2e7d32;display:flex;justify-content:center;align-items:center;height:90vh;margin:0;}"
                  ".box{background:#fff;padding:30px;border-radius:16px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.1);max-width:320px;}"
                  "h2{margin-top:0;}p{color:#555;font-size:14px;}"
                  "</style></head><body><div class='box'>"
                  "<h2>✅ 配置已保存！</h2>"
                  "<p>小维正在连接 WiFi：<b>");
  resp += ssid;
  resp += F("</b></p><p>设备将自动重启联网，你可以关闭此网页啦~</p></div></body></html>");

  pWebServer->send(200, "text/html", resp);
}

static void handlePortalNotFound() {
  // Captive Portal 强制重定向
  pWebServer->sendHeader("Location", "http://192.168.4.1/", true);
  pWebServer->send(302, "text/plain", "");
}

bool wioPortalBegin(const char* apSsid, const WioConfig& curCfg) {
  portalSaved = false;
  currentPresetCfg = curCfg;

  WiFi.mode(WIFI_AP_STA);
  // 扫描附近 WiFi
  cachedScanOptions = "";
  int n = WiFi.scanNetworks();
  if (n > 0) {
    for (int i = 0; i < n; i++) {
      String s = WiFi.SSID(i);
      if (s.length()) {
        cachedScanOptions += "<option value='" + s + "'";
        if (s == curCfg.ssid) cachedScanOptions += " selected";
        cachedScanOptions += ">" + s + " (" + String(WiFi.RSSI(i)) + "dBm)</option>";
      }
    }
  }

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(apSsid)) {
    Serial.println("V: softAP failed");
    return false;
  }
  IPAddress ip = WiFi.softAPIP();
  Serial.print("V: softAP started, ip=");
  Serial.println(ip);

  pDnsServer = new DNSServer();
  pDnsServer->start(53, "*", ip);

  pWebServer = new WebServer(80);
  pWebServer->on("/", HTTP_GET, handlePortalRoot);
  pWebServer->on("/save", HTTP_POST, handlePortalSave);
  pWebServer->on("/generate_204", handlePortalRoot);       // Android Captive Portal
  pWebServer->on("/hotspot-detect.html", handlePortalRoot); // iOS Captive Portal
  pWebServer->onNotFound(handlePortalNotFound);
  pWebServer->begin();

  return true;
}

int wioPortalPoll(WioConfig& outCfg) {
  if (pDnsServer) pDnsServer->processNextRequest();
  if (pWebServer) pWebServer->handleClient();
  if (portalSaved) {
    outCfg = portalResultCfg;
    return 1;
  }
  return 0;
}

void wioPortalEnd() {
  if (pWebServer) {
    pWebServer->stop();
    delete pWebServer;
    pWebServer = nullptr;
  }
  if (pDnsServer) {
    pDnsServer->stop();
    delete pDnsServer;
    pDnsServer = nullptr;
  }
  WiFi.softAPdisconnect(true);
  WiFi.mode(WIFI_STA);
  Serial.println("V: softAP stopped, memory released");
}

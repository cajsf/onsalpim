// 보드 A — 센서 담당 (UNO R4 WiFi)
// PIR(D2) + DHT11(D4) 값을 2초마다 플랫폼에 CIN으로 업로드
// 부팅 시 자기 컨테이너(pir/temp/humi)를 라벨과 함께 직접 생성 (이미 있으면 409 = 정상)
//
// 업로드 전 준비:
//  1. 아래 WIFI_SSID / WIFI_PASS / API_KEY 세 개를 실제 값으로 채우기
//  2. 라이브러리 매니저에서 "DHT sensor library" (Adafruit) 설치
//     (같이 깔라고 뜨는 Adafruit Unified Sensor도 설치)
//  3. WiFi는 핸드폰 핫스팟(2.4GHz) 권장 — 학교 와이파이 안 됨

#include <WiFiS3.h>
#include <DHT.h>

// ===== 여기 세 개만 채우면 됨 =====
#include "secrets.h"   // WIFI_SSID · WIFI_PASS · API_KEY — 저장소에 없음. secrets.example.h 를 복사해 채울 것
// ==================================

const char* HOST    = "onem2m.iotcoss.ac.kr";
const char* AE      = "byeongari";
const char* CREATOR = "sjuBAR2";
const char* LECTURE = "LCT_20260002";
const char* ORIGIN  = "SOrigin_BAR2";

#define PIR_PIN 2
#define DHT_PIN 4

DHT dht(DHT_PIN, DHT11);
WiFiSSLClient client;

void connectWiFi() {
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print("WiFi 접속 시도: ");
    Serial.println(WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    delay(5000);
  }
  Serial.print("WiFi 연결됨, IP: ");
  Serial.println(WiFi.localIP());
}

// oneM2M 요청 공통 함수. ty=3 컨테이너 생성, ty=4 CIN 생성, ty=0 GET
String m2mRequest(const char* method, String path, int ty, String body) {
  if (!client.connect(HOST, 443)) {
    Serial.println("[에러] 서버 접속 실패");
    return "";
  }
  client.print(String(method) + " " + path + " HTTP/1.1\r\n");
  client.print("Host: " + String(HOST) + "\r\n");
  client.print("X-API-KEY: " + String(API_KEY) + "\r\n");
  client.print("X-AUTH-CUSTOM-CREATOR: " + String(CREATOR) + "\r\n");
  client.print("X-AUTH-CUSTOM-LECTURE: " + String(LECTURE) + "\r\n");
  client.print("X-M2M-Origin: " + String(ORIGIN) + "\r\n");
  client.print("X-M2M-RI: nodeA" + String(millis()) + "\r\n");
  client.print("Accept: application/json\r\n");
  if (ty > 0) client.print("Content-Type: application/json;ty=" + String(ty) + "\r\n");
  if (body.length() > 0) client.print("Content-Length: " + String(body.length()) + "\r\n");
  client.print("Connection: close\r\n\r\n");
  if (body.length() > 0) client.print(body);

  String resp = "";
  unsigned long t0 = millis();
  while (millis() - t0 < 5000) {
    while (client.available()) {
      resp += (char)client.read();
      t0 = millis();
    }
    if (!client.connected() && !client.available()) break;
  }
  client.stop();
  return resp;
}

String statusOf(String resp) {
  return resp.length() >= 12 ? resp.substring(9, 12) : "???";
}

void createCNT(String rn, String lblJson) {
  String body = "{\"m2m:cnt\":{\"rn\":\"" + rn + "\",\"lbl\":" + lblJson + "}}";
  String resp = m2mRequest("POST", "/Mobius/" + String(AE), 3, body);
  Serial.println("CNT " + rn + " 생성: " + statusOf(resp) + " (201=성공, 409=이미있음)");
}

void postCIN(String cnt, String value) {
  String body = "{\"m2m:cin\":{\"con\":\"" + value + "\"}}";
  String resp = m2mRequest("POST", "/Mobius/" + String(AE) + "/" + cnt, 4, body);
  Serial.println("  " + cnt + " = " + value + " → " + statusOf(resp));
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(PIR_PIN, INPUT);
  dht.begin();
  connectWiFi();

  createCNT("pir",  "[\"kind=sensor\",\"type=motion\",\"values=0|1\",\"desc=현관 움직임 감지\"]");
  createCNT("temp", "[\"kind=sensor\",\"type=temperature\",\"unit=C\",\"values=0~50\"]");
  createCNT("humi", "[\"kind=sensor\",\"type=humidity\",\"unit=%\",\"values=20~90\"]");
  Serial.println("보드 A 시작 — 2초마다 센서값 업로드");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  int pir = digitalRead(PIR_PIN);
  postCIN("pir", String(pir));

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (!isnan(t)) postCIN("temp", String(t, 1));
  else Serial.println("  temp 판독 실패 (부팅 직후면 정상)");
  if (!isnan(h)) postCIN("humi", String(h, 0));

  delay(2000);
}

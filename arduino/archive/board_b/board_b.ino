// 보드 B — 액추에이터 담당 (UNO R4 WiFi)
// 2초마다 led_cmd / servo_cmd 컨테이너의 최신값(/la)을 읽어서 그대로 실행
// 부팅 시 자기 컨테이너를 라벨과 함께 직접 생성 (이미 있으면 409 = 정상)
//
// 업로드 전 준비:
//  1. 아래 WIFI_SSID / WIFI_PASS / API_KEY 세 개를 실제 값으로 채우기
//  2. 서보는 기본 내장 Servo 라이브러리 사용 (설치 불필요)
//
// 명령 값:
//  led_cmd   : "ON" / "OFF"
//  servo_cmd : "0" ~ "180" (각도)

#include <WiFiS3.h>
#include <Servo.h>

// ===== 여기 세 개만 채우면 됨 =====
#include "secrets.h"   // WIFI_SSID · WIFI_PASS · API_KEY — 저장소에 없음. secrets.example.h 를 복사해 채울 것
// ==================================

const char* HOST    = "onem2m.iotcoss.ac.kr";
const char* AE      = "byeongari";
const char* CREATOR = "sjuBAR2";
const char* LECTURE = "LCT_20260002";
const char* ORIGIN  = "SOrigin_BAR2";

#define R_PIN 3
#define G_PIN 5
#define B_PIN 6
#define SERVO_PIN 9

// 공통 애노드 LED면(동작이 반대면) 아래를 true로
const bool LED_COMMON_ANODE = false;

Servo servo;
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
  client.print("X-M2M-RI: nodeB" + String(millis()) + "\r\n");
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

// 응답 JSON에서 "con" 값만 뽑기 (라이브러리 없이 문자열 검색)
String extractCon(String resp) {
  int i = resp.indexOf("\"con\":");
  if (i < 0) return "";
  i += 6;
  while (i < (int)resp.length() && resp[i] == ' ') i++;
  if (resp[i] == '"') {
    int j = resp.indexOf('"', i + 1);
    return resp.substring(i + 1, j);
  }
  int j = i;
  while (j < (int)resp.length() && resp[j] != ',' && resp[j] != '}') j++;
  return resp.substring(i, j);
}

String getLatest(String cnt) {
  String resp = m2mRequest("GET", "/Mobius/" + String(AE) + "/" + cnt + "/la", 0, "");
  return extractCon(resp);
}

void setLED(int r, int g, int b) {
  if (LED_COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(R_PIN, r);
  analogWrite(G_PIN, g);
  analogWrite(B_PIN, b);
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  servo.attach(SERVO_PIN);
  servo.write(0);
  setLED(0, 0, 0);
  connectWiFi();

  createCNT("led_cmd",   "[\"kind=actuator\",\"type=light\",\"accepts=ON|OFF\",\"desc=현관 조명\"]");
  createCNT("servo_cmd", "[\"kind=actuator\",\"type=window\",\"accepts=range=0~180\",\"unit=deg\",\"desc=창문 개폐\"]");
  Serial.println("보드 B 시작 — 2초마다 명령 확인");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  String led = getLatest("led_cmd");
  if (led == "ON") setLED(255, 255, 255);
  else if (led == "OFF") setLED(0, 0, 0);
  if (led.length() > 0) Serial.println("  led_cmd = " + led);

  String sv = getLatest("servo_cmd");
  if (sv.length() > 0) {
    int angle = sv.toInt();
    if (angle >= 0 && angle <= 180) {
      servo.write(angle);
      Serial.println("  servo_cmd = " + String(angle));
    }
  }

  delay(2000);
}

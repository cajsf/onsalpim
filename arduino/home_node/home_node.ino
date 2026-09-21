// home_node — 세대 1채를 담당하는 노드. 이 스케치 하나를 보드마다 HOME만 바꿔서 굽는다.
//
// 이 보드가 플랫폼에 만드는 것 (라벨로 자기 소개를 한다 — 서버는 경로를 모른다):
//   h{HOME}_pir    kind=sensor  type=motion   home={HOME}  report_s={N}   ← 주기 보고
//   h{HOME}_evt    kind=event   type=motion   home={HOME}  role=activity  ← 움직임 이벤트
//   h{HOME}_temp   kind=sensor  type=temperature                          (HAS_DHT)
//   h{HOME}_humi   kind=sensor  type=humidity                             (HAS_DHT)
//   h{HOME}_batt   kind=sensor  type=battery  unit=%                      (HAS_BATT)
//
// 컨테이너를 왜 둘로 나누는가 (이게 이 펌웨어의 핵심):
//   pir 은 움직임이 있든 없든 REPORT_S 마다 무조건 올린다 → "장치가 살아있다"는 증거.
//   evt 는 움직임이 0→1 로 바뀔 때만 올린다              → "사람이 움직였다"는 증거.
//   서버는 이 둘을 따로 봐서 '무활동'과 '통신 두절'을 구분한다.
//   하나로 합치면 값이 안 오는 게 둘 중 뭔지 영원히 알 수 없다.
//
// 보드 배치 (전시) — 전부 ESP32. UNO R4 도 그대로 굽힌다(핀만 아래에서 갈린다).
// 1층·2층으로 나눈 이유: 세대가 한 줄이면 범위 규칙("2층만 기준 다르게")을 보여줄 수가 없다.
//   101호  PIR + DHT11 + LED/서보   ← 관람객이 손 흔드는 세대, 제어 규칙 시연도 겸함
//   102호  PIR                      ← 가만히 두면 무활동 (부재 등록 시연도 여기서)
//   201호  PIR + 가변저항(배터리)     ← 노브를 돌려 배터리 부족을 만든다
//   202호  PIR                      ← 처음엔 꽂지 않는다. 발표 중 꽂으면 2층에 세대가 는다
//                                      (= 경로를 박아두지 않았다는 증거)
//                                      그대로 USB 를 뽑으면 통신 두절 시연까지 이어진다
//
// 업로드 전:
//   1. 아래 '보드마다 바꾸는 것' 블록을 채운다
//   2. WiFi 는 2.4GHz 만 된다. 학교 와이파이(로그인 페이지) 불가 → 핫스팟 권장
//   3. HAS_DHT 면 Adafruit "DHT sensor library" 설치
//   4. HAS_ACTUATOR + ESP32 면 "ESP32Servo" 설치.
//      analogWrite 는 esp32 보드패키지 3.x 부터 된다 — 2.x 면 컴파일이 막힌다

// ===================== 보드마다 바꾸는 것 =====================
const char* HOME = "101";        // 이 보드가 담당하는 세대 (호수)

#define HAS_DHT       1          // DHT11 온습도 있음
#define HAS_BATT      0          // 가변저항으로 배터리 잔량 모사
#define HAS_ACTUATOR  1          // RGB LED + 서보 (제어 규칙 시연용, UNO R4 권장)

const unsigned long REPORT_S = 5;   // 주기 보고 간격(초).
                                    // 서버의 두절 판정 임계 = 3 × 이 값 → 여기선 15초.
                                    // 라벨에 그대로 실려 나가므로 서버 코드는 손댈 필요 없다.
// =============================================================

// ===== 공용 설정 =====
#include "secrets.h"   // WIFI_SSID · WIFI_PASS · API_KEY — 저장소에 없음. secrets.example.h 를 복사해 채울 것

const char* HOST    = "onem2m.iotcoss.ac.kr";
const char* AE      = "byeongari";
const char* CREATOR = "sjuBAR2";
const char* LECTURE = "LCT_20260002";
const char* ORIGIN  = "SOrigin_BAR2";

// ===== 보드별 차이 흡수 =====
#if defined(ARDUINO_ARCH_ESP32)
  #include <WiFi.h>
  #include <WiFiClientSecure.h>
  WiFiClientSecure client;
  const int ADC_MAX = 4095;
  #define PIR_PIN   27
  #define DHT_PIN   26
  #define BATT_PIN  34
#else                                   // Arduino UNO R4 WiFi
  #include <WiFiS3.h>
  WiFiSSLClient client;
  const int ADC_MAX = 1023;
  #define PIR_PIN   2
  #define DHT_PIN   4
  #define BATT_PIN  A0
#endif

#if HAS_DHT
  #include <DHT.h>
  DHT dht(DHT_PIN, DHT11);
#endif

#if HAS_ACTUATOR
  #if defined(ARDUINO_ARCH_ESP32)
    #include <ESP32Servo.h>
    // UNO 핀(3/5/6/9)을 그대로 쓰면 안 된다:
    //   GPIO 6~11 = 플래시 전용, GPIO 3 = 시리얼(U0RXD), GPIO 5 = 부팅 스트래핑.
    // 아래는 스트래핑·플래시에 안 걸리고 PIR(27)·DHT(26)·배터리(34)와도 안 겹치는 핀.
    #define R_PIN 18
    #define G_PIN 19
    #define B_PIN 21
    #define SERVO_PIN 22
  #else                                 // Arduino UNO R4 WiFi
    #include <Servo.h>
    #define R_PIN 3
    #define G_PIN 5
    #define B_PIN 6
    #define SERVO_PIN 9
  #endif
  const bool LED_COMMON_ANODE = false;
  Servo servo;
#endif

// PIR 이 튀는 걸 막는 최소 간격. 이보다 짧은 간격의 재발화는 같은 움직임으로 본다.
const unsigned long EVENT_MIN_MS = 3000;

String pirCnt, evtCnt, tempCnt, humiCnt, battCnt;
unsigned long lastReport = 0, lastEvent = 0, lastBatt = 0, lastCmd = 0;
int lastPir = LOW;

// ---------- 플랫폼 통신 ----------

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
  client.print("X-M2M-RI: h" + String(HOME) + String(millis()) + "\r\n");
  client.print("Accept: application/json\r\n");
  if (ty > 0) client.print("Content-Type: application/json;ty=" + String(ty) + "\r\n");
  if (body.length() > 0) client.print("Content-Length: " + String(body.length()) + "\r\n");
  client.print("Connection: close\r\n\r\n");
  if (body.length() > 0) client.print(body);

  String resp = "";
  unsigned long t0 = millis();
  while (millis() - t0 < 5000) {
    while (client.available()) { resp += (char)client.read(); t0 = millis(); }
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
  Serial.println("CNT " + rn + " : " + statusOf(resp) + " (201=생성, 409=이미있음)");
}

void postCIN(String cnt, String value) {
  String body = "{\"m2m:cin\":{\"con\":\"" + value + "\"}}";
  m2mRequest("POST", "/Mobius/" + String(AE) + "/" + cnt, 4, body);
}

#if HAS_ACTUATOR
String extractCon(String resp) {
  int i = resp.indexOf("\"con\":");
  if (i < 0) return "";
  i += 6;
  while (i < (int)resp.length() && resp[i] == ' ') i++;
  if (resp[i] == '"') { int j = resp.indexOf('"', i + 1); return resp.substring(i + 1, j); }
  int j = i;
  while (j < (int)resp.length() && resp[j] != ',' && resp[j] != '}') j++;
  return resp.substring(i, j);
}

String getLatest(String cnt) {
  return extractCon(m2mRequest("GET", "/Mobius/" + String(AE) + "/" + cnt + "/la", 0, ""));
}

void setLED(int r, int g, int b) {
  if (LED_COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(R_PIN, r); analogWrite(G_PIN, g); analogWrite(B_PIN, b);
}
#endif

// ---------- 준비 ----------

void setup() {
  Serial.begin(115200);
  delay(2000);
  pinMode(PIR_PIN, INPUT);

  String h = String(HOME);
  pirCnt  = "h" + h + "_pir";
  evtCnt  = "h" + h + "_evt";
  tempCnt = "h" + h + "_temp";
  humiCnt = "h" + h + "_humi";
  battCnt = "h" + h + "_batt";

#if HAS_DHT
  dht.begin();
#endif
#if HAS_ACTUATOR
  #if defined(ARDUINO_ARCH_ESP32)
    // 서보와 LED(analogWrite)가 둘 다 LEDC 를 쓴다. 서보에 타이머를 하나 떼어주지 않으면
    // 둘 중 하나가 조용히 안 먹는다 — LED 는 켜지는데 서보만 안 도는 증상이 이것이다.
    ESP32PWM::allocateTimer(0);
    servo.setPeriodHertz(50);           // SG90 = 50Hz
    servo.attach(SERVO_PIN, 500, 2400); // SG90 펄스폭(us). 0~180도가 안 나오면 이 값을 조정
  #else
    servo.attach(SERVO_PIN);
  #endif
  pinMode(R_PIN, OUTPUT); pinMode(G_PIN, OUTPUT); pinMode(B_PIN, OUTPUT);
  servo.write(0);
  setLED(0, 0, 0);
#endif
#if defined(ARDUINO_ARCH_ESP32)
  client.setInsecure();          // 수업용 서버 — 인증서 검증 생략
#endif

  connectWiFi();

  // 라벨에 report_s 를 실어 보낸다. 서버는 이 값으로 두절 임계를 계산한다.
  // → 전시에서 5초, 실제 운영에서 60초로 바꿔도 서버 코드는 그대로다.
  String common = "\"home=" + h + "\"";
  createCNT(pirCnt, "[\"kind=sensor\",\"type=motion\"," + common +
                    ",\"values=0|1\",\"report_s=" + String(REPORT_S) +
                    "\",\"desc=" + h + "호 움직임 주기보고\"]");
  createCNT(evtCnt, "[\"kind=event\",\"type=motion\"," + common +
                    ",\"role=activity\",\"desc=" + h + "호 움직임 발생\"]");
#if HAS_DHT
  createCNT(tempCnt, "[\"kind=sensor\",\"type=temperature\"," + common +
                     ",\"unit=C\",\"values=0~50\",\"report_s=" + String(REPORT_S) + "\"]");
  createCNT(humiCnt, "[\"kind=sensor\",\"type=humidity\"," + common +
                     ",\"unit=%\",\"values=20~90\",\"report_s=" + String(REPORT_S) + "\"]");
#endif
#if HAS_BATT
  createCNT(battCnt, "[\"kind=sensor\",\"type=battery\"," + common +
                     ",\"unit=%\",\"values=0~100\",\"report_s=" + String(REPORT_S * 4) + "\"]");
#endif
#if HAS_ACTUATOR
  createCNT("led_cmd",   "[\"kind=actuator\",\"type=light\",\"accepts=ON|OFF\"," + common +
                         ",\"desc=현관 조명\"]");
  createCNT("servo_cmd", "[\"kind=actuator\",\"type=window\",\"accepts=range=0~180\"," + common +
                         ",\"unit=deg\",\"desc=창문 개폐\"]");
#endif

  Serial.println(h + "호 노드 시작 — " + String(REPORT_S) + "초마다 보고, 움직임은 발생 즉시");
}

// ---------- 본 루프 ----------
// delay() 를 쓰지 않는다. 주기 보고를 기다리는 동안에도 PIR 을 계속 봐야
// 스쳐 지나가는 움직임을 놓치지 않기 때문이다.

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  unsigned long nowMs = millis();
  int pir = digitalRead(PIR_PIN);

  // ① 움직임 이벤트 — 0→1 로 바뀌는 순간에만, 즉시 올린다
  if (pir == HIGH && lastPir == LOW && (nowMs - lastEvent) > EVENT_MIN_MS) {
    postCIN(evtCnt, "1");
    lastEvent = nowMs;
    Serial.println("  [활동] 움직임 감지 → " + evtCnt);
  }
  lastPir = pir;

  // ② 주기 보고 — 값이 0이어도 무조건 보낸다. 이게 '살아있음'의 증거다.
  if (nowMs - lastReport >= REPORT_S * 1000UL) {
    lastReport = nowMs;
    postCIN(pirCnt, String(pir));
    Serial.println("  [보고] " + pirCnt + " = " + String(pir));

#if HAS_DHT
    float t = dht.readTemperature();
    float hm = dht.readHumidity();
    if (!isnan(t)) postCIN(tempCnt, String(t, 1));
    if (!isnan(hm)) postCIN(humiCnt, String(hm, 0));
#endif
  }

#if HAS_BATT
  // ③ 배터리 — 자주 바뀌지 않으니 덜 보낸다. 가변저항을 돌리면 잔량이 변한다.
  //    (실제 배터리 전압 분배를 읽는 것과 코드 경로가 같다)
  if (nowMs - lastBatt >= REPORT_S * 4000UL) {
    lastBatt = nowMs;
    int pct = (int)(analogRead(BATT_PIN) * 100L / ADC_MAX);
    postCIN(battCnt, String(pct));
    Serial.println("  [배터리] " + String(pct) + "%");
  }
#endif

#if HAS_ACTUATOR
  // ④ 제어 명령 확인 — 규칙 엔진이 올린 값을 그대로 실행한다 (판단하지 않는다)
  if (nowMs - lastCmd >= 2000UL) {
    lastCmd = nowMs;
    String led = getLatest("led_cmd");
    if (led == "ON") setLED(255, 255, 255);
    else if (led == "OFF") setLED(0, 0, 0);

    String sv = getLatest("servo_cmd");
    if (sv.length() > 0) {
      int angle = sv.toInt();
      if (angle >= 0 && angle <= 180) servo.write(angle);
    }
  }
#endif

  delay(50);   // PIR 을 초당 20번 본다 — 이벤트를 놓치지 않을 만큼 촘촘하게
}

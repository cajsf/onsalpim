// DHT11 단독 테스트 — WiFi 없이 온습도만 1초마다 시리얼 출력
// 배선: DATA(가운데 out)->D4, VCC(+)->5V, GND(-)->GND

#include <DHT.h>

#define DHT_PIN 4
DHT dht(DHT_PIN, DHT11);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("DHT11 테스트 시작");
}

void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t) || isnan(h)) {
    Serial.println("판독 실패 — 배선 확인 (DATA=D4, +=5V, -=GND)");
  } else {
    Serial.print("온도: ");
    Serial.print(t);
    Serial.print("C, 습도: ");
    Serial.print(h);
    Serial.println("%");
  }
  delay(1000);
}

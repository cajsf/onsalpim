// 서보 단독 테스트 — WiFi/LED 없이 서보만 3초마다 0도 <-> 180도 왕복
// 배선: 주황(신호)->D9, 빨강(가운데)->5V, 갈색->GND

#include <Servo.h>

Servo servo;

void setup() {
  Serial.begin(115200);
  servo.attach(9);
}

void loop() {
  Serial.println("0도로 이동");
  servo.write(0);
  delay(3000);
  Serial.println("180도로 이동");
  servo.write(180);
  delay(3000);
}

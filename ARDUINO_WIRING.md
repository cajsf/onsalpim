# 아두이노 배선 규격 (보드 A/B) — 2026-07-20 확정

스케치 코드의 핀 상수는 반드시 이 문서와 일치시킬 것.

## 보드 A — 센서 담당 (UNO R4 WiFi #1)

| 부품 | 부품 핀 | 아두이노 핀 | 비고 |
|---|---|---|---|
| PIR (HC-SR501) | VCC | 5V | |
| | OUT | **D2** | 움직임 시 1 |
| | GND | GND | |
| DHT11 | VCC(+) | 5V | 3핀 모듈 기준 |
| | DATA | **D4** | 4핀 짜리(bare)면 VCC-DATA 사이 10kΩ 풀업 필요 |
| | GND(−) | GND | |
| RFID-RC522 (D5에 추가) | 3.3V | **3.3V** | ⚠️ 5V 연결 금지 — 칩 손상 |
| | GND | GND | |
| | RST | D9 | |
| | SDA(SS) | D10 | |
| | MOSI | D11 | |
| | MISO | D12 | |
| | SCK | D13 | |
| | IRQ | (미연결) | 폴링 방식이라 안 씀 — 비워두는 게 정상 |

## 보드 B — 액추에이터 담당 (UNO R4 WiFi #2)

| 부품 | 부품 핀 | 아두이노 핀 | 비고 |
|---|---|---|---|
| SG90 서보 | 주황(신호) | **D9** (PWM) | |
| | 빨강 | 5V | SG90 1개는 보드 5V로 충분 |
| | 갈색 | GND | |
| RGB LED (공통 캐소드) | R 다리 | **D3** (PWM) | 각 다리에 **220Ω 직렬** |
| | G 다리 | **D5** (PWM) | |
| | B 다리 | **D6** (PWM) | |
| | 공통(긴 다리) | GND | |

> RGB LED가 **공통 애노드**(불 안 켜지고 반대로 동작)면: 긴 다리를 5V에 연결하고
> 코드에서 `analogWrite(pin, 255 - value)`로 반전.

## 주의사항 (문서에서 확인된 함정)

1. **WiFi는 2.4GHz만** 됨. 학교 와이파이(로그인 페이지)는 접속 불가 → 핸드폰 핫스팟 사용
2. RC522는 **3.3V 전용**. 나머지는 전부 5V
3. DHT11은 부팅 후 첫 1~2초 판독 실패가 정상 (NaN 나오면 스킵)
4. PIR은 전원 인가 후 30~60초 안정화 시간 필요 + 모듈의 딜레이 가변저항을 최소로
5. 서보가 움찔거리면(브라운아웃) USB 전원 대신 보조배터리/외부 5V 사용

## 플랫폼 컨테이너 매핑 (라벨 규격은 진행노트 §1)

현재 AE는 `byeongari` 하나. 보드별 CNT:

| 보드 | CNT (rn) | 방향 | lbl |
|---|---|---|---|
| A | `pir` | 센서값 업로드 | `kind=sensor, type=motion, values=0\|1, desc=현관 움직임 감지` |
| A | `temp` | 센서값 업로드 | `kind=sensor, type=temperature, unit=C, values=0~50` (이미 생성됨) |
| A | `humi` | 센서값 업로드 | `kind=sensor, type=humidity, unit=%, values=20~90` |
| B | `led_cmd` | 명령 폴링 | `kind=actuator, type=light, accepts=ON\|OFF, desc=현관 조명` (이미 생성됨) |
| B | `servo_cmd` | 명령 폴링 | `kind=actuator, type=window, accepts=range=0~180, unit=deg, desc=창문 개폐` |

- 보드 A 루프: PIR/DHT11 읽기 → `pir`, `temp`, `humi`에 CIN POST → 2초 대기
- 보드 B 루프: `led_cmd/la`, `servo_cmd/la` GET → 값대로 실행 → 2초 대기
- 미생성 CNT: `pir`, `humi`, `servo_cmd` → `iot_platform.py`의 컨테이너 생성 함수로 만들 것

# Postman 재설정 가이드 (2026-07-20)

지난번 교훈 반영:
- **Environment 기능이 깨져 있으므로 쓰지 않는다** → 모든 변수는 **컬렉션 Variables**에 저장
- 스크립트에서는 `pm.variables.get(...)` 사용 (environment 스코프 함수 금지)
- **rn(리소스 이름)은 반드시 영문+숫자만**
- 게이트웨이는 `fu / lvl / ofst / lim / ty` 외의 쿼리 파라미터를 걸러냄 (cra, drt, rn 필터 안 됨)

## 1. 새 컬렉션 생성
이름: `IoTCOSS` (기존 Mobius_API_Release2(kor)를 다시 쓰는 것보다, 필요한 요청 6개만 있는 자체 컬렉션이 관리가 쉬움)

## 2. 컬렉션 Variables (컬렉션 → Variables 탭)

| Variable | Value |
|---|---|
| `server` | `https://onem2m.iotcoss.ac.kr` |
| `origin` | `sjuBAR2` |
| `apiKey` | (포털 프로필 하단의 X-API-KEY 값) |
| `lectureId` | (수업 ID) |
| `ae` | `byeongari` |

## 3. 컬렉션 Pre-request Script (컬렉션 → Scripts → Pre-request)

인증 헤더 5개 자동 추가:

```javascript
pm.request.headers.upsert({ key: 'X-API-KEY', value: pm.variables.get('apiKey') });
pm.request.headers.upsert({ key: 'X-AUTH-CUSTOM-CREATOR', value: pm.variables.get('origin') });
pm.request.headers.upsert({ key: 'X-AUTH-CUSTOM-LECTURE', value: pm.variables.get('lectureId') });
pm.request.headers.upsert({ key: 'X-M2M-Origin', value: pm.variables.get('origin') });
pm.request.headers.upsert({ key: 'X-M2M-RI', value: 'req-' + Date.now() + '-' + Math.floor(Math.random() * 10000) });
pm.request.headers.upsert({ key: 'Accept', value: 'application/json' });
```

## 4. 요청 목록 (검증 순서대로)

### 4-1. AE 조회 — 연결 확인
- `GET {{server}}/Mobius/{{ae}}`
- 헤더: (자동) — 200이면 인증 OK

### 4-2. env_data 컨테이너 조회 — 지난번 생성 여부 확인
- `GET {{server}}/Mobius/{{ae}}/env_data`
- 200 → 이미 생성됨 (4-3 건너뜀) / 404 → 4-3으로

### 4-3. env_data 컨테이너 생성
- `POST {{server}}/Mobius/{{ae}}`
- 헤더 추가: `Content-Type: application/json;ty=3`
- Body (raw JSON):
```json
{ "m2m:cnt": { "rn": "env_data" } }
```
- 201 기대. 409면 이미 존재하는 것이니 OK

### 4-4. CIN(센서값) 생성
- `POST {{server}}/Mobius/{{ae}}/env_data`
- 헤더 추가: `Content-Type: application/json;ty=4`
- Body:
```json
{ "m2m:cin": { "con": "{\"temp\": 25.3, \"humi\": 41}" } }
```
- 201 기대

### 4-5. 최신 CIN 조회
- `GET {{server}}/Mobius/{{ae}}/env_data/la`
- 4-4에서 넣은 값이 그대로 나오면 왕복 검증 완료

### 4-6. (다음 단계용) control / rules 컨테이너 생성
- 4-3과 동일, body의 `rn`만 `control`, `rules`로 변경

## 5. 완료 기준
4-1 ~ 4-5가 전부 통과하면 플랫폼 연동 검증 끝 → 코드 재작성 시작 (config에 apiKey/lectureId 그대로 옮기면 됨)

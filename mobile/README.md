# 온살핌 · 복지사 앱 (Expo)

Render API 와 같은 REST 를 쓰는 **현장용 MVP**: 세대 위험도, 알림, 대응 기록.

## Mac 없이 상시 접속 (Render — 대시보드와 같음)

| 방식 | Mac 필요 | 설명 |
|------|----------|------|
| **Expo Go + QR** | ✅ 개발 중만 | JS 를 맥 Metro(8081)에서 받음 — 배포용 아님 |
| **Render 정적 웹** (`onsalpim-care`) | ❌ | `npm run build:web` 결과를 CDN 에 올림 → 폰 **Safari/Chrome URL** |
| **EAS Build (APK/IPA)** | ❌ (빌드는 Expo 클라우드) | 스토어·TestFlight·APK 설치형 — 아래 “네이티브 설치” |

Blueprint `render.yaml` 에 **onsalpim-care** 가 있으면 API 배포 후:

1. Render → **onsalpim-care** → Environment  
   `EXPO_PUBLIC_API_BASE` = `https://onsalpim-api.onrender.com/api` (대시보드 `VITE_API_BASE` 와 동일)
2. **Manual Deploy** (env 바꾼 뒤 재빌드 필수)
3. 폰 브라우저에서 `https://onsalpim-care.onrender.com` 접속  
   - iOS: 공유 → **홈 화면에 추가**  
   - Android: 메뉴 → **홈 화면에 추가**

API·엔진은 기존 **onsalpim-api** 를 그대로 씁니다.

### 네이티브 설치 (선택, App Store 전)

Expo Go 대신 **설치형 앱**이 필요하면 [EAS Build](https://docs.expo.dev/build/introduction/) 로 APK(Android) 또는 TestFlight(iOS) 를 만듭니다.  
앱 안 JS 도 번들에 포함되므로 맥을 켤 필요 없고, API 주소는 빌드 시 `EXPO_PUBLIC_API_BASE` 로 고정합니다.

```bash
npm i -g eas-cli   # 최초 1회
eas login
eas build:configure
eas build -p android --profile preview   # APK 링크
```

## 로컬 개발 (Expo Go)

```bash
cd mobile
npm install
npm start
```

- **Expo Go** 앱 **안의** “Scan QR code” 로 스캔 (iPhone **카메라 앱**이나 Render 대시보드 QR 은 이 프로젝트와 무관)
- 맥에서 `npm start` 가 **켜져 있어야** 함 (Metro `exp://…:8081`)
- API 기본값: `https://onsalpim-api.onrender.com/api`  
  → **설정** 탭에서 바꿀 수 있음

### QR 스캔 후 Playground · Try again 만 보일 때

1. **같은 Wi‑Fi** — 터미널에 `exp://172.x.x.x:8081` 이 보이면 폰도 그 공유기에 연결
2. **iOS 실기기** — 맥에서 `npx expo login`, Expo Go 우측 상단에서 **같은 Expo 계정** 로그인 후 Try again
3. 안 되면 터널: `npm run start:tunnel` (느리지만 공유기 격리·다른 망일 때 동작)
4. **Expo Go 버전** — 이 프로젝트는 SDK 57. App Store Expo Go 가 낮으면 [expo.dev/go](https://expo.dev/go) 에서 맞는 빌드 설치

로컬 API 를 쓸 때 (맥에서 `start_virtual.command`):

- 실기기는 `localhost` 가 안 됨 → 맥 LAN IP 사용  
  예: `http://192.168.0.10:5001/api` (Flask 가 5001 이면 그대로, `/api` 포함)

## 환경 변수

`.env.example` 을 `.env` 로 복사:

```
EXPO_PUBLIC_API_BASE=https://onsalpim-api.onrender.com/api
```

변경 후 `npm start` 재시작.

## 화면

| 탭 | API |
|----|-----|
| 세대 | `GET /care`, `GET /engine/status` |
| 알림 | `GET /alerts`, 상세에서 `POST .../action` |
| 설정 | API 베이스 URL (AsyncStorage) |

표기 규칙은 `IOT/dashboard/src/format.js` 와 맞춤 (`lib/format.ts`).

## v2 예정

- 푸시 알림 (FCM)
- 로그인 / API 키

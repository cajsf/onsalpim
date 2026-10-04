# 온살핌 복지사 앱 — Android · iOS 설치형 빌드

Safari/Chrome **웹 URL**(`onsalpim-care` on Render)과 별도로, 같은 `mobile/` 코드로 **홈 화면에 설치되는 앱**을 만듭니다.  
API는 Render **`onsalpim-api`** (`…/api`)에 연결합니다. care 호스트 URL을 API로 넣으면 404가 납니다.

| 배포 | 용도 |
|------|------|
| **Render Static (web)** | 링크만 공유, 즉시 반영, 설치 불필요 |
| **EAS Build (native)** | APK/AAB · TestFlight/App Store, 앱처럼 풀스크린 |

---

## 1. 한 번만 하는 준비

### Expo · EAS

```bash
cd mobile
npm install
npx eas login          # expo.dev 계정 (무료)
npx eas init           # 프로젝트 연결 → app.json 에 projectId 추가됨
```

`eas.json`의 `EXPO_PUBLIC_API_BASE`가 본인 API와 다르면 수정하거나, EAS 대시보드 **Environment**에 같은 이름으로 Secret을 둡니다.

### Android (Google Play 또는 APK 직접 배포)

- **시연·내부용**: `preview` 프로필 → **APK** (Play 없이 QR/파일 설치 가능)
- **Play 내부 테스트 / 스토어**: `production` → **AAB** + Play Console

Play Console 계정(일회 등록비)이 없어도 **preview APK**만으로 Android는 배포 가능합니다.

### iOS (TestFlight / Ad Hoc)

- **Apple Developer Program** (연 약 $99) 필요
- **TestFlight**: `production` 빌드 → App Store Connect 업로드 (`eas submit`)
- **소수 기기만·빠른 테스트**: `preview` (internal / Ad Hoc) — 기기 UDID 등록 필요, 최대 100대

Apple Developer에서 **Bundle ID** `com.onsalpim.care` 를 App ID로 등록해 두면 EAS가 인증서를 자동으로 맞춥니다. (다른 ID를 쓰려면 `app.json`의 `ios.bundleIdentifier` / `android.package`를 같이 바꿉니다.)

---

## 2. 빌드 명령

```bash
cd mobile

# Android — APK (QR로 설치 링크)
npm run build:preview:android
# 또는: npx eas build -p android --profile preview

# iOS — Ad Hoc (등록된 iPhone만)
npm run build:preview:ios

# 스토어/TestFlight·Play용
npm run build:production:android   # AAB
npm run build:production:ios       # App Store Connect용 IPA
```

빌드가 끝나면 터미널·[expo.dev](https://expo.dev) 대시보드에 **다운로드 QR / 링크**가 나옵니다.

---

## 3. 스토어에 올리기 (선택)

### iOS → TestFlight

1. [App Store Connect](https://appstoreconnect.apple.com)에 앱 생성 (번들 ID `com.onsalpim.care`)
2. `production` iOS 빌드 완료 후:

```bash
npx eas submit -p ios --profile production --latest
```

처음에는 Apple ID·앱 전용 비밀번호·Team ID 입력을 묻습니다. `eas.json`의 `submit.production.ios`에 저장해 두면 이후 자동화할 수 있습니다.

3. App Store Connect → **TestFlight** → 내부/외부 테스터 초대

### Android → Play 내부 테스트

1. Play Console에 앱 생성, **내부 테스트** 트랙 준비
2. Google Cloud **서비스 계정** JSON (Play API) — 로컬만 보관, **git에 올리지 않음**
3. `production` Android 빌드 후:

```bash
npx eas submit -p android --profile production --latest
```

---

## 4. 웹 vs 앱 — API·설정

- 빌드 시 `EXPO_PUBLIC_API_BASE`가 **번들에 박힙니다** (`eas.json` preview/production).
- 앱 안 **더보기 → API 설정**으로 주소를 바꿀 수 있지만, 기본값은 위 env와 동일하게 맞춰 두었습니다.
- Render API **Free 슬립**은 웹과 동일 — 첫 요청이 느릴 수 있습니다.

---

## 5. 자주 묻는 것

**Q. Mac 없이 iOS 빌드 가능?**  
A. 가능합니다. EAS가 클라우드에서 빌드합니다. 제출·TestFlight 설정만 Apple 계정으로 하면 됩니다.

**Q. Expo Go와 차이?**  
A. Expo Go는 개발용 샌드박스입니다. EAS 빌드는 **온살핌 아이콘**이 붙은 독립 앱입니다.

**Q. 코드 수정 후 앱만 빠르게 갱신?**  
A. JS/UI 변경은 [EAS Update](https://docs.expo.dev/eas-update/introduction/)로 OTA 가능(네이티브 설정 변경 시에는 재빌드 필요). 시연 초기에는 **재빌드**만으로도 충분합니다.

**Q. bundle ID를 팀 도메인으로 바꾸고 싶다**  
A. `app.json`의 `ios.bundleIdentifier`, `android.package` 수정 → Apple/Google 콘솔에 동일 ID 등록 → `eas credentials` 재설정.

---

## 6. 프로필 요약 (`eas.json`)

| 프로필 | Android | iOS | distribution |
|--------|---------|-----|--------------|
| **preview** | APK | 기기 등록(Ad Hoc) | internal |
| **production** | AAB | TestFlight/App Store | store |

웹 배포는 그대로 `npm run build:web` → Render `onsalpim-care`입니다. **웹과 앱을 동시에** 써도 됩니다.

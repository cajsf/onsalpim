# 이 파일을 secrets_local.py 로 복사해 실제 키를 넣는다. secrets_local.py 는 저장소에 올리지 않는다(.gitignore).
GEMINI_API_KEY = "여기에 Gemini API 키"
PLATFORM_API_KEY = "여기에 플랫폼 X-API-KEY"
# 여러 회사 모델 비교 실험용 (선택). 없으면 openrouter: 모델만 못 쓴다. https://openrouter.ai/keys
OPENROUTER_API_KEY = ""
# 카카오톡 나에게 보내기 (선택). 비즈니스 채널 키가 아니다.
# 디벨로퍼스 앱의 REST API 키. 리다이렉트 URI 는 아래 주소와 같아야 한다.
KAKAO_REST_API_KEY = ""
KAKAO_CLIENT_SECRET = ""          # 앱에서 클라이언트 시크릿을 켰을 때만
# KAKAO_REDIRECT_URI = "http://127.0.0.1:5001/api/kakao/callback"
# KAKAO_DASHBOARD_URL = "http://localhost:5173/"

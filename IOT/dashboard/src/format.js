// 화면 여러 곳(대시보드·세대 관리)에서 같이 쓰는 표기 규칙.
// 한 곳에만 두어야 같은 값이 화면마다 다르게 보이지 않는다.
import { ref } from 'vue'

/**
 * 화면 공용 시계 — 1초마다 갱신.
 * "N분 전"을 서버가 준 숫자로 그리면 엔진이 멈췄을 때 그 숫자가 굳어 거짓말이 된다.
 * 서버는 '언제'를 주고, 화면이 지금 시각과의 차이를 계속 다시 계산한다.
 */
export const nowMs = ref(Date.now())
setInterval(() => { nowMs.value = Date.now() }, 1000)

/** 서버가 준 시각('2026-09-17T09:05:06', KST·시간대 표기 없음)부터 지금까지 경과 초. 없으면 null. */
export function secondsSince(iso) {
  if (!iso) return null
  const t = Date.parse(iso)            // 시간대 표기가 없으면 브라우저 로컬(KST)로 해석
  return Number.isFinite(t) ? Math.max(0, (nowMs.value - t) / 1000) : null
}

/* 위험도 — 전시 계획안 ⑤의 4분류. 서버(scope.SEVERITIES)와 같은 키를 쓴다 */
export const SEV = {
  NORMAL:       { ko: '정상',      cls: 'normal', prio: '낮음' },
  WATCH:        { ko: '주의',      cls: 'watch',  prio: '보통' },
  URGENT:       { ko: '긴급 확인', cls: 'urgent', prio: '높음' },
  CHECK_DEVICE: { ko: '점검 필요', cls: 'device', prio: '보통' },
}
export const SEV_ORDER = ['URGENT', 'CHECK_DEVICE', 'WATCH', 'NORMAL']

export const TYPE_KO = {
  motion: '움직임', temperature: '온도', humidity: '습도',
  battery: '배터리', light: '조명', window: '창문', card: '카드',
}
export const typeKo = (t) => TYPE_KO[t] || t || '?'

/** 초 → '3분 6초 전' 같은 사람 표기. 판단 근거에는 반올림하지 않고 그대로 쓴다. */
export function fmtAgo(sec) {
  if (sec == null) return '기록 없음'
  const s = Math.floor(sec)
  if (s < 60) return `${s}초 전`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}분 ${s % 60}초 전`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}시간 ${m % 60}분 전` : `${Math.floor(h / 24)}일 ${h % 24}시간 전`
}

/** 무활동 기준은 분으로 저장하지만 화면에는 '8시간'처럼 사람 말로 보여준다. */
export function fmtMinutes(v) {
  const m = parseInt(v, 10)
  if (!Number.isFinite(m)) return '?'
  if (m < 60) return `${m}분`
  const h = Math.floor(m / 60), mm = m % 60
  return mm ? `${h}시간 ${mm}분` : `${h}시간`
}

export function timeOf(iso) { return iso ? iso.slice(11, 16) : '—' }

/** '2026-09-16T14:31:05' → '09/16 14:31' */
export function stampOf(iso) {
  return iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 16)}` : ''
}

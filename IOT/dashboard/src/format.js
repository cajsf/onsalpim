// 화면 여러 곳(대시보드·세대 관리)에서 같이 쓰는 표기 규칙.
// 한 곳에만 두어야 같은 값이 화면마다 다르게 보이지 않는다.
import { ref, watch } from 'vue'

/**
 * 화면 공용 시계 — 1초마다 갱신.
 * "N분 전"을 서버가 준 숫자로 그리면 엔진이 멈췄을 때 그 숫자가 굳어 거짓말이 된다.
 * 서버는 '언제'를 주고, 화면이 지금 시각과의 차이를 계속 다시 계산한다.
 */
export const nowMs = ref(Date.now())
setInterval(() => { nowMs.value = Date.now() }, 1000)

/**
 * 장치 경로를 화면 이름으로 — AE 뒤를 그대로 보여 준다 ('Mobius/byeongari/h101/temp' → 'h101/temp').
 * 세대 컨테이너 구조에서는 끝 이름(temp)만으로 어느 세대 것인지 알 수 없다.
 */
export const devName = (path) => (path || '').split('/').slice(2).join('/') || (path || '')

/** 완료 안내처럼 한 번 보여주고 끝나야 하는 문구 — 값이 들어오면 ms 뒤 저절로 비운다 */
export function autoClear(r, ms = 5000) {
  let t = null
  watch(r, (v) => {
    clearTimeout(t)
    if (v) t = setTimeout(() => { r.value = '' }, ms)
  })
}

/** 서버가 준 시각('2026-09-17T09:05:06+09:00')부터 지금까지 경과 초. 없으면 null. */
export function secondsSince(iso) {
  if (!iso) return null
  const t = Date.parse(iso)            // +09:00 이면 그 순간, 표기가 없으면 브라우저 로컬(KST)
  return Number.isFinite(t) ? Math.max(0, (nowMs.value - t) / 1000) : null
}

/* 위험도 — 전시 계획안 ⑤의 4분류. 서버(scope.SEVERITIES)와 같은 키를 쓴다 */
export const SEV = {
  NORMAL:       { ko: '정상',      cls: 'normal', prio: '낮음' },
  WATCH:        { ko: '주의',      cls: 'watch',  prio: '보통' },
  URGENT:       { ko: '긴급 확인', cls: 'urgent', prio: '높음' },
  CHECK_DEVICE: { ko: '장치 점검', cls: 'device', prio: '보통' },
}
/* 알림 대응 상태 — 서버 engine.alerts_with_actions 의 state 와 같은 키 */
export const ALERT_STATE = {
  open:     { ko: '대응 필요',       cls: 'urgent' },
  missed:   { ko: '응답 없이 지나감', cls: 'muted' },
  assign:   { ko: '배정',            cls: 'life' },
  ack:      { ko: '확인',            cls: 'watch' },
  progress: { ko: '방문·연락 중',     cls: 'watch' },
  done:     { ko: '조치 완료',        cls: 'normal' },
  late:     { ko: '뒤늦게 확인',      cls: 'muted' },
  edit:     { ko: '메모 수정',        cls: 'muted' },   // 기록 줄에만 쓴다 (상태가 아님)
}
/** 조치 완료 때 고르는 결과 — 서버 engine.OUTCOMES 와 같은 키 */
export const OUTCOMES = [
  { id: 'outing', ko: '외출' },
  { id: 'ok', ko: '정상 확인' },
  { id: 'device', ko: '장치 문제' },
  { id: 'visit', ko: '방문 필요' },
]
export const outcomeKo = (id) => OUTCOMES.find((o) => o.id === id)?.ko || ''
export const SEV_ORDER = ['URGENT', 'CHECK_DEVICE', 'WATCH', 'NORMAL']

export const PATTERN_KO = {
  HOT_IDLE: '고온 지속 + 활동 저하',
  MORNING_NONE: '아침 활동 부재',
  NIGHT_WANDER: '야간 활동 변화',
}
export const FOLLOW_KO = {
  RENOTIFY: '재통지',
  ESCALATE: '다음 담당자에게 이관',
}

/** 생활 쪽 낮은 위험은 '생활 확인'. 배터리 주의·장치 점검·긴급 확인은 각자 이름과 색을 쓴다. */
export function sevKo(h) {
  if (h?.life_check) return '생활 확인'
  return SEV[h?.severity]?.ko || ''
}

export function sevClass(h) {
  if (h?.life_check) return 'life'
  return SEV[h?.severity]?.cls || 'normal'
}

/** 알림 한 줄의 위험 이름. 생활 확인은 배터리 주의와 같은 '주의'로 적지 않는다. */
export function alertKo(a) {
  if (a?.outage) return '망 점검'
  if (a?.follow && FOLLOW_KO[a.follow]) return FOLLOW_KO[a.follow]
  if (a?.welfare) return '안부 확인'
  if (a?.device_check && a?.from === a?.to) return '장치 점검'
  if (a?.life_check && a?.to === 'WATCH') return '생활 확인'
  return SEV[a?.to]?.ko || ''
}

export function alertClass(a) {
  if (a?.outage) return 'device'
  if (a?.follow === 'ESCALATE') return 'urgent'
  if (a?.follow === 'RENOTIFY') return 'watch'
  if (a?.welfare) return 'urgent'
  if (a?.device_check && a?.from === a?.to) return 'device'
  if (a?.life_check && a?.to === 'WATCH') return 'life'
  return SEV[a?.to]?.cls || 'normal'
}

/** 알림 문장 앞의 '이전 → 지금'. 화면에 보이는 이름이 같을 때는 비운다. */
export function alertChange(a) {
  if (!a || a.outage || a.welfare) return ''
  const to = alertKo(a)
  const from = a.from ? (SEV[a.from]?.ko || a.from) : '첫 판정'
  if (!to || from === to) return ''
  return `${from} → ${to} · `
}

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

/** 경과 시간. '전'을 붙이지 않는다. 1분 미만만 초를 남긴다. */
export function fmtSpan(sec) {
  if (sec == null || !Number.isFinite(sec)) return ''
  const s = Math.max(0, Math.floor(sec))
  if (s < 60) return `${s}초`
  const m = Math.floor(s / 60)
  if (m < 60) return s % 60 ? `${m}분 ${s % 60}초` : `${m}분`
  const h = Math.floor(m / 60)
  if (h < 24) return m % 60 ? `${h}시간 ${m % 60}분` : `${h}시간`
  const d = Math.floor(h / 24)
  return h % 24 ? `${d}일 ${h % 24}시간` : `${d}일`
}

/**
 * 무활동 진행. 기준은 이 세대의 idle_min(긴급 단계, 없으면 첫 단계)만 쓴다.
 * 기준이 없으면 null — 화면이 시간을 만들어 채우지 않는다.
 * 움직임 시각이 없으면 막대를 0으로 채우지 않는다.
 */
export function idleBar(elapsedS, idleMin, idleLevels, opts = {}) {
  const levels = (Array.isArray(idleLevels) ? idleLevels : [])
    .map((lv) => ({ minutes: Number(lv.minutes), severity: lv.severity }))
    .filter((lv) => Number.isFinite(lv.minutes) && lv.minutes > 0)
  let limitMin = Number(idleMin)
  if (!Number.isFinite(limitMin) || limitMin <= 0) {
    const urgent = levels.find((lv) => lv.severity === 'URGENT')
    limitMin = urgent ? urgent.minutes : (levels[0] ? levels[0].minutes : NaN)
  }
  if (!Number.isFinite(limitMin) || limitMin <= 0) return null

  const away = !!opts.away
  const silent = opts.lifeKnown === false
  const known = elapsedS != null && Number.isFinite(Number(elapsedS))
  const elapsed = known ? Math.max(0, Number(elapsedS)) : null
  const limitS = limitMin * 60
  const ratio = known ? Math.min(1, elapsed / limitS) : null
  const over = known && elapsed > limitS
  const passedWatch = known && levels.some((lv) =>
    lv.severity === 'WATCH' && elapsed > lv.minutes * 60 && elapsed <= limitS)
  const tone = away || silent ? 'held' : !known ? 'unknown' : over ? 'urgent' : passedWatch ? 'watch' : 'ok'
  const limitText = fmtMinutes(limitMin)
  const ticks = levels
    .filter((lv) => lv.minutes < limitMin)
    .map((lv) => ({
      at: lv.minutes / limitMin,
      title: `${fmtMinutes(lv.minutes)} ${SEV[lv.severity]?.ko || ''}`.trim(),
    }))

  let text
  if (!known) text = `${limitText} 기준 · 움직임 기록 없음`
  else if (away) text = `${limitText} 기준 중 ${fmtSpan(elapsed)} 경과 · 부재 중 판정 보류`
  else if (over) text = `${limitText} 기준을 ${fmtSpan(elapsed - limitS)} 넘김`
  else text = `${limitText} 기준 중 ${fmtSpan(elapsed)} 경과`
  if (silent && known) text += ' · 통신 두절 이후는 확인 불가'

  return {
    limitMin,
    elapsed,
    ratio,
    over,
    tone,
    text,
    ticks,
    big: !known ? '—' : (over && !away && !silent) ? `${fmtSpan(elapsed - limitS)} 초과` : fmtSpan(elapsed),
  }
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

/**
 * 온도 한 칸. 보고 주기 × 3 을 넘긴 값은 숫자로 두지 않는다.
 * 주기를 모르면 두절이라고 단정하지 않고, 값 옆에 시각을 붙인다.
 */
export function tempStatus(temp, limitS) {
  if (!Array.isArray(temp) || temp.length < 2 || temp[1] == null || temp[1] === '') return null
  const age = secondsSince(temp[0])
  const n = Number(temp[1])
  const value = Number.isFinite(n) ? `${n}°C` : String(temp[1])
  const when = stampOf(temp[0])
  const known = typeof limitS === 'number' && limitS > 0 && age != null
  if (known && age > limitS) return { silent: true, text: '센서 응답 없음', when }
  if (known) return { silent: false, text: value, when: '' }
  return { silent: false, text: when ? `${value} · ${when}` : value, when: '' }
}

/** '2026-09-16T14:31:05' → '09/16 14:31' */
export function stampOf(iso) {
  return iso ? `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 16)}` : ''
}

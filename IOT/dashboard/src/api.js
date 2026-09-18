const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = data.errors?.join(', ') || data.error || `HTTP ${res.status}`
    throw new Error(msg)
  }
  return data
}

export const api = {
  // force=true → 서버가 트리 캐시를 무시하고 새로 읽는다 (새 장치 꽂은 직후용)
  getDevices: (force = false) => request(`/devices${force ? '?force=1' : ''}`),
  getSensors: () => request('/sensors'),
  getActuators: () => request('/actuators'),
  getEngineStatus: () => request('/engine/status'),
  getRules: () => request('/rules'),
  // 세대별 위험도 판정 — 규칙 엔진의 Watchdog 이 계산한 결과를 읽는다
  getCare: () => request('/care'),
  getAlerts: (limit = 20) => request(`/alerts?limit=${limit}`),
  // 세대 타임라인 — 엔진이 남긴 위험도 변화·움직임 (최근 24시간)
  getHistory: (home) => request(`/history/${encodeURIComponent(home)}`),
  // value 를 같이 보내면 비어 있던 기준값을 채우면서 승인한다
  // replace=true → 같은 세대·같은 위험도로 겹치는 기존 규칙을 끄고 이 규칙으로 대체
  async approveRule(id, value, replace = false) {
    const res = await fetch(`${BASE}/rules/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...(value === undefined ? {} : { value }), replace }),
    })
    return res.json().catch(() => ({}))
  },
  rejectRule: (id) => request(`/rules/${id}/reject`, { method: 'POST' }),
  // 알림 대응 기록 — status: ack | progress | done(메모 필수). 실패하면 errors 가 온다
  async actAlert(id, status, memo = '') {
    const res = await fetch(`${BASE}/alerts/${encodeURIComponent(id)}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, memo }),
    })
    return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }))
  },
  async addRule(sentence) {
    const res = await fetch(`${BASE}/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sentence }),
    })
    return res.json().catch(() => ({}))
  },
  deleteRule: (id) => request(`/rules/${id}`, { method: 'DELETE' }),
  toggleRule: (id) => request(`/rules/${id}/toggle`, { method: 'POST' }),
  // 부재 등록 — 그 기간엔 무활동 판정 보류, 기기 점검은 계속
  getAbsences: (home) => request(`/absences?home=${encodeURIComponent(home)}`),
  async addAbsence(body) {
    const res = await fetch(`${BASE}/absences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }))
  },
  async endAbsence(id) {
    const res = await fetch(`${BASE}/absences/${id}/end`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }))
  },
  // 겹친 무활동 규칙 중 이 규칙을 쓰고 나머지는 끈다
  async keepRule(id) {
    const res = await fetch(`${BASE}/rules/${id}/keep`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }))
  },
  // 예외 대상 후보가 여럿일 때 고른 규칙에 {세대, 값} 예외를 붙인다 (AI 다시 안 부름)
  async overrideRule(id, home, value) {
    const res = await fetch(`${BASE}/rules/${id}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ home, value }),
    })
    return res.json().catch(() => ({ ok: false, errors: [`HTTP ${res.status}`] }))
  },
  async transcribeSpeech(blob) {
    const form = new FormData()
    const ext = blob.type.includes('mp4') ? 'mp4' : 'webm'
    form.append('audio', blob, `speech.${ext}`)
    const res = await fetch(`${BASE}/speech`, { method: 'POST', body: form })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`)
    }
    return data
  },
}

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
  async approveRule(id, value) {
    const res = await fetch(`${BASE}/rules/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(value === undefined ? {} : { value }),
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

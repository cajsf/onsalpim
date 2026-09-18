<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from './api.js'
import { useSpeechRecognition } from './useSpeechRecognition.js'
import HomeBasis from './HomeBasis.vue'
import HomeTimeline from './HomeTimeline.vue'
import AlertItem from './AlertItem.vue'
import AlertToasts from './AlertToasts.vue'
import { SEV, SEV_ORDER, typeKo, fmtAgo, fmtMinutes, timeOf, stampOf } from './format.js'

// 통계 분석은 세대별 활동 이력이 쌓여야 의미가 있는데 아직 저장소가 없어 '준비 중'으로 둔다.
const NAV = [
  { id: 'dashboard', label: '대시보드', icon: 'home', ready: true },
  { id: 'homes',     label: '세대 관리', icon: 'users', ready: true },
  { id: 'rules',     label: '규칙 관리', icon: 'doc',   ready: true },
  { id: 'alerts',    label: '알림 이력', icon: 'bell',  ready: true },
  { id: 'devices',   label: '기기 관리', icon: 'chip',  ready: true },
  { id: 'stats',     label: '통계 분석', icon: 'chart', ready: false },
]

const activeView = ref('dashboard')

// 로고·이름을 누르면 처음 화면(대시보드)으로
function goHome() {
  activeView.value = 'dashboard'
  window.scrollTo({ top: 0 })
}
const care = ref({ homes: [], updated: null, stale: true, message: '' })
const rules = ref([])
const alerts = ref([])
const alertFilter = ref('todo')      // 알림 이력: 미완료만 / 전체
// open = 아무도 안 본 알림 (배지·팝업). 확인·방문 중도 조치 완료 전까지는 끝난 게 아니다 (미완료 탭).
const openAlerts = computed(() => alerts.value.filter((a) => a.state === 'open'))
const todoAlerts = computed(() => alerts.value.filter((a) => ['open', 'ack', 'progress'].includes(a.state)))
const shownAlerts = computed(() => alertFilter.value === 'todo' ? todoAlerts.value : alerts.value)

/* 새 알림 소리 — 전시장처럼 끄고 싶은 곳이 있다. 이 브라우저에만 기억한다 */
const soundOn = ref(true)
try { soundOn.value = localStorage.getItem('onsalpim.sound') !== 'off' } catch { /* 저장소를 못 쓰면 켠 상태 */ }
function toggleSound() {
  soundOn.value = !soundOn.value
  try { localStorage.setItem('onsalpim.sound', soundOn.value ? 'on' : 'off') } catch { /* 무시 */ }
}
/* 대응을 누르면 서버 응답으로 그 알림만 바로 고치고, 전체 새로고침은 뒤에서 */
function onAlertChanged(p) {
  if (p?.log) {
    alerts.value = alerts.value.map((a) => a.id === p.id
      ? { ...a, log: p.log, state: p.log.at(-1).status,
          first_response_s: (Date.parse(p.log[0].at) - Date.parse(a.ts)) / 1000 }
      : a)
  }
  refresh()
}
function openHome(home) {
  selectedHomeId.value = home
  activeView.value = 'homes'
}
const devices = ref([])
const engineRunning = ref(false)
const engineMessage = ref('')
const connectionError = ref('')
const nowText = ref('')

/* 규칙 만들기 */
const sentence = ref('')
const loading = ref(false)
const inputTab = ref('nl')
const pipelineSteps = ref([])
const lastResult = ref(null)
const ruleError = ref('')
const clarify = ref('')
const ruleWarnings = ref([])
const rulePlan = ref('')
const fillValue = ref('')
const lastSentence = ref('')   // 성공하면 입력창은 비우지만 요약 카드에는 남겨야 한다

/* 표 필터 */
const filter = ref('all')
const search = ref('')

/* 펼쳐진 세대 — 판단 근거를 보여준다 */
const expanded = ref(new Set())
function toggleRow(home) {
  const s = new Set(expanded.value)
  s.has(home) ? s.delete(home) : s.add(home)
  expanded.value = s
}

const { supported: speechSupported, listening, transcribing, speechError, start: toggleSpeech } =
  useSpeechRecognition((text) => { sentence.value = text })

const examples = [
  '전체 세대에서 8시간 동안 움직임이 없으면 긴급으로 표시해줘',
  '102호만 무활동 기준을 6시간으로 바꿔줘',
  '온도가 30도 이상이면 주의 상태로 표시해줘',
  '가스가 감지되면 창문 열어줘',
]

/* ────────── 데이터 ────────── */

let timer = null
let clockTimer = null

async function refresh() {
  try {
    // 장치 목록은 공용 서버를 읽어 수 초 걸릴 수 있다 — 기다리면 나머지 화면까지 늦어진다
    api.getDevices().then((d) => { devices.value = d }).catch(() => {})
    const [c, r, a, eng] = await Promise.all([
      api.getCare(), api.getRules(), api.getAlerts(100), api.getEngineStatus(),
    ])
    care.value = c
    rules.value = r
    alerts.value = a
    engineRunning.value = eng.running
    engineMessage.value = eng.message
    connectionError.value = ''
  } catch (e) {
    connectionError.value = `서버 연결 실패: ${e.message}`
  }
}

function tickClock() {
  const d = new Date()
  const days = ['일', '월', '화', '수', '목', '금', '토']
  nowText.value =
    `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${days[d.getDay()]}) ` +
    `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  refresh(); tickClock()
  timer = setInterval(refresh, 3000)
  clockTimer = setInterval(tickClock, 10000)
})
onUnmounted(() => { clearInterval(timer); clearInterval(clockTimer) })

/* ────────── 집계 ────────── */

const homes = computed(() => care.value.homes || [])
const pendingRules = computed(() => rules.value.filter((r) => r.status === 'pending'))
const activeRules = computed(() => rules.value.filter((r) => r.status !== 'pending'))

const counts = computed(() => {
  const c = { NORMAL: 0, WATCH: 0, URGENT: 0, CHECK_DEVICE: 0 }
  for (const h of homes.value) if (c[h.severity] !== undefined) c[h.severity]++
  return c
})

/* ────────── 세대 관리 ────────── */

/**
 * 세대 목록 — 판정 결과(care)와 장치 트리(devices) 양쪽에서 모은다.
 * 움직임 센서가 없는 세대는 판정 대상이 아니라 care 에 없지만, 장치가 등록돼 있으면 목록에는 보여야 한다.
 * 세대 명단은 코드에 없고 트리의 home= 라벨에서만 나온다.
 */
const homeList = computed(() => {
  const ids = new Set([
    ...homes.value.map((h) => h.home),
    ...devices.value.map((d) => d.meta?.home).filter(Boolean),
  ])
  return [...ids]
    .sort((a, b) => Number(a) - Number(b) || a.localeCompare(b))
    .map((id) => ({
      home: id,
      care: homes.value.find((h) => h.home === id) || null,
      devices: devices.value.filter((d) => d.meta?.home === id),
    }))
})

const selectedHomeId = ref(null)
const selectedHome = computed(() =>
  homeList.value.find((x) => x.home === selectedHomeId.value) || homeList.value[0] || null)

/** 이 세대에 걸린 규칙 — 어느 세대에 걸리는지는 서버가 전개한 결과(care.rules)를 그대로 쓴다. */
function rulesOfHome(entry) {
  return (entry?.care?.rules || []).map((item) => {
    const full = rules.value.find((r) => r.id === item.id)
    const ov = full?.rule?.overrides?.[entry.home]
    return { id: item.id, sentence: item.sentence, rule: full?.rule, override: ov?.value ?? null }
  })
}

function alertsOfHome(home) {
  return alerts.value.filter((a) => a.home === home)
}

/** 이 세대 기준을 바꾸는 문장을 입력창에 준비해둔다. 값은 복지사가 직접 채운다. */
function editHomeThreshold(home) {
  sentence.value = `${home}호만 무활동 기준을 `
  inputTab.value = 'nl'
  activeView.value = 'dashboard'
}

const lowBattery = computed(() =>
  homes.value.filter((h) => h.battery !== null && h.battery !== undefined && h.battery < 20))

const tabs = computed(() => [
  { id: 'all',     label: '전체',       n: homes.value.length },
  { id: 'urgent',  label: '긴급',       n: counts.value.URGENT },
  { id: 'device',  label: '점검 필요',  n: counts.value.CHECK_DEVICE },
  { id: 'battery', label: '배터리 부족', n: lowBattery.value.length },
  { id: 'pending', label: '승인 대기',  n: pendingRules.value.length },
])

const visibleHomes = computed(() => {
  let list = [...homes.value]
  if (filter.value === 'urgent') list = list.filter((h) => h.severity === 'URGENT')
  else if (filter.value === 'device') list = list.filter((h) => h.severity === 'CHECK_DEVICE')
  else if (filter.value === 'battery') list = list.filter((h) => h.battery !== null && h.battery < 20)

  const q = search.value.trim()
  if (q) {
    list = list.filter((h) =>
      h.home.includes(q) ||
      (SEV[h.severity]?.ko || '').includes(q) ||
      (h.rules || []).some((r) => r.sentence.includes(q)))
  }
  return list.sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity))
})

/* 도넛 — 위험도 분포 */
const donut = computed(() => {
  const total = homes.value.length || 1
  const R = 52, C = 2 * Math.PI * R
  let offset = 0
  return SEV_ORDER.filter((k) => counts.value[k] > 0).map((k) => {
    const len = (counts.value[k] / total) * C
    const seg = { key: k, len, gap: C - len, offset: -offset, cls: SEV[k].cls, n: counts.value[k] }
    offset += len
    return seg
  })
})

/* ────────── 규칙 표시용 문장 만들기 ────────── */

function condText(rule) {
  const w = rule?.when || {}
  if (w.op === 'idle_over_m')
    return `${typeKo(w.type)}이 ${fmtMinutes(w.value)} 이상 없음 (${w.type || '?'} 센서 기준)`
  const target = w.type ? typeKo(w.type) : (w.path || '').split('/').pop()
  return `${target} ${w.op} ${w.value}`
}

function actText(rule) {
  const acts = rule?.then || []
  return acts.map((a) => (a.severity
    ? `${SEV[a.severity]?.ko || a.severity} 상태로 표시 · 복지사에게 알림`
    : `${(a.path || '').split('/').pop()} = ${a.value}`)).join(', ')
}

function scopeText(rule) {
  const s = (rule?.scope || {}).homes
  if (!s) return '장치 직접 지정'
  if (String(s).toUpperCase() === 'ALL') return '전체 세대'
  return `${s}호`
}

function prioText(rule) {
  const sev = (rule?.then || []).find((a) => a.severity)?.severity
  return sev ? `${SEV[sev].prio} (${SEV[sev].ko})` : '보통'
}

/**
 * 예외가 '실제로 판정을 바꿨는지' 따진다.
 *
 * 값이 다른 것과 결과가 달라지는 것은 다르다. 102호처럼 무활동이 양쪽 기준을 모두 넘으면
 * 예외가 걸려 있어도 판정은 같다. 그때 "예외 때문에 긴급"이라고 쓰면 화면이 거짓을 말한다.
 * 검토의견 02의 증거로 쓸 문구이므로 실제로 갈리는 경우에만 강조한다.
 */
function overrideChangedVerdict(h) {
  const a = h.applied
  // 통신이 끊긴 세대는 판정이 CHECK_DEVICE 로 고정되므로 예외가 갈랐다고 말할 수 없다
  if (!a || a.source !== 'override' || h.idle_s == null || !h.life_known) return false
  const idleMin = h.idle_s / 60
  return (idleMin > Number(a.minutes)) !== (idleMin > Number(a.common))
}

function overrideText(rule) {
  const ov = rule?.overrides || {}
  const keys = Object.keys(ov)
  if (!keys.length) return ''
  const idle = (rule?.when || {}).op === 'idle_over_m'
  return keys.map((k) => `${k}호 ${idle ? fmtMinutes(ov[k].value) : ov[k].value}`).join(', ')
}

/* ────────── 동작 ────────── */

async function submitRule() {
  const text = sentence.value.trim()
  if (!text) return
  lastSentence.value = text
  loading.value = true
  ruleError.value = ''; clarify.value = ''; ruleWarnings.value = []
  rulePlan.value = ''; lastResult.value = null
  pipelineSteps.value = [
    { id: 'translate', label: 'LLM 번역', status: 'running', detail: 'Gemini에 문장 전송 중…' },
    { id: 'validate', label: '검증기', status: 'pending', detail: '대기 중' },
    { id: 'scope', label: '범위·예외 검증', status: 'pending', detail: '대기 중' },
    { id: 'conflict', label: '충돌 검사', status: 'pending', detail: '대기 중' },
    { id: 'save', label: '저장', status: 'pending', detail: '대기 중' },
  ]
  try {
    const result = await api.addRule(text)
    if (result.steps) pipelineSteps.value = result.steps
    ruleWarnings.value = result.warnings || []
    rulePlan.value = result.plan || ''
    lastResult.value = result

    if (result.status === 'needs_clarification') {
      clarify.value = result.questions?.join(' ') || '기준값을 지정해 주세요.'
    } else if (!result.ok) {
      ruleError.value = result.errors?.join(' ') || '규칙 생성에 실패했습니다.'
    } else {
      sentence.value = ''
    }
    await refresh()
  } catch (e) {
    ruleError.value = e.message
    pipelineSteps.value = []
  } finally {
    loading.value = false
  }
}

async function approve(id, value, replace = false) {
  const res = await api.approveRule(id, value, replace)
  if (!res.ok) { ruleError.value = res.errors?.join(' ') || '승인에 실패했습니다.'; return }
  ruleError.value = ''; clarify.value = ''; fillValue.value = ''
  if (lastResult.value?.id === id) lastResult.value = null
  await refresh()
}

/* 삭제·거부는 버튼을 한 번 더 눌러야 실행된다 (4초 안에).
   브라우저 confirm() 창은 환경에 따라 자동으로 닫혀(앱 안 브라우저 등) 아무 반응 없이 취소된다. */
const confirmingId = ref(null)
const ruleBusy = ref(null)          // 요청 중인 규칙 — 응답 전 연타를 막는다
let confirmTimer = null

async function reject(id) {
  if (confirmingId.value !== id) {
    confirmingId.value = id
    clearTimeout(confirmTimer)
    confirmTimer = setTimeout(() => { confirmingId.value = null }, 4000)
    return
  }
  if (ruleBusy.value) return
  ruleBusy.value = id
  try {
    const res = await api.rejectRule(id)
    if (!res.ok) { ruleError.value = res.errors?.join(' ') || '삭제에 실패했습니다.'; return }
    ruleError.value = ''
    if (lastResult.value?.id === id) lastResult.value = null
    await refresh()
  } catch (e) {
    ruleError.value = `삭제에 실패했습니다: ${e.message}`
  } finally {
    ruleBusy.value = null
    confirmingId.value = null
  }
}

async function toggleRule(id) {
  if (ruleBusy.value) return
  ruleBusy.value = id
  try {
    await api.toggleRule(id)
    ruleError.value = ''
    await refresh()
  } catch (e) {
    ruleError.value = e.message        // 겹치는 규칙이 켜져 있으면 서버가 거부한다
  } finally { ruleBusy.value = null }
}
function useExample(ex) { sentence.value = ex; inputTab.value = 'nl' }
function stepIcon(s) { return ({ ok: '✓', fail: '✗', skip: '—', running: '⋯', pending: '○', warn: '!' })[s] || '○' }

</script>

<template>
  <div class="app">
    <!-- ══════════ 좌측 내비게이션 ══════════ -->
    <aside class="sidebar">
      <a class="brand" href="/" title="처음 화면으로" @click.prevent="goHome">
        <div class="brand-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 10.5 12 3l9 7.5" />
            <path d="M5.5 9.5V20h13V9.5" />
            <path d="M12 16.5s-2.6-1.8-2.6-3.4a1.5 1.5 0 0 1 2.6-1 1.5 1.5 0 0 1 2.6 1c0 1.6-2.6 3.4-2.6 3.4z" />
          </svg>
        </div>
        <div>
          <p class="brand-name">온살핌</p>
          <p class="brand-sub">말로 만들고, 한눈에 살피다</p>
        </div>
      </a>

      <nav class="nav">
        <button
          v-for="n in NAV"
          :key="n.id"
          class="nav-item"
          :class="{ active: activeView === n.id, disabled: !n.ready }"
          :disabled="!n.ready"
          :title="n.ready ? n.label : '준비 중'"
          @click="activeView = n.id"
        >
          <span class="nav-dot" :class="n.icon"></span>
          {{ n.label }}
          <span v-if="n.id === 'rules' && pendingRules.length" class="nav-badge">
            {{ pendingRules.length }}
          </span>
          <span v-else-if="n.id === 'alerts' && openAlerts.length" class="nav-badge" title="대응 필요 알림">
            {{ openAlerts.length }}
          </span>
          <span v-else-if="!n.ready" class="nav-soon">준비 중</span>
        </button>
      </nav>

      <div class="side-foot">
        <p>사람이 있는<br />더 따뜻한 기술,<br /><strong>온살핌</strong>이 함께합니다.</p>
      </div>
    </aside>

    <!-- ══════════ 본문 ══════════ -->
    <div class="main">
      <header class="topbar">
        <div>
          <h1>온살핌 웹 대시보드</h1>
          <p class="topbar-sub">말로 만들고, 한눈에 살피다</p>
        </div>
        <div class="topbar-right">
          <div class="search">
            <span class="search-icon">⌕</span>
            <input v-model="search" type="text" placeholder="세대, 상태, 규칙을 검색해보세요" />
          </div>
          <button class="btn sm ghost" :title="soundOn ? '새 알림 소리 끄기' : '새 알림 소리 켜기'" @click="toggleSound">
            {{ soundOn ? '🔔 소리 켬' : '🔕 소리 끔' }}
          </button>
          <span class="chip" :class="engineRunning ? 'chip-on' : 'chip-off'" :title="engineMessage">
            {{ engineRunning ? '실시간 모니터링 중' : '엔진 미실행' }}
          </span>
          <div class="who">
            <div class="avatar">복</div>
            <div>
              <p class="who-name">복지사님</p>
              <p class="who-org">세종대학교</p>
            </div>
          </div>
        </div>
      </header>

      <p class="stamp">{{ nowText }}</p>
      <p v-if="care.rule_conflicts && care.rule_conflicts.length" class="banner warn">
        같은 세대에 같은 위험도의 무활동 규칙이 겹쳐 있습니다
        ({{ care.rule_conflicts.map((p) => '#' + p.join('·#')).join(', ') }}). 더 짧은 기준을 적용 중입니다 —
        <a href="#" @click.prevent="activeView = 'rules'">규칙 관리</a>에서 하나를 끄거나 지워 주세요.
      </p>
      <p v-if="connectionError" class="banner err">{{ connectionError }}</p>
      <p v-else-if="!engineRunning" class="banner warn">
        규칙 엔진이 실행 중이 아닙니다. 세대 판정이 갱신되지 않습니다 —
        <code class="mono">python -c "import engine; engine.loop()"</code>
      </p>
      <p v-else-if="care.stale" class="banner warn">
        판정이 {{ timeOf(care.updated) }} 이후 갱신되지 않았습니다. 화면의 상태가 최신이 아닐 수 있습니다.
      </p>

      <!-- ────────── 대시보드 ────────── -->
      <main v-if="activeView === 'dashboard'" class="content">
        <!-- KPI -->
        <section class="kpis">
          <article class="kpi kpi-blue">
            <div class="kpi-ico">👥</div>
            <div>
              <p class="kpi-label">전체 모니터링 세대</p>
              <p class="kpi-value">{{ homes.length }} <span>세대</span></p>
              <p class="kpi-foot">등록된 장치에서 자동 발견</p>
            </div>
          </article>
          <article class="kpi kpi-red">
            <div class="kpi-ico">🚨</div>
            <div>
              <p class="kpi-label">긴급 알림</p>
              <p class="kpi-value">{{ counts.URGENT }} <span>건</span></p>
              <p class="kpi-foot">장시간 무활동 · 통신 정상</p>
            </div>
          </article>
          <article class="kpi kpi-orange">
            <div class="kpi-ico">🔧</div>
            <div>
              <p class="kpi-label">기기 이상</p>
              <p class="kpi-value">{{ counts.CHECK_DEVICE }} <span>건</span></p>
              <p class="kpi-foot">통신 두절 — 생활 판정 보류</p>
            </div>
          </article>
          <article class="kpi kpi-green">
            <div class="kpi-ico">📋</div>
            <div>
              <p class="kpi-label">승인 대기 규칙</p>
              <p class="kpi-value">{{ pendingRules.length }} <span>건</span></p>
              <p class="kpi-foot">승인해야 실행됩니다</p>
            </div>
          </article>
        </section>

        <div class="cols">
          <!-- 세대 현황 -->
          <section class="card">
            <div class="card-head">
              <div>
                <h2>세대 현황</h2>
                <p class="hint">각 세대의 생활 상태와 기기 상태를 실시간으로 확인할 수 있습니다.</p>
              </div>
              <button class="btn ghost" @click="refresh">새로고침</button>
            </div>

            <div class="tabs">
              <button
                v-for="t in tabs" :key="t.id"
                class="tab" :class="{ on: filter === t.id, [t.id]: true }"
                @click="filter = t.id"
              >{{ t.label }} ({{ t.n }})</button>
            </div>

            <div v-if="!homes.length" class="empty">
              아직 판정된 세대가 없습니다.
              <span v-if="!engineRunning">규칙 엔진을 실행해 주세요.</span>
              <span v-else>보드에 <code class="mono">home=</code> 라벨이 붙어 있는지 확인해 주세요.</span>
            </div>

            <div v-else-if="filter === 'pending'" class="pending-list">
              <p v-if="!pendingRules.length" class="empty">승인 대기 중인 규칙이 없습니다.</p>
              <article v-for="r in pendingRules" :key="r.id" class="pending-item">
                <div class="pending-top">
                  <span class="tag tag-wait">승인 대기</span>
                  <p class="pending-sentence">"{{ r.sentence }}"</p>
                </div>
                <dl class="mini">
                  <div><dt>조건</dt><dd>{{ condText(r.rule) }}</dd></div>
                  <div><dt>동작</dt><dd>{{ actText(r.rule) }}</dd></div>
                  <div><dt>적용 대상</dt><dd>{{ scopeText(r.rule) }}</dd></div>
                </dl>
                <p v-for="q in r.questions" :key="q" class="msg clarify">{{ q }}</p>
                <p v-for="c in r.conflicts || []" :key="c.id" class="msg warn">
                  ⚠ 기존 규칙 #{{ c.id }}({{ c.summary }})과 {{ c.homes.join(', ') }}호에서 같은 위험도로 겹칩니다.
                  <template v-if="c.covers_all">대체하면 #{{ c.id }}은(는) 예외까지 함께 꺼지고, 대체 기록이 남습니다.</template>
                  <template v-else>일부 세대만 겹쳐 대체할 수 없습니다 — 그 세대만 바꾸려면 "○호만 무활동 기준을 …"처럼 예외로 입력해 주세요.</template>
                </p>
                <div class="pending-act">
                  <input
                    v-if="r.questions && r.questions.length"
                    v-model="fillValue" class="fill" type="text" placeholder="기준값 · 분 (예: 480 = 8시간)"
                  />
                  <button class="btn ghost" :class="{ danger: confirmingId === r.id }" :disabled="ruleBusy === r.id" @click="reject(r.id)">{{ confirmingId === r.id ? '한 번 더 누르면 거부' : '거부' }}</button>
                  <button class="btn primary" :disabled="(r.conflicts || []).some((c) => !c.covers_all)"
                      @click="approve(r.id, fillValue || undefined, !!(r.conflicts || []).length)">
                {{ (r.conflicts || []).length ? '기존 규칙 대체' : '승인하기' }}
              </button>
                </div>
              </article>
            </div>

            <table v-else class="grid">
              <thead>
                <tr>
                  <th>세대</th><th>생활 상태</th><th>기기 상태</th>
                  <th>위험도</th><th>적용 규칙</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="h in visibleHomes" :key="h.home">
                <tr class="crow" :class="{ open: expanded.has(h.home) }" @click="toggleRow(h.home)">
                  <td class="home-cell">
                    <span class="caret">{{ expanded.has(h.home) ? '▾' : '▸' }}</span>{{ h.home }}호
                  </td>
                  <td>
                    <span class="dot" :class="h.life_known ? SEV[h.severity]?.cls : 'unknown'"></span>
                    {{ h.life }}
                  </td>
                  <td>
                    <span class="dot" :class="h.severity === 'CHECK_DEVICE' ? 'device' : 'normal'"></span>
                    {{ h.device }}
                  </td>
                  <td>
                    <span class="tag" :class="'tag-' + SEV[h.severity]?.cls">
                      {{ SEV[h.severity]?.ko }}
                    </span>
                  </td>
                  <td class="rule-cell">
                    <template v-if="h.rules && h.rules.length">
                      <span class="sent" :title="h.rules.map((r) => r.sentence).join('\n')">
                        {{ h.rules[0].sentence }}
                      </span>
                      <span v-if="h.rules.length > 1" class="more">외 {{ h.rules.length - 1 }}개</span>
                      <span v-if="h.applied && h.applied.source === 'override'"
                            class="ovr" :class="{ decisive: overrideChangedVerdict(h) }">
                        예외 {{ fmtMinutes(h.applied.minutes) }} (공통 {{ fmtMinutes(h.applied.common) }})
                        <template v-if="overrideChangedVerdict(h)">
                          — 예외가 판정을 바꿈
                        </template>
                      </span>
                    </template>
                    <span v-else class="muted">적용 규칙 없음</span>
                  </td>
                </tr>

                <!-- 판단 근거 — 결과만 보고도 판단 과정을 따라갈 수 있어야 한다 -->
                <tr v-if="expanded.has(h.home)" class="detail">
                  <td colspan="5"><HomeBasis :h="h" /></td>
                </tr>
                </template>
                <tr v-if="!visibleHomes.length"><td colspan="5" class="empty">해당 조건의 세대가 없습니다.</td></tr>
              </tbody>
            </table>
          </section>

          <!-- 규칙 만들기 -->
          <section class="card make">
            <div class="card-head">
              <div>
                <h2>규칙 만들기</h2>
                <p class="hint">일상적인 말로 규칙을 작성하면, AI가 구조화하고 복지사가 승인합니다.</p>
              </div>
            </div>

            <div class="seg">
              <button class="seg-btn" :class="{ on: inputTab === 'nl' }" @click="inputTab = 'nl'">
                자연어로 입력하기
              </button>
              <button class="seg-btn" :class="{ on: inputTab === 'json' }" @click="inputTab = 'json'">
                구조화 미리보기
              </button>
            </div>

            <div v-if="inputTab === 'nl'">
              <div class="ta-wrap" :class="{ listening }">
                <textarea
                  v-model="sentence" :disabled="loading" maxlength="200" rows="3"
                  placeholder="예: 전체 세대에서 8시간 이상 움직임이 없으면 복지사에게 긴급 알림을 보내줘."
                ></textarea>
                <div class="ta-foot">
                  <button
                    v-if="speechSupported" type="button" class="mic"
                    :class="{ active: listening, busy: transcribing }"
                    :disabled="loading || transcribing" @click="toggleSpeech"
                    :title="listening ? '녹음 중 — 다시 누르면 변환' : '음성으로 입력'"
                  >🎙</button>
                  <span class="count">{{ sentence.length }}/200</span>
                </div>
              </div>

              <button class="btn primary wide" :disabled="loading || !sentence.trim()" @click="submitRule">
                {{ loading ? '규칙을 만드는 중…' : '✨ 규칙 생성하기' }}
              </button>

              <p v-if="listening" class="msg info">🎤 녹음 중… 말씀하신 뒤 마이크를 다시 눌러 주세요</p>
              <p v-if="transcribing" class="msg info">⏳ 음성을 글로 변환하는 중…</p>
              <p v-if="speechError" class="msg err">{{ speechError }}</p>

              <div class="chips">
                <button v-for="ex in examples" :key="ex" class="ex" @click="useExample(ex)">{{ ex }}</button>
              </div>
            </div>

            <pre v-else class="json mono">{{
              lastResult && lastResult.rule
                ? JSON.stringify(lastResult.rule, null, 2)
                : '규칙을 생성하면 AI가 만든 구조화 JSON이 여기에 표시됩니다.'
            }}</pre>

            <p v-if="ruleError" class="msg err">{{ ruleError }}</p>
            <p v-if="clarify" class="msg clarify">{{ clarify }}</p>
            <p v-for="w in ruleWarnings" :key="w" class="msg warn">{{ w }}</p>

            <!-- 파이프라인 -->
            <div v-if="pipelineSteps.length" class="pipe">
              <p class="sec-title">규칙 생성 파이프라인</p>
              <div v-for="(s, i) in pipelineSteps" :key="s.id" class="pstep" :class="s.status">
                <span class="pico">{{ stepIcon(s.status) }}</span>
                <span class="pnum">{{ i + 1 }}</span>
                <span class="plabel">{{ s.label }}</span>
                <span class="pdetail">{{ s.detail }}</span>
              </div>
            </div>

            <!-- 생성된 규칙 요약 -->
            <div v-if="lastResult && lastResult.rule && lastResult.id" class="summary">
              <p class="sec-title ok">
                <span class="tick">✓</span> 생성된 규칙 요약
                <span class="ai-badge">AI 분석 완료</span>
              </p>
              <dl class="mini">
                <div><dt>규칙 이름</dt><dd>{{ lastSentence }}</dd></div>
                <div><dt>조건</dt><dd>{{ condText(lastResult.rule) }}</dd></div>
                <div><dt>동작</dt><dd>{{ actText(lastResult.rule) }}</dd></div>
                <div><dt>적용 대상</dt><dd>{{ scopeText(lastResult.rule) }}</dd></div>
                <div v-if="overrideText(lastResult.rule)">
                  <dt>세대별 예외</dt><dd>{{ overrideText(lastResult.rule) }}</dd>
                </div>
                <div><dt>우선순위</dt><dd><span class="tag tag-urgent">{{ prioText(lastResult.rule) }}</span></dd></div>
              </dl>

              <pre v-if="rulePlan" class="plan mono">{{ rulePlan }}</pre>
              <p v-for="c in lastResult.conflicts || []" :key="c.id" class="msg warn">
                ⚠ 기존 규칙 #{{ c.id }}({{ c.summary }})과 {{ c.homes.join(', ') }}호에서 같은 위험도로 겹칩니다.
                <template v-if="c.covers_all">대체하면 #{{ c.id }}은(는) 예외까지 함께 꺼집니다.</template>
                <template v-else>일부 세대만 겹쳐 대체할 수 없습니다 — 예외로 입력해 주세요.</template>
              </p>

              <div class="summary-act">
                <input
                  v-if="lastResult.status === 'needs_clarification'"
                  v-model="fillValue" class="fill" type="text" placeholder="기준값 · 분 (예: 480 = 8시간)"
                />
                <button class="btn ghost" :class="{ danger: confirmingId === lastResult.id }" :disabled="ruleBusy === lastResult.id" @click="reject(lastResult.id)">{{ confirmingId === lastResult.id ? '한 번 더 누르면 거부' : '거부' }}</button>
                <button class="btn primary" :disabled="(lastResult.conflicts || []).some((c) => !c.covers_all)"
                        @click="approve(lastResult.id, fillValue || undefined, !!(lastResult.conflicts || []).length)">
                  {{ (lastResult.conflicts || []).length ? '기존 규칙 대체' : '승인하기' }}
                </button>
              </div>
            </div>
          </section>
        </div>

        <div class="cols">
          <!-- 위험도 분포 -->
          <section class="card">
            <div class="card-head"><h2>위험도 분포</h2></div>
            <div class="donut-row">
              <svg class="donut" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r="52" class="track" />
                <circle
                  v-for="s in donut" :key="s.key" cx="70" cy="70" r="52"
                  class="seg" :class="s.cls"
                  :stroke-dasharray="`${s.len} ${s.gap}`" :stroke-dashoffset="s.offset"
                />
                <text x="70" y="66" class="dn">{{ homes.length }}</text>
                <text x="70" y="86" class="dl">세대</text>
              </svg>
              <ul class="legend">
                <li v-for="k in SEV_ORDER" :key="k">
                  <span class="dot" :class="SEV[k].cls"></span>
                  {{ SEV[k].ko }}
                  <strong>{{ counts[k] }}</strong>
                  <span class="muted">
                    ({{ homes.length ? Math.round((counts[k] / homes.length) * 100) : 0 }}%)
                  </span>
                </li>
              </ul>
            </div>
          </section>

          <!-- 최근 알림 -->
          <section class="card">
            <div class="card-head">
              <h2>최근 알림</h2>
              <button class="btn ghost" @click="activeView = 'alerts'">전체보기 →</button>
            </div>
            <p v-if="!alerts.length" class="empty">아직 기록된 알림이 없습니다. 위험도가 바뀔 때만 남습니다.</p>
            <ul v-else class="alerts">
              <AlertItem v-for="a in alerts.slice(0, 5)" :key="a.id" :a="a" compact />
            </ul>
          </section>
        </div>
      </main>

      <!-- ────────── 규칙 관리 ────────── -->
      <main v-else-if="activeView === 'rules'" class="content">
        <section class="card">
          <div class="card-head">
            <div>
              <h2>승인 대기 규칙</h2>
              <p class="hint">AI가 만든 규칙은 복지사가 승인해야 실행됩니다.</p>
            </div>
            <span class="count">{{ pendingRules.length }}건</span>
          </div>
          <p v-if="ruleError" class="msg err">{{ ruleError }}</p>
          <p v-if="!pendingRules.length" class="empty">승인 대기 중인 규칙이 없습니다.</p>
          <article v-for="r in pendingRules" :key="r.id" class="pending-item">
            <div class="pending-top">
              <span class="tag tag-wait">승인 대기</span>
              <p class="pending-sentence">"{{ r.sentence }}"</p>
              <span class="muted mono">{{ stampOf(r.created) }}</span>
            </div>
            <dl class="mini">
              <div><dt>조건</dt><dd>{{ condText(r.rule) }}</dd></div>
              <div><dt>동작</dt><dd>{{ actText(r.rule) }}</dd></div>
              <div><dt>적용 대상</dt><dd>{{ scopeText(r.rule) }}</dd></div>
            </dl>
            <p v-for="q in r.questions" :key="q" class="msg clarify">{{ q }}</p>
            <p v-for="c in r.conflicts || []" :key="c.id" class="msg warn">
              ⚠ 기존 규칙 #{{ c.id }}({{ c.summary }})과 {{ c.homes.join(', ') }}호에서 같은 위험도로 겹칩니다.
              <template v-if="c.covers_all">대체하면 #{{ c.id }}은(는) 예외까지 함께 꺼지고, 대체 기록이 남습니다.</template>
              <template v-else>일부 세대만 겹쳐 대체할 수 없습니다 — 그 세대만 바꾸려면 "○호만 무활동 기준을 …"처럼 예외로 입력해 주세요.</template>
            </p>
            <div class="pending-act">
              <input
                v-if="r.questions && r.questions.length"
                v-model="fillValue" class="fill" type="text" placeholder="기준값 · 분 (예: 480 = 8시간)"
              />
              <button class="btn ghost" :class="{ danger: confirmingId === r.id }" :disabled="ruleBusy === r.id" @click="reject(r.id)">{{ confirmingId === r.id ? '한 번 더 누르면 거부' : '거부' }}</button>
              <button class="btn primary" :disabled="(r.conflicts || []).some((c) => !c.covers_all)"
                      @click="approve(r.id, fillValue || undefined, !!(r.conflicts || []).length)">
                {{ (r.conflicts || []).length ? '기존 규칙 대체' : '승인하기' }}
              </button>
            </div>
          </article>
        </section>

        <section class="card">
          <div class="card-head">
            <h2>적용 중인 규칙</h2>
            <span class="count">{{ activeRules.length }}건</span>
          </div>
          <p v-if="!activeRules.length" class="empty">아직 승인된 규칙이 없습니다.</p>
          <article v-for="r in activeRules" :key="r.id" class="pending-item" :class="{ off: !r.enabled }">
            <div class="pending-top">
              <span class="tag tag-normal">#{{ r.id }}</span>
              <p class="pending-sentence">"{{ r.sentence }}"</p>
              <span v-if="r.approved_by" class="muted">
                {{ r.approved_by }} 승인 · {{ stampOf(r.approved_at) }}
              </span>
              <span v-if="r.superseded_by && !r.enabled" class="tag tag-muted">
                #{{ r.superseded_by }}로 대체됨 · {{ r.superseded_who }} · {{ stampOf(r.superseded_at) }}
              </span>
              <span v-if="r.replaced && r.replaced.length" class="muted">#{{ r.replaced.join(', #') }} 대체</span>
            </div>
            <dl class="mini">
              <div><dt>조건</dt><dd>{{ condText(r.rule) }}</dd></div>
              <div><dt>동작</dt><dd>{{ actText(r.rule) }}</dd></div>
              <div><dt>적용 대상</dt><dd>{{ scopeText(r.rule) }}</dd></div>
              <div v-if="overrideText(r.rule)"><dt>세대별 예외</dt><dd>{{ overrideText(r.rule) }}</dd></div>
            </dl>
            <div class="pending-act">
              <button class="btn ghost" :disabled="ruleBusy === r.id" @click="toggleRule(r.id)">{{ r.enabled ? '일시중지' : '재개' }}</button>
              <button class="btn danger" :class="{ ghost: confirmingId !== r.id }" :disabled="ruleBusy === r.id" @click="reject(r.id)">{{ confirmingId === r.id ? '한 번 더 누르면 삭제' : '삭제' }}</button>
            </div>
          </article>
        </section>
      </main>

      <!-- ────────── 세대 관리 ────────── -->
      <main v-else-if="activeView === 'homes'" class="content">
        <div class="homes-layout">
          <section class="card">
            <div class="card-head">
              <div>
                <h2>세대 목록</h2>
                <p class="hint">장치 라벨(home=)에서 자동으로 발견합니다.</p>
              </div>
              <span class="count">{{ homeList.length }}세대</span>
            </div>
            <p v-if="!homeList.length" class="empty">발견된 세대가 없습니다.</p>
            <button
              v-for="x in homeList" :key="x.home" type="button"
              class="home-item" :class="{ on: selectedHome && selectedHome.home === x.home }"
              @click="selectedHomeId = x.home"
            >
              <span class="home-no">{{ x.home }}호</span>
              <span v-if="x.care" class="tag" :class="'tag-' + SEV[x.care.severity]?.cls">
                {{ SEV[x.care.severity]?.ko }}
              </span>
              <span v-else class="tag tag-home">판정 대상 아님</span>
              <span class="home-sub">장치 {{ x.devices.length }} · 규칙 {{ (x.care?.rules || []).length }}</span>
            </button>
          </section>

          <section v-if="selectedHome" class="card">
            <div class="card-head">
              <div class="home-head">
                <h2>{{ selectedHome.home }}호</h2>
                <span v-if="selectedHome.care" class="tag" :class="'tag-' + SEV[selectedHome.care.severity]?.cls">
                  {{ SEV[selectedHome.care.severity]?.ko }}
                </span>
              </div>
              <button class="btn ghost" @click="editHomeThreshold(selectedHome.home)">이 세대 기준 바꾸기</button>
            </div>

            <p class="sec-title">현재 상태</p>
            <HomeBasis v-if="selectedHome.care" :h="selectedHome.care" />
            <p v-else class="muted home-note">
              움직임 센서가 없어 돌봄 판정 대상이 아닙니다. 등록된 장치는 아래에서 확인할 수 있습니다.
            </p>

            <template v-if="selectedHome.care">
              <p class="sec-title">타임라인</p>
              <HomeTimeline :home="selectedHome.home" :judged-at="selectedHome.care.judged_at" />
            </template>

            <p class="sec-title">적용 중인 규칙</p>
            <p v-if="!rulesOfHome(selectedHome).length" class="muted home-note">이 세대에 걸린 규칙이 없습니다.</p>
            <ul v-else class="home-rules">
              <li v-for="r in rulesOfHome(selectedHome)" :key="r.id">
                <span class="tag tag-normal">#{{ r.id }}</span>
                <div>
                  <p class="hr-sentence">"{{ r.sentence }}"</p>
                  <p class="muted">
                    {{ r.rule ? condText(r.rule) : '' }}
                    <span v-if="r.override != null" class="flag ovr-flag">이 세대 예외 {{ fmtMinutes(r.override) }}</span>
                  </p>
                </div>
              </li>
            </ul>

            <p class="sec-title">연결된 장치 ({{ selectedHome.devices.length }})</p>
            <ul class="devlist">
              <li v-for="d in selectedHome.devices" :key="d.path">
                <div class="devrow">
                  <span class="tag" :class="d.meta.kind === 'actuator' ? 'tag-watch' : 'tag-normal'">
                    {{ d.meta.kind === 'sensor' ? '센서' : d.meta.kind === 'event' ? '이벤트' : '액추에이터' }}
                  </span>
                  <span class="mono devname">{{ d.path.split('/').pop() }}</span>
                  <span class="muted">{{ typeKo(d.meta.type) }}</span>
                </div>
                <div class="lbls mono"><span v-for="l in d.labels" :key="l">{{ l }}</span></div>
              </li>
            </ul>

            <p class="sec-title">알림 이력 (최근 {{ alertsOfHome(selectedHome.home).length }}건)</p>
            <p v-if="!alertsOfHome(selectedHome.home).length" class="muted home-note">기록된 알림이 없습니다.</p>
            <ul v-else class="alerts">
              <AlertItem v-for="a in alertsOfHome(selectedHome.home)" :key="a.id" :a="a"
                         :show-home="false" @changed="onAlertChanged" />
            </ul>
          </section>
        </div>
      </main>

      <!-- ────────── 알림 이력 ────────── -->
      <main v-else-if="activeView === 'alerts'" class="content">
        <section class="card">
          <div class="card-head">
            <div>
              <h2>알림 이력</h2>
              <p class="hint">
                위험도가 바뀐 순간만 기록합니다. 이상 알림은 복지사가 대응해야 끝나고, 누가·언제·무엇을 했는지 남습니다.
              </p>
            </div>
            <span class="count">{{ alerts.length }}건</span>
          </div>
          <div class="tabs">
            <button class="tab" :class="{ on: alertFilter === 'todo', urgent: alertFilter === 'todo' }"
                    @click="alertFilter = 'todo'">
              미완료 ({{ todoAlerts.length }}<template v-if="openAlerts.length"> · 미확인 {{ openAlerts.length }}</template>)
            </button>
            <button class="tab" :class="{ on: alertFilter === 'all' }" @click="alertFilter = 'all'">
              전체 ({{ alerts.length }})
            </button>
          </div>
          <p v-if="!shownAlerts.length" class="empty">
            {{ alertFilter === 'todo' ? '조치할 알림이 없습니다.' : '아직 기록된 알림이 없습니다.' }}
          </p>
          <ul v-else class="alerts big">
            <AlertItem v-for="a in shownAlerts" :key="a.id" :a="a" @changed="onAlertChanged" />
          </ul>
        </section>
      </main>

      <!-- ────────── 기기 관리 ────────── -->
      <main v-else-if="activeView === 'devices'" class="content">
        <section class="card">
          <div class="card-head">
            <div>
              <h2>연결된 장치 (oneM2M 리소스 트리)</h2>
              <p class="hint">
                장치 목록은 코드에 없습니다. 표준 규격대로 라벨을 붙여 꽂으면 여기에 나타납니다.
              </p>
            </div>
            <span class="count">{{ devices.length }}개</span>
          </div>
          <p v-if="!devices.length" class="empty">등록된 장치가 없습니다.</p>
          <ul v-else class="devlist">
            <li v-for="d in devices" :key="d.path">
              <div class="devrow">
                <span class="tag" :class="d.meta.kind === 'actuator' ? 'tag-watch' : 'tag-normal'">
                  {{ d.meta.kind === 'sensor' ? '센서' : d.meta.kind === 'event' ? '이벤트' : '액추에이터' }}
                </span>
                <span class="mono devname">{{ d.path.split('/').pop() }}</span>
                <span class="muted">{{ typeKo(d.meta.type) }}</span>
                <span v-if="d.meta.home" class="tag tag-home">{{ d.meta.home }}호</span>
              </div>
              <div class="lbls mono">
                <span v-for="l in d.labels" :key="l">{{ l }}</span>
              </div>
            </li>
          </ul>
        </section>
      </main>

      <footer class="foot">
        온살핌 · 모두가 안심하는, 따뜻한 일상 &nbsp;|&nbsp; 팀 병아리 · 세종대학교
      </footer>
    </div>

    <!-- 새 알림 팝업 — 화면이 바뀌어도 떠 있어야 해서 최상위에 둔다 -->
    <AlertToasts :alerts="alerts" :sound="soundOn" @open-home="openHome"
                 @open-alerts="activeView = 'alerts'; alertFilter = 'todo'" @changed="onAlertChanged" />
  </div>
</template>

<style scoped>
.app { display: flex; min-height: 100vh; }

/* ───── 사이드바 ───── */
.sidebar {
  width: 232px; flex: 0 0 232px; background: var(--surface);
  border-right: 1px solid var(--border); display: flex; flex-direction: column;
  padding: 1.25rem 0.85rem; position: sticky; top: 0; height: 100vh;
}
.brand { display: flex; gap: 0.7rem; align-items: center; padding: 0 0.45rem 1.25rem; color: inherit; text-decoration: none; cursor: pointer; }
.brand:hover .brand-name { color: var(--brand-dim); }
.brand-mark {
  width: 40px; height: 40px; border-radius: 11px; display: grid; place-items: center;
  background: var(--brand-soft); color: var(--brand); flex: 0 0 40px;
}
.brand-mark svg { width: 23px; height: 23px; }
.brand-name { font-weight: 700; font-size: 1.05rem; letter-spacing: -0.01em; }
.brand-sub { font-size: 0.68rem; color: var(--muted); }

.nav { display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 0.6rem; width: 100%;
  padding: 0.62rem 0.7rem; border: 0; background: none; border-radius: var(--radius-sm);
  font-size: 0.875rem; color: var(--text-2); cursor: pointer; text-align: left;
}
.nav-item:hover:not(.disabled) { background: var(--surface-2); color: var(--text); }
.nav-item.active { background: var(--brand-soft); color: var(--brand-dim); font-weight: 600; }
.nav-item.disabled { opacity: 0.45; cursor: default; }
.nav-dot { flex: 0 0 7px; width: 7px; height: 7px; border-radius: 3px; background: currentColor; opacity: 0.55; }
.nav-item.active .nav-dot { opacity: 1; }
.nav-badge {
  margin-left: auto; background: var(--urgent); color: #fff; font-size: 0.68rem;
  font-weight: 700; padding: 0.05rem 0.42rem; border-radius: 999px;
}
.nav-soon { margin-left: auto; font-size: 0.65rem; color: var(--muted); }

.side-foot {
  margin-top: auto; padding: 0.9rem; background: var(--surface-2);
  border-radius: var(--radius-sm); font-size: 0.72rem; color: var(--muted); line-height: 1.65;
}
.side-foot strong { color: var(--brand); }

/* ───── 상단 ───── */
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.topbar {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem 1.5rem;
  padding: 1.15rem 1.75rem 0.9rem; background: var(--surface);
  border-bottom: 1px solid var(--border); flex-wrap: wrap;
}
.topbar h1 { font-size: 1.32rem; font-weight: 700; letter-spacing: -0.015em; white-space: nowrap; }
.topbar-sub { font-size: 0.8rem; color: var(--muted); white-space: nowrap; }
.topbar-right { display: flex; align-items: center; gap: 0.9rem; flex: 1 1 320px; justify-content: flex-end; min-width: 0; }
.search { position: relative; flex: 1 1 160px; min-width: 0; max-width: 260px; }
.search input {
  width: 100%; padding: 0.5rem 0.75rem 0.5rem 2rem; font-size: 0.82rem;
  border: 1px solid var(--border-strong); border-radius: 999px;
  background: var(--surface-2); color: var(--text); font-family: inherit;
}
.search input:focus { outline: 2px solid var(--brand-soft); border-color: var(--brand); }
.search-icon { position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%); color: var(--muted); }
.chip { font-size: 0.72rem; font-weight: 600; padding: 0.28rem 0.62rem; border-radius: 999px; white-space: nowrap; }
.chip-on { background: var(--normal-soft); color: var(--normal); }
.chip-off { background: var(--urgent-soft); color: var(--urgent); }
.who { display: flex; align-items: center; gap: 0.55rem; }
.avatar {
  width: 34px; height: 34px; border-radius: 50%; background: var(--brand-soft);
  color: var(--brand-dim); display: grid; place-items: center; font-weight: 700; font-size: 0.82rem;
}
.who-name { font-size: 0.82rem; font-weight: 600; white-space: nowrap; }
.who-org { font-size: 0.68rem; color: var(--muted); white-space: nowrap; }

.stamp { padding: 0.7rem 1.75rem 0; font-size: 0.75rem; color: var(--muted); }
.banner {
  margin: 0.7rem 1.75rem 0; padding: 0.6rem 0.9rem; border-radius: var(--radius-sm); font-size: 0.82rem;
}
.banner.err { background: var(--urgent-soft); color: var(--urgent); }
.banner.warn { background: var(--watch-soft); color: var(--watch); }
.banner code { background: rgba(0, 0, 0, 0.05); padding: 0.05rem 0.3rem; border-radius: 4px; }

/* ───── 레이아웃 ───── */
.content { padding: 1.1rem 1.75rem 1.5rem; display: flex; flex-direction: column; gap: 1.1rem; }
.cols { display: grid; grid-template-columns: minmax(0, 1.85fr) minmax(0, 1fr); gap: 1.1rem; align-items: start; }
@media (max-width: 1180px) { .cols { grid-template-columns: 1fr; } }

.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 1.1rem 1.25rem; box-shadow: var(--shadow);
}
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: 0.9rem; }
.card h2 { font-size: 0.99rem; font-weight: 700; }
.hint { font-size: 0.76rem; color: var(--muted); margin-top: 0.15rem; }
.count { font-size: 0.75rem; color: var(--muted); background: var(--surface-2); padding: 0.15rem 0.5rem; border-radius: 6px; white-space: nowrap; }
.sec-title { font-size: 0.8rem; font-weight: 700; margin-bottom: 0.55rem; display: flex; align-items: center; gap: 0.4rem; }
.sec-title.ok { color: var(--normal); }
.tick { background: var(--normal-soft); border-radius: 50%; width: 18px; height: 18px; display: grid; place-items: center; font-size: 0.7rem; }
.ai-badge { margin-left: auto; font-size: 0.66rem; color: var(--brand); background: var(--brand-soft); padding: 0.1rem 0.45rem; border-radius: 999px; }
.empty { padding: 1.6rem 0; text-align: center; color: var(--muted); font-size: 0.83rem; }

/* ───── KPI ───── */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
@media (max-width: 1000px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
.kpi {
  display: flex; gap: 0.85rem; align-items: center; padding: 1rem 1.1rem;
  border-radius: var(--radius); border: 1px solid var(--border); box-shadow: var(--shadow-sm);
}
.kpi-ico { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; font-size: 1.25rem; background: #fff; }
.kpi-label { font-size: 0.76rem; color: var(--text-2); }
.kpi-value { font-size: 1.6rem; font-weight: 700; line-height: 1.25; letter-spacing: -0.02em; }
.kpi-value span { font-size: 0.82rem; font-weight: 600; color: var(--muted); }
.kpi-foot { font-size: 0.68rem; color: var(--muted); }
.kpi-blue { background: #eff5ff; }
.kpi-red { background: var(--urgent-soft); }
.kpi-orange { background: var(--device-soft); }
.kpi-green { background: var(--normal-soft); }

/* ───── 탭 ───── */
.tabs { display: flex; gap: 0.45rem; flex-wrap: wrap; margin-bottom: 0.8rem; }
.tab {
  padding: 0.4rem 0.8rem; border-radius: 999px; border: 1px solid var(--border-strong);
  background: var(--surface); font-size: 0.78rem; color: var(--text-2); cursor: pointer;
}
.tab:hover { background: var(--surface-2); }
.tab.on { background: var(--brand); border-color: var(--brand); color: #fff; font-weight: 600; }
.tab.on.urgent { background: var(--urgent); border-color: var(--urgent); }
.tab.on.device { background: var(--device); border-color: var(--device); }
.tab.on.battery { background: var(--watch); border-color: var(--watch); }

/* ───── 표 ───── */
.grid { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.grid th {
  text-align: left; font-weight: 600; font-size: 0.74rem; color: var(--muted);
  padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); background: var(--surface-2);
}
.grid th:first-child { border-radius: 8px 0 0 0; }
.grid th:last-child { border-radius: 0 8px 0 0; }
.grid td { padding: 0.72rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: top; }
.grid tbody tr:hover { background: var(--surface-2); }
.home-cell { font-weight: 700; white-space: nowrap; }
.crow { cursor: pointer; }
.crow.open { background: var(--surface-2); }
.caret { color: var(--muted); font-size: 0.7rem; margin-right: 0.3rem; }

/* 판단 근거 — 결과만 보고도 판단 과정을 따라갈 수 있게 */
.detail > td { background: var(--surface-2); padding: 0.9rem 1.1rem; }
/* 규칙 문장이 길어서 그대로 두면 행 높이가 들쭉날쭉해진다. 두 줄까지만 보이고 나머지는 말줄임. */
.rule-cell { color: var(--text-2); max-width: 260px; }
.rule-cell .sent {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; line-height: 1.45;
}
.more { color: var(--muted); margin-left: 0.25rem; }
.ovr { display: block; margin-top: 0.2rem; font-size: 0.72rem; color: var(--brand); font-weight: 600; }
/* 예외가 실제로 판정을 갈랐을 때만 눈에 띄게 — 검토의견 02의 증거가 되는 줄 */
.ovr.decisive {
  background: var(--brand-soft); color: var(--brand-dim);
  padding: 0.12rem 0.4rem; border-radius: 5px; display: inline-block;
}
.dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 0.38rem; vertical-align: 1px; }
.dot.normal { background: var(--normal); }
.dot.watch { background: var(--watch); }
.dot.urgent { background: var(--urgent); }
.dot.device { background: var(--device); }
.dot.unknown { background: var(--muted); }


/* ───── 규칙 만들기 ───── */
.seg { display: flex; gap: 0.3rem; background: var(--surface-2); padding: 0.25rem; border-radius: var(--radius-sm); margin-bottom: 0.8rem; }
.seg-btn { flex: 1; padding: 0.42rem; border: 0; background: none; border-radius: 7px; font-size: 0.78rem; color: var(--text-2); cursor: pointer; }
.seg-btn.on { background: var(--surface); color: var(--brand-dim); font-weight: 600; box-shadow: var(--shadow-sm); }

.ta-wrap { border: 1px solid var(--border-strong); border-radius: var(--radius-sm); background: var(--surface-2); padding: 0.6rem 0.7rem; }
.ta-wrap.listening { border-color: var(--urgent); box-shadow: 0 0 0 3px var(--urgent-soft); }
.ta-wrap textarea { width: 100%; border: 0; background: none; resize: vertical; font-family: inherit; font-size: 0.86rem; color: var(--text); line-height: 1.6; }
.ta-wrap textarea:focus { outline: none; }
.ta-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 0.3rem; }
.count { font-size: 0.7rem; }
.mic { width: 30px; height: 30px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--surface); cursor: pointer; font-size: 0.85rem; }
.mic.active { background: var(--urgent-soft); border-color: var(--urgent); }
.mic.busy { opacity: 0.6; }


.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.75rem; }
.ex { font-size: 0.72rem; padding: 0.3rem 0.6rem; border-radius: 999px; border: 1px dashed var(--border-strong); background: none; color: var(--text-2); cursor: pointer; text-align: left; }
.ex:hover { border-style: solid; background: var(--brand-soft); color: var(--brand-dim); }

.json, .plan {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 0.75rem 0.85rem; font-size: 0.73rem; line-height: 1.7; white-space: pre-wrap;
  color: var(--text-2); max-height: 320px; overflow: auto;
}
.plan { margin-top: 0.6rem; }

.msg { margin-top: 0.6rem; padding: 0.55rem 0.8rem; border-radius: var(--radius-sm); font-size: 0.79rem; }
.msg.err { background: var(--urgent-soft); color: var(--urgent); }
.msg.warn { background: var(--watch-soft); color: var(--watch); }
.msg.info { background: var(--brand-soft); color: var(--brand-dim); }
.msg.clarify { background: var(--brand-soft); color: var(--brand-dim); font-weight: 500; }

/* ───── 파이프라인 ───── */
.pipe { margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid var(--border); }
.pstep { display: grid; grid-template-columns: 20px 16px auto 1fr; gap: 0.45rem; align-items: baseline; padding: 0.28rem 0; font-size: 0.76rem; }
.pico { font-weight: 700; }
.pstep.ok .pico { color: var(--normal); }
.pstep.fail .pico { color: var(--urgent); }
.pstep.warn .pico { color: var(--watch); }
.msg.warn { background: var(--watch-soft); color: var(--text); }
.pstep.skip { opacity: 0.5; }
.pnum { color: var(--muted); font-size: 0.68rem; }
.plabel { font-weight: 600; white-space: nowrap; }
.pdetail { color: var(--muted); }

/* ───── 요약 / 승인 ───── */
.summary { margin-top: 0.9rem; padding: 0.9rem; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); }
.mini { display: flex; flex-direction: column; gap: 0.35rem; }
.mini > div { display: grid; grid-template-columns: 74px 1fr; gap: 0.5rem; font-size: 0.78rem; }
.mini dt { color: var(--muted); }
.mini dd { color: var(--text); }
.summary-act, .pending-act { display: flex; gap: 0.4rem; justify-content: flex-end; margin-top: 0.8rem; flex-wrap: wrap; }
.fill { flex: 1; min-width: 110px; padding: 0.45rem 0.6rem; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); font-size: 0.8rem; font-family: inherit; }

.pending-list { display: flex; flex-direction: column; gap: 0.7rem; }
.pending-item { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.85rem 0.95rem; margin-bottom: 0.7rem; }
.pending-item.off { opacity: 0.55; }
.pending-top { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.55rem; flex-wrap: wrap; }
.pending-sentence { font-weight: 600; font-size: 0.86rem; }
.pending-top .muted { font-size: 0.7rem; margin-left: auto; }

/* ───── 도넛 ───── */
.donut-row { display: flex; gap: 1.5rem; align-items: center; }
.donut { width: 150px; height: 150px; flex: 0 0 150px; }
.donut .track { fill: none; stroke: var(--surface-2); stroke-width: 18; }
.donut .seg { fill: none; stroke-width: 18; transform: rotate(-90deg); transform-origin: 70px 70px; }
.donut .seg.normal { stroke: var(--normal); }
.donut .seg.watch { stroke: var(--watch); }
.donut .seg.urgent { stroke: var(--urgent); }
.donut .seg.device { stroke: var(--device); }
.donut .dn { text-anchor: middle; font-size: 1.5rem; font-weight: 700; fill: var(--text); }
.donut .dl { text-anchor: middle; font-size: 0.7rem; fill: var(--muted); }
.legend { list-style: none; display: flex; flex-direction: column; gap: 0.45rem; font-size: 0.8rem; }
.legend strong { margin-left: 0.2rem; }

/* ───── 알림 ───── */
.alerts { list-style: none; display: flex; flex-direction: column; }
.alerts li { display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 0; border-bottom: 1px solid var(--border); font-size: 0.8rem; }
.alerts li:last-child { border-bottom: 0; }
.atext { flex: 1; color: var(--text-2); min-width: 0; }
.atime { color: var(--muted); font-size: 0.72rem; white-space: nowrap; }
.alerts.big li { padding: 0.7rem 0; }

/* ───── 기기 목록 ───── */
/* ───── 세대 관리 ───── */
.homes-layout { display: grid; grid-template-columns: minmax(220px, 300px) minmax(0, 1fr); gap: 1.1rem; align-items: start; }
@media (max-width: 860px) { .homes-layout { grid-template-columns: 1fr; } }
.home-item {
  display: grid; grid-template-columns: auto 1fr; grid-template-rows: auto auto; gap: 0.15rem 0.5rem;
  align-items: center; width: 100%; text-align: left; padding: 0.6rem 0.7rem; margin-bottom: 0.4rem;
  border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); cursor: pointer;
}
.home-item:hover { background: var(--surface-2); }
.home-item.on { border-color: var(--brand); background: var(--brand-soft); }
.home-item .tag { justify-self: end; }
.home-no { font-weight: 700; font-size: 0.9rem; }
.home-sub { grid-column: 1 / -1; font-size: 0.72rem; color: var(--muted); }
.home-head { display: flex; align-items: center; gap: 0.6rem; }
.home-head h2 { font-size: 1.15rem; }
.homes-layout .sec-title { margin-top: 1.1rem; }
.home-note { font-size: 0.8rem; }
.home-rules { list-style: none; display: flex; flex-direction: column; gap: 0.5rem; }
.home-rules li { display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.8rem; }
.hr-sentence { font-weight: 600; margin-bottom: 0.1rem; }
.devlist { list-style: none; display: flex; flex-direction: column; gap: 0.5rem; }
.devlist li { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.65rem 0.8rem; }
.devrow { display: flex; align-items: center; gap: 0.55rem; font-size: 0.82rem; }
.devname { font-weight: 600; }
.lbls { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.4rem; }
.lbls span { font-size: 0.68rem; background: var(--surface-2); color: var(--muted); padding: 0.1rem 0.4rem; border-radius: 4px; }

.foot { margin-top: auto; padding: 1rem 1.75rem; font-size: 0.72rem; color: var(--muted); text-align: right; }

/* ───── 좁은 화면 대응 ─────
   전시는 넓은 모니터지만, 노트북 한 대로 시연하는 경우도 있어 무너지지 않게 한다. */
@media (max-width: 1000px) {
  .content, .topbar, .stamp, .banner, .foot { padding-left: 1rem; padding-right: 1rem; }
  .banner, .stamp { margin-left: 1rem; margin-right: 1rem; }
}
@media (max-width: 860px) {
  .sidebar { width: 62px; flex: 0 0 62px; padding: 1rem 0.5rem; align-items: center; }
  .brand { padding: 0 0 1rem; }
  .brand > div, .side-foot, .nav-soon { display: none; }
  .nav-item { justify-content: center; padding: 0.6rem 0; font-size: 0; gap: 0; }
  .nav-dot { width: 9px; height: 9px; }
  .nav-badge { position: absolute; margin: 0; transform: translate(14px, -10px); font-size: 0.6rem; }
  .nav-item { position: relative; }
  .topbar { padding-top: 0.9rem; }
  .kpis { grid-template-columns: repeat(2, 1fr); gap: 0.7rem; }
  .kpi { padding: 0.8rem; }
  .kpi-value { font-size: 1.3rem; }
  .donut-row { flex-direction: column; align-items: flex-start; gap: 0.9rem; }
  .grid { font-size: 0.76rem; }
  .grid td, .grid th { padding: 0.5rem 0.4rem; }
}
@media (max-width: 620px) {
  .kpis { grid-template-columns: 1fr; }
  .topbar-right { flex: 1 1 100%; }
  .who { display: none; }
}
</style>

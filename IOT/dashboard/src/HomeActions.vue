<script setup>
// 세대 한 곳에 거는 예외 두 가지.
//   영구 예외 — "102호만 무활동 기준을 6시간으로": 말로 입력, 규칙 생성과 같은 검증을 거친다
//   임시 예외 — 부재 등록: 입원·외출 기간엔 무활동을 판정하지 않는다(기기는 계속 본다). 기간이 끝나면 저절로 풀린다
import { ref, computed, watch, onMounted } from 'vue'
import { api } from './api.js'
import { fmtMinutes, stampOf } from './format.js'

const props = defineProps({
  home: { type: String, required: true },
  care: { type: Object, default: null },
})
const emit = defineEmits(['changed'])

const open = ref('')               // '' | 'threshold' | 'absence'
const busy = ref(false)
const error = ref('')
const notice = ref('')

function toggle(which) {
  open.value = open.value === which ? '' : which
  error.value = ''
  notice.value = ''
}

/* ── 영구 예외: 무활동 기준 ── */
const valueText = ref('')
const choice = ref(null)           // 예외를 붙일 규칙이 여럿일 때 서버가 준 후보
const applied = computed(() => props.care?.applied || {})

async function submitThreshold() {
  if (busy.value || !valueText.value.trim()) return
  busy.value = true; error.value = ''; notice.value = ''; choice.value = null
  try {
    const r = await api.addRule(`${props.home}호만 무활동 기준을 ${valueText.value.trim()}으로 바꿔줘`)
    if (r.status === 'needs_choice') { choice.value = r; return }
    if (!r.ok) { error.value = (r.errors || r.questions || []).join(' ') || '적용하지 못했습니다.'; return }
    notice.value = `${props.home}호 예외 기준을 적용했습니다. 다음 판정(몇 초 안)부터 반영됩니다.`
    valueText.value = ''
    emit('changed')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function pick(c) {
  if (busy.value) return
  busy.value = true
  const r = await api.overrideRule(c.id, choice.value.choice.home, choice.value.choice.value)
  busy.value = false
  if (!r.ok) { error.value = (r.errors || []).join(' '); return }
  notice.value = `규칙 #${c.id}에 ${props.home}호 예외 ${fmtMinutes(choice.value.choice.value)}을(를) 적용했습니다.`
  choice.value = null
  valueText.value = ''
  emit('changed')
}

/* ── 임시 예외: 부재 등록 ── */
const REASONS = ['입원', '가족 방문', '외출·여행']
const reason = ref('')
const start = ref('')
const end = ref('')
const absences = ref([])

function toLocal(d) {             // <input type="datetime-local"> 형식 (브라우저 시간대)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}
function setDays(n) {
  const s = start.value ? new Date(start.value) : new Date()
  end.value = toLocal(new Date(s.getTime() + n * 86400e3))
}
function resetAbsenceForm() {
  reason.value = ''
  start.value = toLocal(new Date())
  end.value = ''
}

async function loadAbsences() {
  try { absences.value = await api.getAbsences(props.home) } catch { absences.value = [] }
}
onMounted(() => { loadAbsences(); resetAbsenceForm() })
watch(() => props.home, () => { open.value = ''; choice.value = null; valueText.value = ''; loadAbsences(); resetAbsenceForm() })

function absenceState(a) {
  if (a.ended_at) return { ko: `일찍 해제 (${stampOf(a.ended_at)} · ${a.ended_by})`, cls: 'muted', live: false }
  const t = Date.now()
  if (Date.parse(a.end) <= t) return { ko: '끝남', cls: 'muted', live: false }
  if (Date.parse(a.start) > t) return { ko: '예정', cls: 'watch', live: true }
  return { ko: '부재 중', cls: 'home', live: true }   // 보라(기기 이상)와 섞이지 않게 중립 색
}

async function submitAbsence() {
  if (busy.value) return
  busy.value = true; error.value = ''; notice.value = ''
  const r = await api.addAbsence({ home: props.home, start: start.value, end: end.value, reason: reason.value })
  busy.value = false
  if (!r.ok) { error.value = (r.errors || []).join(' '); return }
  notice.value = `${props.home}호 부재를 등록했습니다 (${stampOf(r.absence.end)}까지). 그동안 무활동 알림은 울리지 않고, 기기 점검은 계속합니다.`
  resetAbsenceForm()
  await loadAbsences()
  emit('changed')
}

async function endAbsence(a) {
  if (busy.value) return
  busy.value = true; error.value = ''
  const r = await api.endAbsence(a.id)
  busy.value = false
  if (!r.ok) { error.value = (r.errors || []).join(' '); return }
  notice.value = `${props.home}호 부재를 해제했습니다. 지금부터 무활동을 다시 판정합니다.`
  await loadAbsences()
  emit('changed')
}
</script>

<template>
  <div class="ha">
    <div class="ha-btns">
      <button class="btn ghost" :class="{ on: open === 'threshold' }" @click="toggle('threshold')">
        이 세대만 무활동 기준 다르게
      </button>
      <button class="btn ghost" :class="{ on: open === 'absence' }" @click="toggle('absence')">
        {{ care?.away ? '부재 관리' : '부재 등록' }}
      </button>
    </div>

    <!-- 영구 예외 -->
    <div v-if="open === 'threshold'" class="panel">
      <p class="now muted">
        <template v-if="applied.minutes">
          지금 {{ home }}호 기준: <strong>{{ fmtMinutes(applied.minutes) }}</strong>
          <template v-if="applied.source === 'override'"> (예외 · 공통 {{ fmtMinutes(applied.common) }})</template>
          <template v-else> (공통 기준)</template>
        </template>
        <template v-else>이 세대에 걸린 무활동 규칙이 없습니다. 먼저 전체 세대 규칙을 만들어 주세요.</template>
      </p>
      <div class="sentence">
        <span>{{ home }}호만 무활동 기준을</span>
        <input v-model="valueText" placeholder="예: 6시간" maxlength="20" @keyup.enter="submitThreshold" />
        <span>으로 바꿔줘</span>
        <button class="btn primary sm" :disabled="busy || !valueText.trim()" @click="submitThreshold">
          {{ busy ? '적용 중…' : '적용' }}
        </button>
      </div>
      <p class="muted small">말로 만든 규칙과 똑같이 AI 번역 → 검증 → 대상 규칙 찾기를 거쳐 적용됩니다.</p>
      <div v-if="choice" class="picks">
        <p class="msg clarify">{{ choice.questions?.join(' ') }}</p>
        <button v-for="c in choice.candidates" :key="c.id" class="pick" :disabled="busy" @click="pick(c)">
          <strong>#{{ c.id }}에 적용</strong> <span class="muted">{{ c.summary }}</span>
        </button>
      </div>
    </div>

    <!-- 임시 예외 -->
    <div v-if="open === 'absence'" class="panel">
      <p class="muted small">
        등록한 기간에는 <strong>무활동 알림을 울리지 않습니다.</strong> 통신 두절·배터리 같은 기기 점검은 계속합니다.
        기간이 끝나면 저절로 풀립니다.
      </p>
      <div class="row">
        <span class="lbl">사유</span>
        <button v-for="r in REASONS" :key="r" class="chip-btn" :class="{ on: reason === r }" @click="reason = r">{{ r }}</button>
        <input v-model="reason" class="grow" maxlength="50" placeholder="직접 입력" />
      </div>
      <div class="row">
        <span class="lbl">기간</span>
        <input v-model="start" type="datetime-local" />
        <span>~</span>
        <input v-model="end" type="datetime-local" />
        <button v-for="n in [1, 3, 7]" :key="n" class="chip-btn" @click="setDays(n)">{{ n }}일</button>
      </div>
      <div class="row">
        <button class="btn primary sm" :disabled="busy || !reason.trim() || !end" @click="submitAbsence">부재 등록</button>
      </div>

      <ul v-if="absences.length" class="alist">
        <li v-for="a in absences.slice(0, 5)" :key="a.id">
          <span class="tag" :class="'tag-' + absenceState(a).cls">{{ absenceState(a).ko }}</span>
          <span>{{ stampOf(a.start) }} ~ {{ stampOf(a.end) }} · {{ a.reason }}</span>
          <span class="muted">{{ a.by }} 등록</span>
          <button v-if="absenceState(a).live" class="btn sm ghost" :disabled="busy" @click="endAbsence(a)">부재 해제</button>
        </li>
      </ul>
    </div>

    <p v-if="error" class="msg err">{{ error }}</p>
    <p v-if="notice" class="msg info">{{ notice }}</p>
  </div>
</template>

<style scoped>
.ha { display: grid; gap: 0.5rem; }
.ha-btns { display: flex; gap: 0.4rem; flex-wrap: wrap; justify-content: flex-end; }
.btn.on { border-color: var(--brand); color: var(--brand-dim); background: var(--brand-soft); }
.panel { display: grid; gap: 0.5rem; padding: 0.75rem 0.85rem; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); font-size: 0.8rem; }
.now { margin: 0; }
.small { font-size: 0.74rem; margin: 0; }
.sentence, .row { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.sentence input { width: 7rem; }
input { padding: 0.34rem 0.55rem; border: 1px solid var(--border-strong); border-radius: 6px; font-size: 0.78rem; background: var(--surface); color: var(--text); }
.grow { flex: 1 1 8rem; }
.lbl { color: var(--muted); width: 2.4rem; }
.chip-btn { padding: 0.24rem 0.6rem; border: 1px solid var(--border-strong); border-radius: 999px; background: var(--surface); font-size: 0.74rem; cursor: pointer; color: var(--text-2); white-space: nowrap; }
.chip-btn.on { border-color: var(--brand); background: var(--brand-soft); color: var(--brand-dim); font-weight: 600; }
.picks { display: grid; gap: 0.35rem; }
.pick { text-align: left; padding: 0.5rem 0.7rem; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); cursor: pointer; font-size: 0.78rem; }
.pick:hover:not(:disabled) { border-color: var(--brand); background: var(--brand-soft); }
.alist { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }
.alist li { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; font-size: 0.76rem; }
.msg { margin: 0; }
</style>

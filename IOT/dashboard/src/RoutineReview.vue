<script setup>
// 생활 일정(외출·수면) — 등록 → 승인 대기 → 안전성 검토 → 승인·거절. 승인한 일정만 판정에 들어간다.
// 일정 중에는 주의 단계 생활 알림만 보류하고(긴급은 그대로), 일정이 끝나고 30분 넘게 움직임이 없으면 추가 확인.
import { ref, watch } from 'vue'
import { api } from './api.js'

const props = defineProps({
  home: { type: String, required: true },
  worker: { type: String, default: '복지사' },
})

const DAYS = ['월', '화', '수', '목', '금', '토', '일']
const KIND = { outing: '외출', sleep: '수면' }
const data = ref(null)
const error = ref('')
const busy = ref(false)
const form = ref(blank())
const memo = ref('')

function blank() {
  return { label: '', kind: 'outing', from: '10:00', to: '13:00', days: [] }
}

watch(() => props.home, load, { immediate: true })

async function load() {
  error.value = ''
  try {
    data.value = await api.getRoutines(props.home)
  } catch (e) {
    error.value = e.message
  }
}

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
    await load()
    return true
  } catch (e) {
    error.value = e.message
    return false
  } finally {
    busy.value = false
  }
}

const daysText = (r) => (r.days ? r.days.map((d) => DAYS[d]).join('·') : '매일')
const when = (r) => `${daysText(r)} ${r.from}~${r.to}`

async function propose() {
  const r = { ...form.value, days: form.value.days.length ? [...form.value.days] : null }
  if (await run(() => api.proposeRoutine(props.home, r, props.worker))) form.value = blank()
}
const decide = (id, action) => run(() => api.decideRoutine(props.home, id, { action, by: props.worker, memo: memo.value }))
const remove = (i) => run(() => api.removeRoutine(props.home, i, props.worker, memo.value))

function toggleDay(d) {
  const ds = form.value.days
  form.value.days = ds.includes(d) ? ds.filter((x) => x !== d) : [...ds, d].sort()
}
</script>

<template>
  <section class="routines">
    <h3>생활 일정 — {{ home }}호</h3>
    <p class="hint">
      복지관·병원 외출, 수면처럼 정해진 일정 동안에는 주의 단계 생활 알림을 보류합니다 (긴급 확인은 보류하지 않음).
      일정이 끝나고 30분이 지나도 움직임이 없으면 '추가 확인'으로 알립니다. 하루 보류 시간은 12시간을 넘길 수 없습니다.
    </p>
    <p v-if="error" class="msg err">{{ error }}</p>

    <table v-if="data?.approved.length" class="grid">
      <thead><tr><th>적용 중인 일정</th><th>종류</th><th>요일·시간</th><th>시간</th><th></th></tr></thead>
      <tbody>
        <tr v-for="(r, i) in data.approved" :key="i">
          <td><b>{{ r.label }}</b></td><td>{{ KIND[r.kind] }}</td><td>{{ when(r) }}</td><td>{{ r.hours }}시간</td>
          <td><button class="btn ghost sm danger" type="button" :disabled="busy" @click="remove(i)">해제</button></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="hint">적용 중인 일정이 없습니다.</p>

    <div v-for="p in data?.pending || []" :key="p.id" class="pending">
      <div class="row">
        <span class="tag tag-wait">승인 대기</span>
        <b>{{ p.routine.label }}</b> · {{ KIND[p.routine.kind] }} · {{ when(p.routine) }} ({{ p.hours }}시간)
        <span class="muted">— {{ p.by }} 등록</span>
      </div>
      <p v-if="p.check.ok" class="ok">✓ 안전성 검토 통과 — 적용 중인 일정과 합쳐도 하루 12시간 이내</p>
      <ul v-else class="bad"><li v-for="b in p.check.blocks" :key="b">✗ {{ b }}</li></ul>
      <div class="row">
        <button class="btn ghost sm danger" type="button" :disabled="busy" @click="decide(p.id, 'reject')">거절</button>
        <button class="btn primary sm" type="button" :disabled="busy || !p.check.ok" @click="decide(p.id, 'approve')"
                :title="p.check.ok ? '' : '안전성 검토를 통과하지 못한 일정은 승인할 수 없습니다'">승인</button>
      </div>
    </div>

    <div class="form">
      <input v-model="form.label" maxlength="20" placeholder="일정 이름 (예: 복지관)" class="label" />
      <select v-model="form.kind"><option value="outing">외출</option><option value="sleep">수면</option></select>
      <input v-model="form.from" type="time" /> ~ <input v-model="form.to" type="time" />
      <span class="days">
        <button v-for="(d, i) in DAYS" :key="d" type="button" class="day" :class="{ on: form.days.includes(i) }"
                @click="toggleDay(i)">{{ d }}</button>
      </span>
      <span class="muted">{{ form.days.length ? '' : '(요일을 안 고르면 매일)' }}</span>
      <button class="btn ghost sm" type="button" :disabled="busy || !form.label.trim()" @click="propose">등록 (승인 대기로)</button>
    </div>
    <input v-model="memo" class="memo" maxlength="200" placeholder="승인·거절·해제 메모 (선택)" />

    <details v-if="data?.history.length" class="hist">
      <summary>일정 이력 {{ data.history.length }}건</summary>
      <ul>
        <li v-for="(h, i) in [...data.history].reverse()" :key="i">
          {{ h.at.replace('T', ' ').slice(0, 16) }} · {{ h.by }} ·
          {{ { routine_propose: '등록', routine_approve: '승인', routine_reject: '거절', routine_remove: '해제' }[h.action] }}
          — {{ h.routine.label }} ({{ when(h.routine) }})
          <span v-if="h.memo" class="muted">— {{ h.memo }}</span>
        </li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.routines { display: flex; flex-direction: column; gap: 0.6rem; border-top: 1px solid var(--border); padding-top: 0.9rem; }
.routines h3 { font-size: 0.9rem; font-weight: 700; }
.hint, .muted { color: var(--muted); font-size: 0.76rem; }
.grid { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.grid th { text-align: left; color: var(--muted); font-weight: 600; font-size: 0.72rem; padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border); }
.grid td { padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--border); }
.pending { border: 1px solid var(--border); border-radius: 10px; padding: 0.6rem 0.75rem; font-size: 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
.row, .form { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; font-size: 0.8rem; }
.ok { color: var(--ok, #1a7f37); font-size: 0.78rem; }
.bad { color: var(--danger, #c0392b); font-size: 0.78rem; list-style: none; padding: 0; }
.form input, .form select, .memo { padding: 0.3rem 0.45rem; border: 1px solid var(--border-strong); border-radius: 7px; font: inherit; font-size: 0.8rem; background: var(--surface); color: var(--text); }
.label { width: 11rem; }
.days { display: inline-flex; gap: 0.2rem; }
.day { border: 1px solid var(--border-strong); background: var(--surface); color: var(--text-2); border-radius: 6px; padding: 0.15rem 0.4rem; font-size: 0.74rem; cursor: pointer; }
.day.on { background: var(--primary, #2563eb); border-color: var(--primary, #2563eb); color: #fff; }
.hist { font-size: 0.76rem; }
.hist ul { margin-top: 0.4rem; padding-left: 1rem; display: flex; flex-direction: column; gap: 0.2rem; }
</style>

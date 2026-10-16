<script setup>
// 개인 기준(오전 활동 비율) — 연결된 14일 기록으로 추천 → 승인 전 안전성 검토 → 미리보기 → 승인·수정·거절.
// 계산·검사·저장은 모두 서버(baseline.py)가 한다. 화면은 보여 주고 결정만 보낸다.
import { ref, computed, watch } from 'vue'
import { api } from './api.js'
import RoutineReview from './RoutineReview.vue'

const props = defineProps({
  homes: { type: Array, default: () => [] },
  worker: { type: String, default: '복지사' },
})

const HOURS = ['8', '9', '10', '11']
const STATUS = { pending: '승인 대기', approved: '승인됨 · 판정에 적용 중', rejected: '거절' }

const home = ref('')
const data = ref(null)
const busy = ref(false)
const error = ref('')
const blocks = ref([])
const editing = ref(false)
const draft = ref({})
const memo = ref('')
const source = ref('')

watch(() => props.homes, (hs) => { if (!home.value && hs.length) home.value = hs[0] }, { immediate: true })
watch(home, load, { immediate: true })

async function load() {
  if (!home.value) return
  error.value = ''
  blocks.value = []
  editing.value = false
  try {
    data.value = await api.getBaseline(home.value)
    source.value = data.value.source || data.value.replays?.[0] || ''
  } catch (e) {
    error.value = e.message
  }
}

const pct = (v) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`)
const hourLabel = (h) => `${String(h).padStart(2, '0')}시`
const windowLabel = (h) => `${String(h - 1).padStart(2, '0')}:00~${String(h).padStart(2, '0')}:00`
const current = computed(() => data.value?.approved_theta)
const diff = computed(() => {
  const p = data.value?.preview
  return p ? p.personal.candidate_days - p.common.candidate_days : 0
})

async function run(fn) {
  busy.value = true
  error.value = ''
  blocks.value = []
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

const link = () => run(() => api.linkBaseline(home.value, source.value, props.worker))
const approve = () => run(() => api.decideBaseline(home.value, { action: 'approve', by: props.worker, memo: memo.value }))
const reject = () => run(() => api.decideBaseline(home.value, { action: 'reject', by: props.worker, memo: memo.value }))

function startEdit() {
  const base = current.value || data.value.recommended
  draft.value = Object.fromEntries(HOURS.map((h) => [h, base[h] === null ? '' : (base[h] * 100).toFixed(1)]))
  editing.value = true
}

async function saveEdit() {
  const theta = Object.fromEntries(HOURS.map((h) => [h, draft.value[h] === '' ? null : Number(draft.value[h]) / 100]))
  busy.value = true
  error.value = ''
  blocks.value = []
  try {
    await api.decideBaseline(home.value, { action: 'approve', theta, by: props.worker, memo: memo.value })
    await load()
  } catch (e) {
    blocks.value = e.message.split(', ')       // 안전성 검토에 막힌 이유 — 저장되지 않았다
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="review">
    <div class="pick">
      <label>세대
        <select v-model="home">
          <option v-for="h in homes" :key="h" :value="h">{{ h }}호</option>
        </select>
      </label>
      <label>14일 기록
        <select v-model="source">
          <option v-for="r in data?.replays || []" :key="r" :value="r">AIHub {{ r }}</option>
        </select>
      </label>
      <button class="btn ghost sm" type="button" :disabled="busy || !source || source === data?.source" @click="link">
        {{ data?.source ? '다른 기록으로 바꾸기' : '기록 연결' }}
      </button>
      <span v-if="!data?.replays?.length" class="hint">연결할 기록이 없습니다 — AIHub 원본이 있는 PC 에서 aihub_export.py 를 실행하세요</span>
    </div>

    <p v-if="error" class="msg err">{{ error }}</p>

    <template v-if="data?.source">
      <p class="msg info">
        {{ home }}호 ← AIHub {{ data.source }} ({{ data.period.start }} ~ {{ data.period.end }}).
        앞 14일로 기준을 만들고 뒤 14일에 적용해 봅니다. 08·09·10·11시마다 직전 1시간 10분 칸 6개를 보고,
        활동 칸 비율이 기준보다 낮으면서 30분 넘게 움직임이 없으면 생활 확인입니다. 기준 = 평소 비율(중앙값) × 0.5.
      </p>

      <table class="grid">
        <thead>
          <tr><th>평가 시각</th><th>보는 구간</th><th>평소 비율</th><th>유효일</th><th>공통 기준</th><th>추천 기준</th><th>적용 중</th></tr>
        </thead>
        <tbody>
          <tr v-for="h in HOURS" :key="h">
            <td>{{ hourLabel(h) }}</td>
            <td class="muted">{{ windowLabel(Number(h)) }}</td>
            <td>{{ pct(data.basis[h].median) }}</td>
            <td>{{ data.basis[h].valid_days }}/14일</td>
            <td>{{ pct(data.common[h]) }}</td>
            <td><b>{{ pct(data.recommended[h]) }}</b></td>
            <td>{{ current ? pct(current[h]) : '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div class="cols2">
        <div class="box">
          <h3>승인 전 안전성 검토</h3>
          <p v-if="data.check.ok" class="ok">✓ 통과 — 충족 불가능·공통 안전 정책 무력화 없음</p>
          <ul v-else class="bad"><li v-for="b in data.check.blocks" :key="b">✗ {{ b }}</li></ul>
          <ul v-if="data.check.notes.length" class="note"><li v-for="n in data.check.notes" :key="n">{{ n }}</li></ul>
        </div>
        <div class="box">
          <h3>미리보기 — 뒤 14일에 적용했다면</h3>
          <p>공통 기준: 생활 확인 <b>{{ data.preview.common.candidate_days }}일</b> ·
             추천 기준: <b>{{ data.preview.personal.candidate_days }}일</b>
             <span class="muted">({{ diff > 0 ? '+' : '' }}{{ diff }}일)</span></p>
          <p class="muted" v-if="Object.keys(data.preview.personal.first).length">
            추천 기준으로 걸린 날: {{ Object.entries(data.preview.personal.first).map(([d, t]) => `${d.slice(5)} ${t}`).join(', ') }}
          </p>
          <p class="muted" v-if="data.preview.personal.unverifiable_days">
            관측이 빠져 일부 시간창을 판단할 수 없었던 날 {{ data.preview.personal.unverifiable_days }}일 (0으로 채우지 않음)
          </p>
        </div>
      </div>

      <div class="decide">
        <span class="tag" :class="data.status === 'approved' ? 'tag-normal' : data.status === 'rejected' ? 'tag-muted' : 'tag-wait'">
          {{ STATUS[data.status] || '승인 대기' }}
        </span>
        <input v-model="memo" class="memo" maxlength="200" placeholder="메모 (선택) — 예: 오전 외출이 잦음" />
        <button class="btn ghost sm" type="button" :disabled="busy" @click="startEdit">수정해서 승인</button>
        <button class="btn ghost sm danger" type="button" :disabled="busy" @click="reject">거절</button>
        <button class="btn primary sm" type="button" :disabled="busy || !data.check.ok" @click="approve"
                :title="data.check.ok ? '' : '안전성 검토를 통과하지 못한 추천은 승인할 수 없습니다'">추천대로 승인</button>
      </div>

      <div v-if="editing" class="edit">
        <label v-for="h in HOURS" :key="h">{{ hourLabel(h) }}
          <input v-model="draft[h]" type="number" min="0" max="100" step="0.1" placeholder="판정 안 함" /> %
        </label>
        <button class="btn ghost sm" type="button" @click="editing = false">취소</button>
        <button class="btn primary sm" type="button" :disabled="busy" @click="saveEdit">검토 후 승인</button>
        <ul v-if="blocks.length" class="bad"><li v-for="b in blocks" :key="b">✗ {{ b }} — 저장하지 않았습니다</li></ul>
      </div>

      <details v-if="data.history.length" class="hist">
        <summary>변경 이력 {{ data.history.length }}건</summary>
        <ul>
          <li v-for="(h, i) in [...data.history].reverse()" :key="i">
            {{ h.at.replace('T', ' ').slice(0, 16) }} · {{ h.by }} ·
            {{ { link: `기록 연결 (${h.source})`, approve: h.modified ? '수정 승인' : '승인', reject: '거절' }[h.action] }}
            <span v-if="h.theta" class="muted">— {{ HOURS.map((k) => pct(h.theta[k])).join(' · ') }}</span>
            <span v-if="h.memo" class="muted">— {{ h.memo }}</span>
          </li>
        </ul>
      </details>
    </template>

    <RoutineReview v-if="home" :home="home" :worker="worker" />
  </section>
</template>

<style scoped>
.review { display: flex; flex-direction: column; gap: 0.8rem; }
.pick { display: flex; flex-wrap: wrap; gap: 0.6rem 1rem; align-items: center; }
.pick label { display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--text-2); }
.pick select, .memo, .edit input { padding: 0.3rem 0.45rem; border: 1px solid var(--border-strong); border-radius: 7px; font: inherit; font-size: 0.8rem; background: var(--surface); color: var(--text); }
.hint, .muted { color: var(--muted); font-size: 0.76rem; }
.grid { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.grid th { text-align: left; color: var(--muted); font-weight: 600; font-size: 0.72rem; padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
.grid td { padding: 0.5rem; border-bottom: 1px solid var(--border); }
.cols2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.8rem; }
.box { border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.8rem; font-size: 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
.box h3 { font-size: 0.82rem; font-weight: 700; }
.ok { color: var(--ok, #1a7f37); }
.bad { color: var(--danger, #c0392b); font-size: 0.78rem; padding-left: 0; list-style: none; }
.note { color: var(--muted); font-size: 0.76rem; padding-left: 1rem; }
.decide, .edit { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
.memo { flex: 1; min-width: 200px; }
.edit label { display: flex; align-items: center; gap: 0.3rem; font-size: 0.76rem; }
.edit input { width: 5.5rem; }
.edit .bad { flex-basis: 100%; }
.hist { font-size: 0.76rem; }
.hist ul { margin-top: 0.4rem; padding-left: 1rem; display: flex; flex-direction: column; gap: 0.2rem; }
</style>

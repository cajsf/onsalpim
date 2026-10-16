<script setup>
// 14일 개인 기준 추천 검토. 승인·수정·거부는 이 브라우저에만 남고 판정에는 넣지 않는다.
import { ref, computed } from 'vue'
import {
  HOURS, COMMON_THETA, HOUSEHOLDS, loadDecisions, saveDecisions, pct,
} from './baselineRecommendations.js'

const props = defineProps({
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['open', 'changed'])

const decisions = ref(loadDecisions())
const openId = ref(props.compact ? '' : 'E002')
const editing = ref('')
const draft = ref(['', '', '', ''])
const editError = ref('')

const STATUS = {
  pending: '승인 대기',
  modified: '수정됨 · 승인 대기',
  approved: '승인됨 · 판정 미적용',
  rejected: '거부',
  held: '추천 보류',
}

const rows = computed(() => HOUSEHOLDS.map((h) => ({ ...h, decision: decisions.value[h.id] })))

function persist() {
  saveDecisions(decisions.value)
  emit('changed', decisions.value)
}

function toggle(id) {
  if (props.compact) return
  openId.value = openId.value === id ? '' : id
  editing.value = ''
  editError.value = ''
}

function startEdit(h) {
  editing.value = h.id
  draft.value = decisions.value[h.id].theta.map((v) => (v * 100).toFixed(2))
  editError.value = ''
  openId.value = h.id
}

function cancelEdit() {
  editing.value = ''
  editError.value = ''
}

function saveEdit(h) {
  const theta = draft.value.map((s) => Number(String(s).trim()) / 100)
  if (theta.some((n) => !Number.isFinite(n) || n < 0 || n > 1)) {
    editError.value = '0에서 100 사이의 비율(%)을 네 칸 모두 입력해 주세요.'
    return
  }
  const same = theta.every((n, i) => Math.abs(n - h.theta[i]) < 1e-9)
  decisions.value = {
    ...decisions.value,
    [h.id]: { status: same ? 'pending' : 'modified', theta },
  }
  editing.value = ''
  editError.value = ''
  persist()
}

function approve(h) {
  if (h.hold) return
  decisions.value = {
    ...decisions.value,
    [h.id]: { ...decisions.value[h.id], status: 'approved' },
  }
  persist()
}

function reject(h) {
  if (h.hold) return
  decisions.value = {
    ...decisions.value,
    [h.id]: { ...decisions.value[h.id], status: 'rejected' },
  }
  editing.value = ''
  persist()
}

function reset(h) {
  decisions.value = {
    ...decisions.value,
    [h.id]: { status: 'pending', theta: h.theta.slice() },
  }
  editing.value = ''
  persist()
}

function delta(h) {
  const d = h.personalDays - h.commonDays
  return d > 0 ? `+${d}` : String(d)
}

function tagClass(status) {
  if (status === 'approved') return 'tag-normal'
  if (status === 'rejected') return 'tag-muted'
  if (status === 'held') return 'tag-watch'
  if (status === 'modified') return 'tag-device'
  return 'tag-wait'
}
</script>

<template>
  <section class="review">
    <div class="card-head">
      <div>
        <h2>14일 개인 기준 추천</h2>
        <p class="hint">
          AIHub 5가구, 앞 14일로 08·09·10·11시 활동 비율 임계값을 계산했습니다.
          후보 조건은 직전 1시간 활동 비율이 임계값보다 낮고, 관측된 연속 0이 30분 이상인 경우입니다.
        </p>
      </div>
      <button v-if="compact" class="btn primary" type="button" @click="emit('open')">검토하기</button>
    </div>

    <p class="msg info">
      공통 임계값은 08·09시 {{ pct(COMMON_THETA[0]) }}, 10·11시 {{ pct(COMMON_THETA[2]) }}입니다.
      승인·수정·거부는 이 화면에만 남고, 시연 세대 프로필과 실시간 판정에는 들어가지 않습니다.
      원본 시각의 시간대는 확정되지 않았습니다.
    </p>

    <div class="table-wrap">
      <table class="grid">
        <thead>
          <tr>
            <th>가구</th>
            <th>유형</th>
            <th>개인 08·09·10·11시</th>
            <th>공통 후보일</th>
            <th>개인 후보일</th>
            <th>차이</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="h in rows" :key="h.id">
            <tr class="crow" :class="{ open: openId === h.id, flat: compact }" @click="toggle(h.id)">
              <td class="home-cell">
                <span v-if="!compact" class="caret">{{ openId === h.id ? '▾' : '▸' }}</span>{{ h.id }}
                <span v-if="h.representative" class="tag tag-wait">대표</span>
              </td>
              <td>{{ h.type }}</td>
              <td class="mono nums">{{ h.decision.theta.map(pct).join(' · ') }}</td>
              <td>{{ h.commonDays }}</td>
              <td>{{ h.personalDays }}</td>
              <td>{{ delta(h) }}일</td>
              <td><span class="tag" :class="tagClass(h.decision.status)">{{ STATUS[h.decision.status] }}</span></td>
            </tr>
            <tr v-if="!compact && openId === h.id" class="detail">
              <td colspan="7">
                <p class="note">{{ h.note }}</p>
                <dl class="meta">
                  <div><dt>기준선</dt><dd>{{ h.baseline }}</dd></div>
                  <div><dt>검증</dt><dd>{{ h.validation }}</dd></div>
                  <div><dt>관측률</dt><dd>{{ h.coverage }}%</dd></div>
                  <div><dt>오전 중앙 활동</dt><dd>{{ pct(h.morningMedian) }}</dd></div>
                  <div><dt>하루 중앙 활동</dt><dd>{{ pct(h.dayMedian) }}</dd></div>
                  <div><dt>오전 au Q25·50·75·90</dt><dd class="mono">{{ h.au.join(' · ') }}</dd></div>
                  <div><dt>연속 0 Q90</dt><dd>{{ h.zeroQ90 }}분</dd></div>
                </dl>

                <p v-if="h.hold" class="msg warn">
                  이 가구는 추천 보류입니다. 임계값 0을 최소값으로 바꾸지 않습니다.
                </p>

                <div v-else-if="editing === h.id" class="edit">
                  <label v-for="(hour, i) in HOURS" :key="hour">
                    {{ hour }}
                    <input v-model="draft[i]" type="number" min="0" max="100" step="0.01" />
                    <span>%</span>
                  </label>
                  <p v-if="editError" class="msg err">{{ editError }}</p>
                  <div class="acts">
                    <button class="btn ghost sm" type="button" @click.stop="cancelEdit">취소</button>
                    <button class="btn primary sm" type="button" @click.stop="saveEdit(h)">수정값 저장</button>
                  </div>
                </div>

                <div v-else class="acts">
                  <button class="btn ghost sm" type="button" @click.stop="startEdit(h)">수정</button>
                  <button class="btn ghost sm danger" type="button" @click.stop="reject(h)">거부</button>
                  <button class="btn primary sm" type="button" @click.stop="approve(h)">승인</button>
                  <button
                    v-if="h.decision.status !== 'pending'"
                    class="btn ghost sm" type="button" @click.stop="reset(h)"
                  >원래 추천으로</button>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.review { display: flex; flex-direction: column; gap: 0.75rem; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.card-head h2 { font-size: 0.99rem; font-weight: 700; }
.hint { font-size: 0.76rem; color: var(--muted); margin-top: 0.15rem; }
.table-wrap { overflow-x: auto; }
.grid { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.grid th { text-align: left; color: var(--muted); font-weight: 600; font-size: 0.72rem; padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
.grid td { padding: 0.55rem 0.5rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
.crow { cursor: pointer; }
.crow.flat { cursor: default; }
.crow:hover { background: var(--surface-2); }
.home-cell { font-weight: 700; white-space: nowrap; }
.caret { display: inline-block; width: 1rem; color: var(--muted); }
.nums { font-size: 0.74rem; white-space: nowrap; }
.detail td { background: var(--surface-2); cursor: default; }
.note { font-size: 0.8rem; margin-bottom: 0.55rem; }
.meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.35rem 1rem; margin-bottom: 0.7rem; }
.meta > div { display: grid; grid-template-columns: 108px 1fr; gap: 0.4rem; font-size: 0.76rem; }
.meta dt { color: var(--muted); }
.edit { display: flex; flex-wrap: wrap; gap: 0.55rem 0.8rem; align-items: end; margin-top: 0.4rem; }
.edit label { display: flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; color: var(--text-2); }
.edit input { width: 5.2rem; padding: 0.28rem 0.4rem; border: 1px solid var(--border-strong); border-radius: 7px; font: inherit; }
.acts { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.65rem; }
</style>

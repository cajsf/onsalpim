<script setup>
// 알림 한 줄 + 대응 기록. 알림 이력·대시보드·세대 관리가 같이 쓴다.
// compact: 목록 요약용 (대응 상태 배지만). 아니면 대응 버튼과 기록까지.
import { ref, computed } from 'vue'
import { api } from './api.js'
import { ALERT_STATE, OUTCOMES, alertKo, alertClass, alertChange, outcomeKo, fmtAgo, stampOf, timeOf } from './format.js'

const props = defineProps({
  a: { type: Object, required: true },
  compact: { type: Boolean, default: false },
  showHome: { type: Boolean, default: true },
  focused: { type: Boolean, default: false },   // 팝업에서 '확인'하고 넘어왔을 때 눈에 띄게
  worker: { type: String, default: '복지사' },
})
const emit = defineEmits(['changed'])

const memoOpen = ref(false)
const editing = ref(false)          // 조치 완료 메모를 고치는 중
const memo = ref('')
const outcome = ref('')
const busy = ref(false)
const error = ref('')

// 회복 기록(state 없음)·조치 완료·뒤늦게 확인은 더 할 일이 없다
const actionable = computed(() => ['open', 'assign', 'ack', 'progress'].includes(props.a.state))
const st = computed(() => ALERT_STATE[props.a.state])
const mine = computed(() => !props.a.assignee || props.a.assignee === (props.worker || '복지사'))
const changeText = computed(() => (props.compact ? '' : alertChange(props.a)))

// 지금 보이는 조치 메모 — 고쳤으면 마지막 수정본
const lastMemo = computed(() =>
  [...props.a.log].reverse().find((l) => l.status === 'done' || l.status === 'edit')?.memo || '')

function startEdit() {
  editing.value = true
  memo.value = lastMemo.value
  memoOpen.value = true
}

async function act(status) {
  if (busy.value) return            // 응답 오기 전 연타는 버린다
  if (status === 'done' && !memoOpen.value) { editing.value = false; outcome.value = ''; memoOpen.value = true; return }
  if (status === 'done' && !outcome.value) { error.value = '결과를 골라 주세요.'; return }
  busy.value = true
  error.value = ''
  const withMemo = status === 'done' || status === 'edit'
  const r = await api.actAlert(props.a.id, status, withMemo ? memo.value : '', {
    by: props.worker || '복지사',
    outcome: status === 'done' ? outcome.value : '',
  })
  busy.value = false
  if (!r.ok) { error.value = (r.errors || []).join(' '); return }
  memoOpen.value = false
  editing.value = false
  memo.value = ''
  emit('changed', { id: props.a.id, log: r.log, assignee: r.assignee })
}
</script>

<template>
  <li class="ai" :class="{ open: a.state === 'open', focused }" :data-alert-id="a.id">
    <div class="ai-row">
      <!-- 안부 확인: 위험도는 '점검 필요' 그대로라 'A → A'로 보이지 않게 따로 적는다 -->
      <span class="tag" :class="'tag-' + alertClass(a)">{{ alertKo(a) }}</span>
      <span class="atext">
        <strong v-if="showHome">{{ a.outage ? '전체 ' : a.home + '호 ' }}</strong>
        <template v-if="changeText">{{ changeText }}</template>{{ a.reason }}
      </span>
      <span v-if="a.assignee" class="tag tag-life">{{ a.assignee }}</span>
      <span v-if="st" class="tag" :class="'tag-' + st.cls">{{ st.ko }}</span>
      <span class="atime mono">{{ compact ? timeOf(a.ts) : stampOf(a.ts) }}</span>
    </div>

    <template v-if="!compact">
      <ol v-if="a.log.length" class="log">
        <li v-for="(l, i) in a.log" :key="i">
          <span class="mono">{{ timeOf(l.at) }}</span>
          <strong>{{ ALERT_STATE[l.status]?.ko }}</strong> · {{ l.by }}
          <span v-if="i === 0 && a.first_response_s != null" class="muted">
            (알림 후 {{ fmtAgo(a.first_response_s).replace(' 전', '') }} 만에)
          </span>
          <span v-if="l.outcome" class="memo">— {{ outcomeKo(l.outcome) }}</span>
          <span v-if="l.memo" class="memo">{{ l.outcome ? '·' : '—' }} {{ l.memo }}</span>
        </li>
      </ol>

      <!-- 응답 없이 지나간 알림은 이미 상황이 바뀌었다 — 뒤늦게 봤다는 확인만 남긴다 -->
      <div v-if="a.state === 'missed'" class="acts">
        <button class="btn sm ghost" :disabled="busy" @click="act('late')">뒤늦게 확인</button>
      </div>
      <div v-else-if="a.state === 'done' && !memoOpen" class="acts">
        <button class="btn sm ghost" @click="startEdit">메모 수정</button>
      </div>
      <p v-else-if="actionable && a.assignee && !mine" class="err">{{ a.assignee }}가 맡은 알림입니다.</p>
      <div v-else-if="actionable && !a.assignee" class="acts">
        <button class="btn sm primary" :disabled="busy" @click="act('assign')">맡기</button>
      </div>
      <div v-else-if="actionable && mine" class="acts">
        <button v-if="a.state === 'open' || a.state === 'assign'" class="btn sm" :disabled="busy" @click="act('ack')">확인</button>
        <button v-if="a.state !== 'progress'" class="btn sm" :disabled="busy" @click="act('progress')">방문·연락 중</button>
        <button class="btn sm primary" :disabled="busy" @click="act('done')">조치 완료</button>
      </div>
      <div v-if="memoOpen" class="memo-box">
        <div v-if="!editing" class="outcomes">
          <button v-for="o in OUTCOMES" :key="o.id" type="button" class="btn sm"
                  :class="{ on: outcome === o.id }" @click="outcome = o.id">{{ o.ko }}</button>
        </div>
        <input v-model="memo" maxlength="200" placeholder="메모 (선택). 예: 전화로 확인"
               @keyup.enter="act(editing ? 'edit' : 'done')" />
        <button class="btn sm primary" :disabled="busy || (editing ? !memo.trim() : !outcome)" @click="act(editing ? 'edit' : 'done')">
          {{ editing ? '수정 저장' : '저장' }}
        </button>
        <button class="btn sm ghost" @click="memoOpen = false; editing = false">취소</button>
        <span v-if="editing" class="muted hint-edit">원래 메모는 기록에 그대로 남습니다.</span>
      </div>
      <p v-if="error" class="err">{{ error }}</p>
    </template>
  </li>
</template>

<style scoped>
.ai { display: grid; gap: 0.35rem; padding: 0.6rem 0; border-bottom: 1px solid var(--border); font-size: 0.8rem; }
.ai:last-child { border-bottom: 0; }
.ai.open { background: linear-gradient(90deg, var(--urgent-soft), transparent 60%); margin: 0 -0.6rem; padding-left: 0.6rem; padding-right: 0.6rem; border-radius: 6px; }
.ai-row { display: flex; align-items: center; gap: 0.6rem; min-width: 0; }
.atext { flex: 1; color: var(--text-2); min-width: 0; }
.atime { color: var(--muted); font-size: 0.72rem; white-space: nowrap; }
.log { list-style: none; margin: 0; padding: 0 0 0 0.2rem; display: grid; gap: 0.15rem; font-size: 0.74rem; color: var(--text-2); border-left: 2px solid var(--border); padding-left: 0.6rem; }
.log .mono { color: var(--muted); margin-right: 0.3rem; }
.memo { color: var(--text); }
.acts, .memo-box, .outcomes { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.outcomes { margin-bottom: 0.15rem; }
.btn.on { border-color: var(--brand); color: var(--brand-dim); background: var(--brand-soft); }
.memo-box input { flex: 1 1 220px; padding: 0.35rem 0.55rem; border: 1px solid var(--border-strong); border-radius: 6px; font-size: 0.76rem; }
.err { color: var(--urgent); font-size: 0.74rem; margin: 0; }
.hint-edit { font-size: 0.72rem; }
.ai.focused { outline: 2px solid var(--brand); outline-offset: 2px; border-radius: 6px; animation: pulse 1.2s ease-out 2; }
@keyframes pulse { from { outline-color: var(--brand); } to { outline-color: transparent; } }
@media (prefers-reduced-motion: reduce) { .ai.focused { animation: none; } }
</style>

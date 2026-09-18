<script setup>
// 알림 한 줄 + 대응 기록. 알림 이력·대시보드·세대 관리가 같이 쓴다.
// compact: 목록 요약용 (대응 상태 배지만). 아니면 대응 버튼과 기록까지.
import { ref, computed } from 'vue'
import { api } from './api.js'
import { SEV, ALERT_STATE, fmtAgo, stampOf, timeOf } from './format.js'

const props = defineProps({
  a: { type: Object, required: true },
  compact: { type: Boolean, default: false },
  showHome: { type: Boolean, default: true },
})
const emit = defineEmits(['changed'])

const memoOpen = ref(false)
const memo = ref('')
const busy = ref(false)
const error = ref('')

// 회복 기록(state 없음)·조치 완료·뒤늦게 확인은 더 할 일이 없다
const actionable = computed(() => ['open', 'ack', 'progress'].includes(props.a.state))
const st = computed(() => ALERT_STATE[props.a.state])

async function act(status) {
  if (status === 'done' && !memoOpen.value) { memoOpen.value = true; return }
  busy.value = true
  error.value = ''
  const r = await api.actAlert(props.a.id, status, status === 'done' ? memo.value : '')
  busy.value = false
  if (!r.ok) { error.value = (r.errors || []).join(' '); return }
  memoOpen.value = false
  memo.value = ''
  emit('changed')
}
</script>

<template>
  <li class="ai" :class="{ open: a.state === 'open' }">
    <div class="ai-row">
      <span class="tag" :class="'tag-' + SEV[a.to]?.cls">{{ SEV[a.to]?.ko }}</span>
      <span class="atext">
        <strong v-if="showHome">{{ a.home }}호 </strong>
        <template v-if="!compact">{{ a.from ? SEV[a.from]?.ko : '첫 판정' }} → {{ SEV[a.to]?.ko }} · </template>{{ a.reason }}
      </span>
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
          <span v-if="l.memo" class="memo">— {{ l.memo }}</span>
        </li>
      </ol>

      <!-- 응답 없이 지나간 알림은 이미 상황이 바뀌었다 — 뒤늦게 봤다는 확인만 남긴다 -->
      <div v-if="a.state === 'missed'" class="acts">
        <button class="btn sm ghost" :disabled="busy" @click="act('late')">뒤늦게 확인</button>
      </div>
      <div v-else-if="actionable" class="acts">
        <button v-if="!a.log.length" class="btn sm" :disabled="busy" @click="act('ack')">확인</button>
        <button v-if="a.state !== 'progress'" class="btn sm" :disabled="busy" @click="act('progress')">방문·연락 중</button>
        <button class="btn sm primary" :disabled="busy" @click="act('done')">조치 완료</button>
      </div>
      <div v-if="memoOpen" class="memo-box">
        <input v-model="memo" maxlength="200" placeholder="무엇을 했는지 적어 주세요 (예: 전화 통화, 이상 없음)"
               @keyup.enter="act('done')" />
        <button class="btn sm primary" :disabled="busy || !memo.trim()" @click="act('done')">저장</button>
        <button class="btn sm ghost" @click="memoOpen = false">취소</button>
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
.acts, .memo-box { display: flex; gap: 0.35rem; flex-wrap: wrap; align-items: center; }
.memo-box input { flex: 1 1 220px; padding: 0.35rem 0.55rem; border: 1px solid var(--border-strong); border-radius: 6px; font-size: 0.76rem; }
.err { color: var(--urgent); font-size: 0.74rem; margin: 0; }
</style>

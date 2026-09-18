<script setup>
// 새 알림 팝업 — 화면을 연 뒤에 새로 생긴 '대응 필요' 알림만 띄운다.
// 목록에만 쌓이면 복지사가 다른 화면을 보는 동안 놓친다. 대응(확인)하거나 상태가 바뀌면 사라진다.
// 닫기(×)는 팝업만 치우는 것 — 알림은 '대응 필요'로 남는다.
import { ref, computed, watch } from 'vue'
import { api } from './api.js'
import { SEV, timeOf } from './format.js'

const props = defineProps({
  alerts: { type: Array, required: true },
  sound: { type: Boolean, default: true },
})
const emit = defineEmits(['open-home', 'open-alerts', 'changed'])
const MAX = 3                   // 한꺼번에 여러 세대가 끊기면 화면을 덮는다 — 나머지는 한 줄로

let seen = null                 // 처음 불러온 알림은 이미 있던 것 — 팝업하지 않는다
const shown = ref([])           // 팝업 중인 알림 id
const busy = ref('')

watch(() => props.alerts, (list) => {
  const ids = list.map((a) => a.id)
  if (seen === null) { seen = new Set(ids); return }
  const fresh = list.filter((a) => !seen.has(a.id) && a.state === 'open')
  ids.forEach((id) => seen.add(id))
  if (fresh.length) {
    shown.value = [...fresh.map((a) => a.id), ...shown.value]
    if (props.sound) beep(fresh.some((a) => a.to === 'URGENT'))
  }
})

// 대응됐거나 상태가 바뀐 알림은 알아서 빠진다
const toasts = computed(() =>
  shown.value.map((id) => props.alerts.find((a) => a.id === id)).filter((a) => a && a.state === 'open'))

function dismiss(id) { shown.value = shown.value.filter((x) => x !== id) }

async function ack(a) {
  if (busy.value) return
  busy.value = a.id
  const r = await api.actAlert(a.id, 'ack')
  busy.value = ''
  dismiss(a.id)
  if (r.ok) emit('changed', { id: a.id, log: r.log })
}

/* 소리 — 파일 없이 브라우저가 만든다. 브라우저 정책상 화면을 한 번 누른 뒤부터 난다. */
let ctx = null
function beep(urgent) {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)()
    const tones = urgent ? [880, 660, 880] : [660]
    tones.forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain()
      o.frequency.value = f
      g.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.22)
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.22 + 0.2)
      o.connect(g).connect(ctx.destination)
      o.start(ctx.currentTime + i * 0.22)
      o.stop(ctx.currentTime + i * 0.22 + 0.2)
    })
  } catch { /* 소리를 못 내도 팝업은 뜬다 */ }
}
</script>

<template>
  <div class="toasts" aria-live="assertive">
    <div v-for="a in toasts.slice(0, MAX)" :key="a.id" class="toast" :class="'t-' + SEV[a.to]?.cls" role="alert">
      <div class="t-head">
        <span class="tag" :class="'tag-' + SEV[a.to]?.cls">{{ SEV[a.to]?.ko }}</span>
        <strong>{{ a.home }}호</strong>
        <span class="mono t-time">{{ timeOf(a.ts) }}</span>
        <button class="t-x" title="팝업 닫기 (알림은 '대응 필요'로 남습니다)" @click="dismiss(a.id)">×</button>
      </div>
      <p class="t-reason">{{ a.reason }}</p>
      <div class="t-acts">
        <button class="btn sm primary" :disabled="busy === a.id" @click="ack(a)">확인</button>
        <button class="btn sm" @click="emit('open-home', a.home); dismiss(a.id)">세대 보기</button>
      </div>
    </div>
    <button v-if="toasts.length > MAX" class="toast more" @click="emit('open-alerts')">
      외 {{ toasts.length - MAX }}건 — 알림 이력에서 보기
    </button>
  </div>
</template>

<style scoped>
.toasts { position: fixed; right: 1rem; bottom: 1rem; display: flex; flex-direction: column; gap: 0.6rem; z-index: 50; width: min(340px, calc(100vw - 2rem)); }
.toast { background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--urgent); border-radius: 10px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.16); padding: 0.75rem 0.85rem; display: grid; gap: 0.4rem; animation: in 0.25s ease-out; }
.t-device { border-left-color: var(--device); }
.t-watch { border-left-color: var(--watch); }
.t-head { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
.t-time { color: var(--muted); font-size: 0.72rem; margin-left: auto; }
.t-x { border: 0; background: none; font-size: 1.1rem; line-height: 1; color: var(--muted); cursor: pointer; padding: 0 0.2rem; }
.t-reason { margin: 0; font-size: 0.8rem; color: var(--text-2); }
.t-acts { display: flex; gap: 0.4rem; }
.more { cursor: pointer; font-size: 0.8rem; font-weight: 600; color: var(--text-2); text-align: left; border-left-color: var(--border-strong); }
@keyframes in { from { transform: translateY(8px); opacity: 0; } to { transform: none; opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .toast { animation: none; } }
</style>

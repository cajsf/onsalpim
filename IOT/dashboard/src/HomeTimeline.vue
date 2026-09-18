<script setup>
// 세대 타임라인 — 언제 움직였고, 판정이 언제 어떻게 바뀌었나.
// '지금 긴급'만으로는 왜 긴급인지 따라가기 어렵다. 움직임이 끊긴 뒤 기준 시간이 지나 빨갛게
// 바뀌는 것, 통신이 끊기면 보라색(점검 필요)으로 바뀌는 것을 시간 축 위에서 보여준다.
// 데이터는 엔진이 판정하며 남긴 기록(/api/history) — 화면은 그리기만 한다.
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { api } from './api.js'
import { SEV, nowMs } from './format.js'

const props = defineProps({
  home: { type: String, required: true },
  judgedAt: { type: String, default: null },   // 가장 최근 판정 시각 — 그 뒤는 '판정 없음'
})

const WINDOWS = [{ h: 0.25, label: '15분' }, { h: 1, label: '1시간' }, { h: 24, label: '24시간' }]
const hours = ref(1)
const hist = ref({ sev: [], move: [] })
const failed = ref(false)

async function load() {
  try {
    hist.value = await api.getHistory(props.home)
    failed.value = false
  } catch {
    failed.value = true
  }
}
let timer = null
onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
watch(() => props.home, load)

const t = (iso) => Date.parse(iso)
const end = computed(() => nowMs.value)
const start = computed(() => end.value - hours.value * 3600e3)
const pct = (ms) => ((ms - start.value) / (end.value - start.value)) * 100

function hm(ms) {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function dur(ms) {
  const m = Math.round(ms / 60000)
  return m < 60 ? `${m}분` : `${Math.floor(m / 60)}시간 ${m % 60}분`
}

/* 위험도 구간 — 다음 기록까지 이어진다. 마지막 구간은 마지막 판정 시각까지만:
   엔진이 멈췄는데 지금까지 칠하면 판정하지 않은 시간을 판정한 것처럼 보인다. */
const bands = computed(() => {
  const s = hist.value.sev
  const last = props.judgedAt ? Math.min(t(props.judgedAt), end.value) : end.value
  const out = []
  s.forEach(([at, sev], i) => {
    const a = Math.max(t(at), start.value)
    const b = Math.min(i + 1 < s.length ? t(s[i + 1][0]) : last, end.value)
    if (b > a) out.push({ a, b, sev })
  })
  if (s.length && last < end.value - 30e3) out.push({ a: Math.max(last, start.value), b: end.value, sev: null })
  return out.map((x) => ({
    ...x,
    left: pct(x.a), width: pct(x.b) - pct(x.a),
    cls: x.sev ? SEV[x.sev]?.cls : 'none',
    tip: `${hm(x.a)}–${hm(x.b)} · ${x.sev ? SEV[x.sev]?.ko : '판정 없음 (엔진 꺼짐)'} · ${dur(x.b - x.a)}`,
  }))
})

const moves = computed(() =>
  hist.value.move.map(t).filter((m) => m >= start.value && m <= end.value)
    .map((m) => ({ m, left: pct(m), tip: `${hm(m)} 움직임 관측` })))

/* 그림을 못 보는 경우를 위한 한 줄 요약 */
const summary = computed(() => {
  const sum = (sev) => bands.value.filter((b) => b.sev === sev).reduce((n, b) => n + (b.b - b.a), 0)
  const parts = [`움직임 ${moves.value.length}회 관측`]
  if (moves.value.length) parts.push(`마지막 ${hm(moves.value.at(-1).m)}`)
  for (const k of ['URGENT', 'CHECK_DEVICE', 'WATCH']) {
    const ms = sum(k)
    if (ms >= 60000) parts.push(`${SEV[k].ko} ${dur(ms)}`)
  }
  return parts.join(' · ')
})

const ticks = computed(() => [0, 0.5, 1].map((f) => ({
  left: f * 100, label: f === 1 ? '지금' : hm(start.value + f * (end.value - start.value)),
})))
</script>

<template>
  <div class="tl">
    <div class="tl-head">
      <span class="muted">{{ failed ? '타임라인을 불러오지 못했습니다' : summary }}</span>
      <div class="seg">
        <button v-for="w in WINDOWS" :key="w.h" class="seg-btn" :class="{ on: hours === w.h }"
                @click="hours = w.h">{{ w.label }}</button>
      </div>
    </div>

    <div class="tl-row">
      <span class="tl-label">판정</span>
      <div class="tl-track">
        <div v-for="(b, i) in bands" :key="i" class="band" :class="'b-' + b.cls"
             :style="{ left: b.left + '%', width: b.width + '%' }" :title="b.tip">
          <!-- 정상(초록)·주의(노랑)는 적록색약에게 비슷해 보인다 — 넓은 구간엔 글자로도 적는다 -->
          <span v-if="b.sev && b.width > 12" class="bl">{{ SEV[b.sev].ko }}</span>
        </div>
      </div>
    </div>
    <div class="tl-row">
      <span class="tl-label">움직임</span>
      <div class="tl-track moves">
        <div v-for="x in moves" :key="x.m" class="tick" :style="{ left: x.left + '%' }">
          <span class="hit" :title="x.tip"></span>
        </div>
      </div>
    </div>
    <div class="tl-row axis">
      <span class="tl-label"></span>
      <div class="tl-track bare">
        <span v-for="k in ticks" :key="k.left" class="ax" :style="{ left: k.left + '%' }">{{ k.label }}</span>
      </div>
    </div>

    <p v-if="!hist.sev.length && !failed" class="muted note">
      아직 기록이 없습니다. 규칙 엔진이 돌기 시작한 뒤부터 쌓입니다.
    </p>
    <ul class="legend">
      <li v-for="k in ['NORMAL', 'WATCH', 'URGENT', 'CHECK_DEVICE']" :key="k">
        <i :class="'b-' + SEV[k].cls"></i>{{ SEV[k].ko }}
      </li>
      <li><i class="b-none"></i>판정 없음</li>
      <li><i class="sw-move"></i>움직임 (1분 단위)</li>
    </ul>
  </div>
</template>

<style scoped>
.tl { display: grid; gap: 0.35rem; }
.tl-head { display: flex; justify-content: space-between; align-items: center; gap: 0.8rem; flex-wrap: wrap; font-size: 0.78rem; }
.tl-row { display: grid; grid-template-columns: 48px 1fr; gap: 0.6rem; align-items: center; }
.tl-label { font-size: 0.74rem; color: var(--muted); }
.tl-track { position: relative; height: 22px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
.tl-track.bare { border: 0; }
.seg { display: flex; gap: 0.2rem; background: var(--surface-2); padding: 0.2rem; border-radius: 8px; }
.seg-btn { padding: 0.25rem 0.6rem; border: 0; background: none; border-radius: 6px; font-size: 0.74rem; color: var(--text-2); cursor: pointer; }
.seg-btn.on { background: var(--surface); color: var(--brand-dim); font-weight: 600; box-shadow: var(--shadow-sm); }
.tl-track.moves { height: 18px; }
.tl-track.bare { height: 16px; background: none; overflow: visible; }
.band { position: absolute; top: 0; bottom: 0; box-shadow: inset -2px 0 0 var(--surface); }
.bl { position: absolute; left: 6px; top: 50%; transform: translateY(-50%); font-size: 0.68rem; font-weight: 600; color: #fff; white-space: nowrap; }
.b-normal { background: var(--normal); }
.b-watch { background: var(--watch); }
.b-urgent { background: var(--urgent); }
.b-device { background: var(--device); }
.b-none { background: repeating-linear-gradient(45deg, var(--border) 0 4px, transparent 4px 8px); }
.tick { position: absolute; top: 3px; bottom: 3px; width: 2px; margin-left: -1px; background: var(--text); border-radius: 1px; }
.hit { position: absolute; left: -5px; right: -5px; top: -3px; bottom: -3px; }
.ax { position: absolute; transform: translateX(-50%); font-size: 0.68rem; color: var(--muted); white-space: nowrap; }
.ax:first-child { transform: none; }
.ax:last-child { transform: translateX(-100%); }
.legend { display: flex; flex-wrap: wrap; gap: 0.3rem 0.9rem; list-style: none; padding: 0; margin: 0.2rem 0 0; font-size: 0.72rem; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 0.3rem; }
.legend i { width: 12px; height: 10px; border-radius: 2px; display: inline-block; }
.legend .sw-move { width: 2px; height: 10px; background: var(--text); }
.note { font-size: 0.76rem; margin: 0; }
</style>

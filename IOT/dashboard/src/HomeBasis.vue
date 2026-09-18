<script setup>
// 세대 하나의 판단 근거 — 결과만 보고도 판단 과정을 따라갈 수 있어야 한다.
// 대시보드 표의 펼침과 세대 관리 화면이 같은 모양으로 보여주도록 한 곳에 둔다.
import { computed } from 'vue'
import { SEV, fmtAgo, fmtMinutes, secondsSince } from './format.js'

const props = defineProps({ h: { type: Object, required: true } })

// 실제 시각이 있으면 지금 기준으로 다시 계산한다. (옛 판정 파일에는 시각이 없어 경과 초로 대체)
const contactAgo = computed(() =>
  props.h.last_contact_at !== undefined ? secondsSince(props.h.last_contact_at) : props.h.silent_s)
const activityAgo = computed(() =>
  props.h.last_activity_at !== undefined ? secondsSince(props.h.last_activity_at) : props.h.idle_s)
const judgedAgo = computed(() => secondsSince(props.h.judged_at))
</script>

<template>
  <dl class="basis">
    <div>
      <dt>마지막 통신</dt>
      <dd>
        {{ fmtAgo(contactAgo) }}
        <span v-if="h.severity === 'CHECK_DEVICE'" class="flag">두절</span>
      </dd>
    </div>
    <div>
      <dt>마지막 움직임</dt>
      <dd>
        {{ fmtAgo(activityAgo) }}
        <span v-if="!h.life_known" class="muted">(기록 기준) · 통신 두절 이후는 확인 불가</span>
      </dd>
    </div>
    <div v-if="h.applied && h.applied.common">
      <dt>공통 기준</dt><dd>{{ fmtMinutes(h.applied.common) }}</dd>
    </div>
    <div v-if="h.idle_levels && h.idle_levels.length > 1">
      <dt>단계 기준</dt>
      <dd>
        <span v-for="(lv, i) in h.idle_levels" :key="i">
          {{ i ? ' → ' : '' }}{{ fmtMinutes(lv.minutes) }} {{ SEV[lv.severity]?.ko }}
        </span>
      </dd>
    </div>
    <div v-if="h.idle_min != null">
      <dt>적용 기준</dt>
      <dd>
        {{ fmtMinutes(h.idle_min) }}
        <span v-if="h.applied && h.applied.source === 'override'" class="flag ovr-flag">
          {{ h.home }}호 예외
        </span>
      </dd>
    </div>
    <div v-if="h.battery != null">
      <dt>배터리</dt><dd>{{ Math.round(h.battery) }}%</dd>
    </div>
    <div class="sep">
      <dt>판정</dt>
      <dd><span class="tag" :class="'tag-' + SEV[h.severity]?.cls">{{ SEV[h.severity]?.ko }}</span></dd>
    </div>
    <div><dt>판단 근거</dt><dd class="basis-text">{{ h.basis }}</dd></div>
    <div v-if="judgedAgo != null">
      <dt>판정 시각</dt>
      <dd>
        {{ fmtAgo(judgedAgo) }}
        <span v-if="judgedAgo > 30" class="flag">판정이 갱신되지 않음</span>
      </dd>
    </div>
  </dl>
</template>

<style scoped>
.basis { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 0.4rem 1.6rem; }
.basis > div { display: grid; grid-template-columns: 88px 1fr; gap: 0.6rem; font-size: 0.79rem; align-items: baseline; }
.basis dt { color: var(--muted); }
.basis dd { color: var(--text); }
.basis .sep { grid-column: 1 / -1; border-top: 1px solid var(--border); padding-top: 0.5rem; margin-top: 0.3rem; }
.basis-text { font-weight: 600; }
</style>

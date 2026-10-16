<script setup>
// 무활동이 기준에 얼마나 가까워졌는지. 기준이 없는 세대는 그리지 않는다.
import { computed } from 'vue'
import { idleBar, secondsSince } from './format.js'

const props = defineProps({
  h: { type: Object, required: true },
  size: { type: String, default: 'lg' },
})

const activityAgo = computed(() =>
  props.h.last_activity_at !== undefined ? secondsSince(props.h.last_activity_at) : props.h.idle_s)

const bar = computed(() => idleBar(activityAgo.value, props.h.idle_min, props.h.idle_levels, {
  away: !!props.h.away,
  lifeKnown: props.h.life_known !== false,
}))

const width = computed(() => (bar.value?.ratio == null ? '0%' : `${bar.value.ratio * 100}%`))
</script>

<template>
  <div v-if="bar" class="idle" :class="[size, bar.tone]">
    <div class="idle-top">
      <span class="idle-big">{{ bar.big }}</span>
      <span class="idle-cap">{{ bar.text }}</span>
    </div>
    <div
      class="track"
      role="progressbar"
      :aria-label="bar.text"
      :aria-valuemin="0"
      :aria-valuemax="bar.limitMin"
      :aria-valuenow="bar.elapsed == null ? undefined : Math.round(bar.elapsed / 60)"
    >
      <div class="fill" :style="{ width }"></div>
      <span
        v-for="(tick, i) in bar.ticks"
        :key="i"
        class="mark"
        :style="{ left: (tick.at * 100) + '%' }"
        :title="tick.title"
      ></span>
    </div>
  </div>
</template>

<style scoped>
.idle { display: flex; flex-direction: column; gap: 0.35rem; min-width: 0; }
.idle.lg { grid-column: 1 / -1; margin-bottom: 0.35rem; }
.idle.sm { margin-top: 0.35rem; max-width: 220px; }
.idle-top { display: flex; align-items: baseline; gap: 0.55rem; flex-wrap: wrap; }
.idle-big { font-weight: 700; letter-spacing: -0.02em; color: var(--text); line-height: 1.1; }
.lg .idle-big { font-size: 1.35rem; }
.sm .idle-big { display: none; }
.idle-cap { font-size: 0.75rem; color: var(--text-2); }
.track {
  position: relative; height: 8px; border-radius: 999px; background: var(--surface-2);
  border: 1px solid var(--border); overflow: hidden;
}
.sm .track { height: 5px; }
.fill { height: 100%; border-radius: inherit; width: 0; }
.ok .fill { background: var(--normal); }
.watch .fill { background: var(--watch); }
.urgent .fill { background: var(--urgent); }
.held .fill { background: var(--muted); }
.unknown .fill { width: 0 !important; }
.mark {
  position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px;
  background: var(--text-2); opacity: 0.45;
}
</style>

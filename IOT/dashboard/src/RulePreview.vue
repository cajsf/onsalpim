<script setup>
import { computed, ref, watch } from 'vue'
import { api } from './api.js'

const props = defineProps({
  ruleId: { type: Number, required: true },
  fillValue: { type: String, default: '' },
  replace: { type: Boolean, default: false },
  /** 무활동 규칙이 아니거나 기준값이 비어 있으면 false */
  enabled: { type: Boolean, default: true },
})

const loading = ref(false)
const data = ref(null)
const err = ref('')

async function load() {
  if (!props.enabled || !props.ruleId) {
    data.value = null
    err.value = ''
    return
  }
  loading.value = true
  err.value = ''
  try {
    data.value = await api.previewRule(props.ruleId, props.fillValue || undefined, props.replace)
    if (!data.value.ok && data.value.errors?.length) {
      err.value = data.value.errors.join(' ')
    }
  } catch (e) {
    data.value = null
    err.value = e.message || '미리보기를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.ruleId, props.fillValue, props.replace, props.enabled],
  () => { load() },
  { immediate: true },
)

const summary = computed(() => {
  if (!data.value?.ok) return null
  return data.value
})

const hot = computed(() => (summary.value?.homes || []).filter((h) => h.alerts > 0))
</script>

<template>
  <div v-if="enabled" class="rule-preview">
    <p class="sec-title preview-title">규칙 미리 돌려 보기 (지난 {{ summary?.days || 14 }}일)</p>
    <p class="hint">
      승인 전에, 이 규칙이 지난 2주 동안 적용돼 있었다면 세대별로 알림이 몇 번 울렸을지 추정합니다.
      아래 <strong>지금 규칙 그대로였다면</strong>과 비교해 잘못 읽은 기준(예: 8시간→30분)을 확인하세요.
    </p>

    <p v-if="loading" class="muted">기록을 대입하는 중…</p>
    <p v-else-if="err" class="msg warn">{{ err }}</p>
    <p v-else-if="data && data.supported === false" class="msg info">{{ data.reason }}</p>

    <template v-else-if="summary">
      <p v-if="summary.total >= 20 || summary.delta_total >= 20" class="msg warn">
        이 기준으로는 추정 알림이 {{ summary.total }}건입니다
        <template v-if="summary.delta_total > 0">(지금 규칙보다 +{{ summary.delta_total }}건)</template>.
        기준을 다시 읽어 보고, 맞을 때만 승인하세요.
      </p>
      <p v-if="summary.sparse_data" class="msg info">
        이 구간에 움직임 기록이 거의 없습니다. 엔진을 더 오래 켜 두면 추정이 정확해집니다.
      </p>
      <div class="preview-kpi">
        <div>
          <span class="k">이 규칙 적용 시</span>
          <strong class="v" :class="{ hot: summary.total >= 20 }">{{ summary.total }}건</strong>
        </div>
        <div>
          <span class="k">지금 규칙 그대로였다면</span>
          <strong class="v">{{ summary.baseline_total }}건</strong>
        </div>
        <div v-if="summary.actual_total != null">
          <span class="k">실제 알림 (기록)</span>
          <strong class="v">{{ summary.actual_total }}건</strong>
        </div>
      </div>

      <table v-if="hot.length" class="preview-grid">
        <thead>
          <tr>
            <th>세대</th>
            <th>알림 (추정)</th>
            <th>긴급</th>
            <th>주의</th>
            <th>지금 규칙 대비</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in hot" :key="h.home">
            <td>{{ h.home }}호</td>
            <td><strong>{{ h.alerts }}</strong></td>
            <td>{{ h.urgent }}</td>
            <td>{{ h.watch }}</td>
            <td :class="{ up: h.delta > 0, down: h.delta < 0 }">
              {{ h.delta > 0 ? '+' : '' }}{{ h.delta }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">추정 알림 0건 — 기준을 넘는 무활동 구간이 없었습니다.</p>
      <p class="muted note">{{ summary.note }}</p>
    </template>
  </div>
</template>

<style scoped>
.rule-preview {
  margin-top: 0.85rem;
  padding-top: 0.75rem;
  border-top: 1px dashed var(--border);
}
.preview-title { margin-bottom: 0.25rem; }
.preview-kpi {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  margin: 0.65rem 0;
}
.preview-kpi .k { display: block; font-size: 0.72rem; color: var(--muted); }
.preview-kpi .v { font-size: 1.15rem; }
.preview-kpi .v.hot { color: var(--urgent, #c0392b); }
.preview-grid {
  width: 100%;
  font-size: 0.82rem;
  border-collapse: collapse;
  margin-top: 0.35rem;
}
.preview-grid th, .preview-grid td {
  border-bottom: 1px solid var(--border);
  padding: 0.35rem 0.5rem;
  text-align: left;
}
.preview-grid .up { color: var(--urgent, #c0392b); font-weight: 600; }
.preview-grid .down { color: var(--ok, #2e7d32); }
.note { font-size: 0.72rem; margin-top: 0.5rem; }
</style>

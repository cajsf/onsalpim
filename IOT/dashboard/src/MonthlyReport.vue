<script setup>
// 월간 보고 초안 — 2026 사업안내 월간보고의 '5일 이상 활동미감지·전원차단·데이터미수신 대상자 명단(사유 포함)'.
// 사유는 판정이 붙인 라벨(초안)이고, 확정은 복지사가 한다. 공식 서식은 보지 못해 항목 이름만 따랐다.
import { ref, watch, onMounted } from 'vue'
import { api } from './api.js'
import { stampOf } from './format.js'

const today = new Date()   // toISOString 은 UTC 라 1일 새벽에 지난달이 된다 — 현지 날짜로
const thisMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
const month = ref(thisMonth)
// 시연은 몇 분이면 끝난다 — 5일 기준으로는 아무것도 안 나와서 짧은 기준을 따로 둔다
const LIMITS = [
  { s: 5 * 86400, label: '5일 이상 (보고 기준)' },
  { s: 60, label: '1분 이상 (시연용)' },
]
const minS = ref(LIMITS[0].s)
const rows = ref([])
const error = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    rows.value = (await api.getMonthlyReport(month.value, minS.value)).rows
    error.value = ''
  } catch (e) {
    error.value = `불러오지 못했습니다: ${e.message}`
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([month, minS], load)

function dur(s) {
  const m = Math.floor(s / 60), h = Math.floor(m / 60), d = Math.floor(h / 24)
  if (d) return `${d}일 ${h % 24}시간`
  if (h) return `${h}시간 ${m % 60}분`
  return `${m}분`
}
const KIND_TAG = { 기기: 'tag-device', 생활: 'tag-urgent', 부재: 'tag-muted' }

/* 내려받기 — 엑셀이 한글을 깨뜨리지 않게 BOM 을 붙인다 */
function downloadCsv() {
  const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const head = ['세대', '구분', '시작', '끝', '지속', '사유 초안 (판정 라벨)', '복지사 확인']
  const lines = rows.value.map((r) => [
    `${r.home}호`, r.kind, r.start.replace('T', ' '),
    r.end ? r.end.replace('T', ' ') + (r.cut ? ' (판정 멈춤 — 이후 모름)' : '') : '진행 중',
    dur(r.duration_s), r.draft, r.notes.map((n) => `${n.at.replace('T', ' ')} ${n.status}: ${n.memo}`).join(' / '),
  ].map(q).join(','))
  const blob = new Blob(['﻿' + [head.map(q).join(','), ...lines].join('\r\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `월간보고_초안_${month.value}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <div class="bar">
    <label>달 <input v-model="month" type="month" :max="thisMonth" /></label>
    <label>기준
      <select v-model.number="minS">
        <option v-for="l in LIMITS" :key="l.s" :value="l.s">{{ l.label }}</option>
      </select>
    </label>
    <button class="btn sm ghost" :disabled="loading" @click="load">새로고침</button>
    <button class="btn sm primary" :disabled="!rows.length" @click="downloadCsv">CSV 내려받기</button>
  </div>
  <p class="note">
    사유는 판정이 붙인 <b>초안</b>입니다 — 확정은 복지사가 합니다. 오른쪽 칸은 그 기간 알림에 남긴 대응 메모입니다.
    서버는 전원이 나간 것과 통신만 끊긴 것을 가르지 못해 둘 다 '데이터 미수신'으로 적습니다.
  </p>
  <p v-if="error" class="msg">{{ error }}</p>
  <p v-else-if="!rows.length" class="empty">
    {{ loading ? '불러오는 중…' : `${month}에 기준 이상 이어진 구간이 없습니다.` }}
  </p>
  <div v-else class="wrap">
    <table class="grid">
      <thead>
        <tr><th>세대</th><th>구분</th><th>기간</th><th>지속</th><th>사유 초안 (판정 라벨)</th><th>복지사 확인</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.home + r.kind + r.start">
          <td class="home">{{ r.home }}호</td>
          <td><span class="tag" :class="KIND_TAG[r.kind]">{{ r.kind }}</span></td>
          <td class="when">
            {{ stampOf(r.start) }} ~ {{ r.end ? stampOf(r.end) : '진행 중' }}
            <div v-if="r.cut" class="muted cut" title="엔진이 멈춰 그 뒤 상태는 모릅니다">판정 멈춤 — 이후 모름</div>
          </td>
          <td class="when">{{ dur(r.duration_s) }}</td>
          <td>{{ r.draft }}</td>
          <td>
            <span v-if="!r.notes.length" class="muted">대응 메모 없음</span>
            <div v-for="n in r.notes" :key="n.at" class="memo">
              <span class="muted">{{ stampOf(n.at) }} {{ n.status }}</span> {{ n.memo }}
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem; margin-bottom: 0.7rem; font-size: 0.8rem; }
.bar input, .bar select {
  margin-left: 0.3rem; padding: 0.3rem 0.45rem; font: inherit;
  border: 1px solid var(--border-strong); border-radius: var(--radius-sm); background: var(--surface); color: var(--text);
}
.note { font-size: 0.76rem; color: var(--muted); margin-bottom: 0.8rem; line-height: 1.5; }
.msg { color: var(--urgent); font-size: 0.8rem; }
.empty { padding: 1.6rem 0; text-align: center; color: var(--muted); font-size: 0.83rem; }
.wrap { overflow-x: auto; }
.grid { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.grid th {
  text-align: left; font-weight: 600; font-size: 0.74rem; color: var(--muted); white-space: nowrap;
  padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); background: var(--surface-2);
}
.grid td { padding: 0.72rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: top; }
.home { font-weight: 700; white-space: nowrap; }
.when { white-space: nowrap; }
.muted { color: var(--muted); }
.memo + .memo { margin-top: 0.3rem; }
.cut { font-size: 0.72rem; margin-top: 0.15rem; }
</style>

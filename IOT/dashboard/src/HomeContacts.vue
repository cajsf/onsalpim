<script setup>
// 세대 상세의 보호자·담당자 전화. 저장된 번호만 걸고, 없으면 등록란을 연다.
import { computed, ref, watch } from 'vue'
import { api } from './api.js'

const props = defineProps({
  home: { type: String, required: true },
  editor: { type: Boolean, default: true },
})

const ROWS = [
  { role: 'guardian', label: '보호자' },
  { role: 'staff', label: '담당자' },
]

const book = ref({ home: props.home, guardian: null, staff: null })
const editing = ref(false)
const busy = ref(false)
const error = ref('')
const form = ref(blankForm())

const anyPhone = computed(() => ROWS.some((r) => book.value[r.role]?.phone))

function blankForm() {
  return { guardianName: '', guardianPhone: '', staffName: '', staffPhone: '' }
}

function tel(phone) {
  const digits = String(phone || '').replace(/\D/g, '')
  return digits ? `tel:${digits}` : ''
}

async function load() {
  error.value = ''
  try {
    book.value = await api.getContacts(props.home)
  } catch (e) {
    error.value = e.message
  }
}

function startEdit() {
  const g = book.value.guardian || {}
  const s = book.value.staff || {}
  form.value = {
    guardianName: g.name || '',
    guardianPhone: g.phone || '',
    staffName: s.name || '',
    staffPhone: s.phone || '',
  }
  editing.value = true
  error.value = ''
}

async function save() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  const r = await api.saveContacts(props.home, {
    guardian: { name: form.value.guardianName, phone: form.value.guardianPhone },
    staff: { name: form.value.staffName, phone: form.value.staffPhone },
  })
  busy.value = false
  if (!r.ok) {
    error.value = (r.errors || []).join(' ') || '저장하지 못했습니다.'
    return
  }
  book.value = r.contacts
  editing.value = false
}

watch(() => props.home, () => {
  editing.value = false
  form.value = blankForm()
  load()
}, { immediate: true })
</script>

<template>
  <section v-if="editor || anyPhone" class="contacts">
    <div class="head">
      <p class="title">연락</p>
      <button v-if="editor && !editing" type="button" class="btn ghost sm" @click="startEdit">
        {{ anyPhone ? '수정' : '연락처 등록' }}
      </button>
    </div>
    <p v-if="editor && !anyPhone && !editing" class="muted">등록된 보호자·담당자 번호가 없습니다.</p>
    <p v-if="error" class="err">{{ error }}</p>

    <div v-if="!editing" class="calls">
      <template v-for="row in ROWS" :key="row.role">
        <a v-if="book[row.role]?.phone" class="btn call" :href="tel(book[row.role].phone)">
          {{ book[row.role].name ? row.label + ' ' + book[row.role].name : row.label }}
          · {{ book[row.role].phone }}
        </a>
      </template>
    </div>

    <form v-else class="form" @submit.prevent="save">
      <div v-for="row in ROWS" :key="row.role" class="pair">
        <span class="role">{{ row.label }}</span>
        <input v-model="form[row.role + 'Name']" :placeholder="row.label + ' 이름'" maxlength="30" />
        <input v-model="form[row.role + 'Phone']" :placeholder="row.label + ' 전화'" inputmode="tel" maxlength="20" />
      </div>
      <p class="muted small">번호를 비우고 저장하면 그 연락처는 지워집니다.</p>
      <div class="acts">
        <button type="button" class="btn ghost sm" :disabled="busy" @click="editing = false">취소</button>
        <button type="submit" class="btn primary sm" :disabled="busy">{{ busy ? '저장 중…' : '저장' }}</button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.contacts { margin: 0.7rem 0 0.2rem; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; margin-bottom: 0.4rem; }
.title { font-size: 0.8rem; font-weight: 700; }
.muted { font-size: 0.78rem; color: var(--muted); }
.small { margin-top: 0.35rem; }
.err { color: var(--urgent); font-size: 0.78rem; margin-bottom: 0.35rem; }
.calls { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.call { text-decoration: none; color: var(--brand-dim); border-color: var(--brand); background: var(--brand-soft); }
.form { display: flex; flex-direction: column; gap: 0.45rem; }
.pair { display: grid; grid-template-columns: 52px 1fr 1fr; gap: 0.4rem; align-items: center; }
.role { font-size: 0.75rem; color: var(--muted); font-weight: 600; }
.pair input {
  min-width: 0; padding: 0.4rem 0.55rem; border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm); font: inherit; font-size: 0.8rem; color: var(--text); background: var(--surface);
}
.acts { display: flex; justify-content: flex-end; gap: 0.4rem; }
@media (max-width: 620px) {
  .pair { grid-template-columns: 1fr; }
}
</style>

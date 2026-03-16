<template>
  <div class="scheduler-panel">
    <div class="panel-header">
      <span class="panel-icon">⏱️</span>
      <span class="panel-title">Automated Data Feeds</span>
      <span class="badge" v-if="sources.length">{{ sources.length }}</span>
      <button class="btn-add" @click="showForm = !showForm">{{ showForm ? '✕' : '+ Add feed' }}</button>
    </div>

    <!-- Add form -->
    <transition name="fade">
      <div v-if="showForm" class="add-form">
        <div class="field-row">
          <div class="field">
            <label class="field-label">Feed name</label>
            <input v-model="form.name" class="text-input" placeholder="Reuters Energy Desk" />
          </div>
          <div class="field narrow">
            <label class="field-label">Interval (min)</label>
            <input v-model.number="form.interval_minutes" type="number" min="5" class="text-input" />
          </div>
          <div class="field narrow">
            <label class="field-label">Mode</label>
            <select v-model="form.mode" class="text-input">
              <option value="auto">Auto</option>
              <option value="basic">Basic</option>
              <option value="stealthy">Stealthy</option>
              <option value="dynamic">Dynamic</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label class="field-label">URLs <span class="muted">(one per line)</span></label>
          <textarea v-model="form.urlInput" class="url-textarea" rows="3"
            placeholder="https://reuters.com/technology&#10;https://ft.com/markets" />
        </div>
        <div class="form-actions">
          <button class="btn-primary" @click="createFeed" :disabled="creating || !form.name || !formUrls.length">
            {{ creating ? 'Creating…' : 'Create feed' }}
          </button>
          <span v-if="formError" class="form-error">{{ formError }}</span>
        </div>
      </div>
    </transition>

    <!-- Source list -->
    <div v-if="!sources.length && !loading" class="empty">
      No automated feeds configured. Add one above to keep data continuously fresh.
    </div>

    <div class="source-list">
      <div v-for="src in sources" :key="src.source_id" class="source-row">
        <div class="source-info">
          <div class="source-name">{{ src.name }}</div>
          <div class="source-meta">
            <span>Every {{ src.interval_minutes }}min</span>
            <span>·</span>
            <span>{{ src.urls.length }} URL{{ src.urls.length > 1 ? 's' : '' }}</span>
            <span v-if="src.last_run_at">·</span>
            <span v-if="src.last_run_at" :class="'status-' + src.last_run_status">
              Last: {{ relativeTime(src.last_run_at) }}
              {{ src.last_run_status === 'ok' ? `(${src.last_run_words?.toLocaleString()}w)` : `(${src.last_run_status})` }}
            </span>
          </div>
        </div>
        <div class="source-actions">
          <button class="btn-icon" @click="runNow(src.source_id)" title="Run now">▶</button>
          <label class="toggle-switch" :title="src.enabled ? 'Disable' : 'Enable'">
            <input type="checkbox" :checked="src.enabled" @change="toggle(src)" />
            <span class="slider" />
          </label>
          <button class="btn-icon danger" @click="remove(src.source_id)" title="Delete">✕</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listSources, createSource, toggleSource, deleteSource, runSourceNow } from '../api/scheduler'

const props = defineProps({
  projectId: { type: String, default: '' },
})

const sources = ref([])
const loading = ref(false)
const showForm = ref(false)
const creating = ref(false)
const formError = ref('')

const form = ref({ name: '', interval_minutes: 60, mode: 'auto', urlInput: '' })

const formUrls = computed(() =>
  form.value.urlInput.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'))
)

async function load() {
  loading.value = true
  try {
    const res = await listSources(props.projectId)
    sources.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function createFeed() {
  if (!props.projectId) { formError.value = 'No project selected'; return }
  creating.value = true
  formError.value = ''
  try {
    await createSource({
      project_id: props.projectId,
      name: form.value.name,
      urls: formUrls.value,
      mode: form.value.mode,
      interval_minutes: form.value.interval_minutes,
    })
    form.value = { name: '', interval_minutes: 60, mode: 'auto', urlInput: '' }
    showForm.value = false
    await load()
  } catch (err) {
    formError.value = err.message
  } finally {
    creating.value = false
  }
}

async function toggle(src) {
  await toggleSource(src.source_id, !src.enabled)
  await load()
}

async function remove(sourceId) {
  await deleteSource(sourceId)
  sources.value = sources.value.filter(s => s.source_id !== sourceId)
}

async function runNow(sourceId) {
  await runSourceNow(sourceId)
  setTimeout(load, 3000)
}

function relativeTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

onMounted(load)
</script>

<style scoped>
.scheduler-panel {
  background: #0f1117;
  border: 1px solid #1e2535;
  border-radius: 10px;
  padding: 16px 20px;
  color: #c9d1d9;
  font-size: 13px;
}

.panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.panel-icon { font-size: 16px; }
.panel-title { font-size: 14px; font-weight: 600; color: #e6edf3; flex: 1; }
.badge { background: #21262d; border: 1px solid #30363d; border-radius: 20px; padding: 1px 8px; font-size: 11px; }

.btn-add { padding: 4px 12px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; font-size: 12px; cursor: pointer; }
.btn-add:hover { border-color: #58a6ff; color: #58a6ff; }

.add-form { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.field-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.field { flex: 1; min-width: 120px; }
.field.narrow { flex: 0 0 100px; }
.field-label { display: block; font-size: 11px; font-weight: 600; color: #6e7681; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }
.text-input, .url-textarea, select.text-input {
  width: 100%;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 5px;
  color: #c9d1d9;
  font-size: 12px;
  padding: 5px 8px;
  box-sizing: border-box;
}
.url-textarea { font-family: monospace; resize: vertical; }
.text-input:focus, .url-textarea:focus, select.text-input:focus { outline: none; border-color: #58a6ff; }
.form-actions { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.form-error { color: #f85149; font-size: 12px; }
.muted { color: #6e7681; }

.empty { color: #6e7681; font-size: 12px; padding: 10px 0; text-align: center; }

.source-list { display: flex; flex-direction: column; gap: 8px; }
.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 7px;
  padding: 10px 14px;
  gap: 10px;
}

.source-info { flex: 1; min-width: 0; }
.source-name { font-size: 12px; font-weight: 600; color: #e6edf3; }
.source-meta { display: flex; gap: 6px; flex-wrap: wrap; font-size: 11px; color: #6e7681; margin-top: 2px; }
.status-ok    { color: #3fb950; }
.status-error { color: #f85149; }
.status-empty { color: #e3b341; }

.source-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.btn-icon { background: none; border: none; color: #6e7681; cursor: pointer; font-size: 14px; padding: 2px 5px; transition: color 0.15s; }
.btn-icon:hover { color: #e6edf3; }
.btn-icon.danger:hover { color: #f85149; }

/* Toggle switch */
.toggle-switch { position: relative; display: inline-block; width: 32px; height: 18px; cursor: pointer; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; inset: 0; background: #30363d; border-radius: 18px; transition: 0.2s; }
.slider::before { content: ''; position: absolute; width: 12px; height: 12px; left: 3px; top: 3px; background: #6e7681; border-radius: 50%; transition: 0.2s; }
.toggle-switch input:checked + .slider { background: #238636; }
.toggle-switch input:checked + .slider::before { transform: translateX(14px); background: #fff; }

.btn-primary { padding: 6px 14px; background: #1f6feb; color: #fff; border: none; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; }
.btn-primary:not(:disabled):hover { background: #388bfd; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

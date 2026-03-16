<template>
  <div class="template-selector">
    <div class="panel-header">
      <span class="panel-icon">📋</span>
      <span class="panel-title">Use-case Templates</span>
      <span class="panel-sub">pre-built simulation configs</span>
    </div>

    <div v-if="loading" class="loading">Loading templates…</div>

    <div v-else class="template-grid">
      <div
        v-for="t in templates"
        :key="t.id"
        class="template-card"
        :class="{ selected: selected === t.id }"
        @click="select(t)"
      >
        <span class="t-icon">{{ t.icon }}</span>
        <div class="t-body">
          <div class="t-name">{{ t.name }}</div>
          <div class="t-use">{{ t.use_case }}</div>
        </div>
      </div>
    </div>

    <!-- Detail panel -->
    <transition name="fade">
      <div v-if="detail" class="detail-panel">
        <div class="detail-header">
          <span>{{ detail.icon }} {{ detail.name }}</span>
          <button class="btn-close" @click="detail = null; selected = null">✕</button>
        </div>

        <p class="detail-desc">{{ detail.description }}</p>

        <div class="detail-meta">
          <span>👥 {{ detail.suggested_agent_count?.toLocaleString() }} agents</span>
          <span>🔄 {{ detail.suggested_rounds }} rounds</span>
          <span>📡 {{ detail.suggested_platform }}</span>
        </div>

        <div class="detail-section">
          <div class="section-label">Key metrics</div>
          <ul class="metric-list">
            <li v-for="m in detail.key_metrics" :key="m">{{ m }}</li>
          </ul>
        </div>

        <!-- Schedule option -->
        <div v-if="detail.suggested_urls?.length" class="detail-section">
          <label class="toggle-label">
            <input type="checkbox" v-model="createSchedule" />
            <span>Auto-schedule data feed</span>
            <span class="muted">(scrape {{ detail.suggested_urls.length }} source{{ detail.suggested_urls.length > 1 ? 's' : '' }} every {{ detail.scrape_interval_minutes }}min)</span>
          </label>
          <div class="url-chips">
            <span v-for="u in detail.suggested_urls" :key="u" class="chip">{{ domainOf(u) }}</span>
          </div>
        </div>

        <div class="apply-row">
          <button class="btn-primary" @click="apply" :disabled="applying || !projectId">
            {{ applying ? 'Applying…' : 'Apply to project' }}
          </button>
          <span v-if="!projectId" class="muted">Create a project first</span>
        </div>

        <div v-if="feedback" class="feedback" :class="feedbackType">{{ feedback }}</div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listTemplates, getTemplate, applyTemplate } from '../api/templates'

const props = defineProps({
  projectId: { type: String, default: '' },
})
const emit = defineEmits(['applied'])

const templates = ref([])
const loading = ref(false)
const selected = ref(null)
const detail = ref(null)
const createSchedule = ref(false)
const applying = ref(false)
const feedback = ref('')
const feedbackType = ref('info')

async function load() {
  loading.value = true
  try {
    const res = await listTemplates()
    templates.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function select(t) {
  selected.value = t.id
  feedback.value = ''
  const res = await getTemplate(t.id)
  detail.value = res.data
  createSchedule.value = false
}

async function apply() {
  if (!props.projectId || !detail.value) return
  applying.value = true
  feedback.value = ''
  try {
    const res = await applyTemplate(detail.value.id, props.projectId, {
      createSchedule: createSchedule.value,
      intervalMinutes: detail.value.scrape_interval_minutes,
    })
    const d = res.data
    feedback.value = `Template applied. Simulation requirement set.${d.scheduled_source ? ' Data feed scheduled.' : ''}`
    feedbackType.value = 'success'
    emit('applied', d)
  } catch (err) {
    feedback.value = `Failed: ${err.message}`
    feedbackType.value = 'error'
  } finally {
    applying.value = false
  }
}

function domainOf(url) {
  try { return new URL(url).hostname } catch { return url }
}

onMounted(load)
</script>

<style scoped>
.template-selector {
  background: #0f1117;
  border: 1px solid #1e2535;
  border-radius: 10px;
  padding: 18px 22px;
  color: #c9d1d9;
  font-size: 13px;
}

.panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.panel-icon   { font-size: 16px; }
.panel-title  { font-size: 14px; font-weight: 600; color: #e6edf3; }
.panel-sub    { font-size: 11px; color: #6e7681; }

.loading { color: #6e7681; font-size: 12px; }

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.template-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.template-card:hover   { border-color: #58a6ff; background: #1a2233; }
.template-card.selected { border-color: #1f6feb; background: #1a2233; }

.t-icon { font-size: 20px; line-height: 1; flex-shrink: 0; margin-top: 1px; }
.t-name { font-size: 12px; font-weight: 600; color: #e6edf3; line-height: 1.3; }
.t-use  { font-size: 11px; color: #6e7681; margin-top: 2px; line-height: 1.3; }

/* Detail panel */
.detail-panel {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px 18px;
  margin-top: 4px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
  margin-bottom: 10px;
}

.btn-close {
  background: none;
  border: none;
  color: #6e7681;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.btn-close:hover { color: #e6edf3; }

.detail-desc { color: #8b949e; font-size: 12px; line-height: 1.5; margin-bottom: 12px; }

.detail-meta {
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: #58a6ff;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.detail-section { margin-bottom: 12px; }
.section-label  { font-size: 11px; font-weight: 600; color: #6e7681; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }

.metric-list { margin: 0; padding-left: 16px; color: #c9d1d9; font-size: 12px; line-height: 1.7; }

.toggle-label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 12px; }
.toggle-label input { cursor: pointer; }
.muted { color: #6e7681; }

.url-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.chip { background: #0d1117; border: 1px solid #30363d; border-radius: 20px; padding: 2px 10px; font-size: 11px; color: #79c0ff; font-family: monospace; }

.apply-row { display: flex; align-items: center; gap: 10px; margin-top: 14px; }

.btn-primary { padding: 7px 18px; background: #1f6feb; color: #fff; border: none; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; }
.btn-primary:not(:disabled):hover { background: #388bfd; }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.feedback { margin-top: 10px; padding: 7px 10px; border-radius: 5px; font-size: 12px; }
.feedback.success { background: #0f2d1a; color: #3fb950; }
.feedback.error   { background: #2d0f0f; color: #f85149; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

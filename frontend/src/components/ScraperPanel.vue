<template>
  <div class="scraper-panel">
    <div class="panel-header">
      <span class="panel-icon">🌐</span>
      <span class="panel-title">Web Data Ingestion</span>
      <span class="panel-sub">powered by Scrapling</span>
    </div>

    <p class="description">
      Feed live web content directly into the knowledge graph. Supports news sites,
      government publications, company reports, and JS-heavy pages.
    </p>

    <!-- Mode selector -->
    <div class="field-group">
      <label class="field-label">Fetch mode</label>
      <div class="mode-tabs">
        <button
          v-for="m in modes"
          :key="m.value"
          class="mode-tab"
          :class="{ active: mode === m.value }"
          @click="mode = m.value"
          :title="m.hint"
        >
          {{ m.label }}
        </button>
      </div>
      <p class="field-hint">{{ currentModeHint }}</p>
    </div>

    <!-- URL input -->
    <div class="field-group">
      <label class="field-label">URLs <span class="muted">(one per line, max 10)</span></label>
      <textarea
        v-model="urlInput"
        class="url-textarea"
        placeholder="https://reuters.com/article/...&#10;https://ec.europa.eu/report/...&#10;https://company.com/investor-relations"
        rows="4"
        :disabled="loading"
      />
    </div>

    <!-- Crawl options -->
    <div class="field-group inline">
      <label class="toggle-label">
        <input type="checkbox" v-model="doCrawl" :disabled="loading || urlList.length !== 1" />
        <span>Crawl domain</span>
        <span class="muted">(follow links, single URL only)</span>
      </label>
      <div v-if="doCrawl" class="inline-field">
        <label class="field-label">Max pages</label>
        <input v-model.number="maxPages" type="number" min="1" max="100" class="number-input" />
      </div>
    </div>

    <!-- Action buttons -->
    <div class="action-row">
      <button class="btn-secondary" @click="preview" :disabled="loading || !urlList.length">
        {{ loading && action === 'preview' ? 'Scraping…' : 'Preview text' }}
      </button>
      <button
        v-if="projectId"
        class="btn-primary"
        @click="ingest"
        :disabled="loading || !urlList.length"
      >
        {{ loading && action === 'ingest' ? 'Ingesting…' : 'Add to project' }}
      </button>
    </div>

    <!-- Progress -->
    <div v-if="loading" class="progress-bar-wrap">
      <div class="progress-bar" :style="{ width: progress + '%' }" />
      <span class="progress-label">{{ progressMsg }}</span>
    </div>

    <!-- Preview result -->
    <div v-if="previewData" class="result-card">
      <div class="result-meta">
        <span>{{ previewData.pages_scraped }} pages</span>
        <span>·</span>
        <span>{{ previewData.total_words.toLocaleString() }} words</span>
      </div>
      <pre class="text-preview">{{ previewData.preview }}</pre>
      <div class="page-list">
        <div
          v-for="(p, i) in previewData.pages"
          :key="i"
          class="page-row"
          :class="{ failed: !p.success }"
        >
          <span class="page-status">{{ p.success ? '✓' : '✗' }}</span>
          <span class="page-url">{{ p.url }}</span>
          <span class="page-words">{{ p.word_count?.toLocaleString() }} w</span>
        </div>
      </div>
    </div>

    <!-- Feedback -->
    <div v-if="feedback" class="feedback" :class="feedbackType">{{ feedback }}</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { fetchUrls, ingestToProject, crawlDomain, getScraperTask } from '../api/scraper'

const props = defineProps({
  /** Pass project_id to enable "Add to project" button */
  projectId: { type: String, default: '' },
})

const emit = defineEmits(['ingested'])

const modes = [
  { value: 'auto',     label: 'Auto',     hint: 'Automatically picks the right mode per domain' },
  { value: 'basic',    label: 'Basic',    hint: 'Fast HTTP with TLS fingerprint spoofing' },
  { value: 'stealthy', label: 'Stealthy', hint: 'Bypass Cloudflare and anti-bot systems' },
  { value: 'dynamic',  label: 'Dynamic',  hint: 'Full browser (Playwright) for JS-heavy sites' },
]

const mode = ref('auto')
const urlInput = ref('')
const doCrawl = ref(false)
const maxPages = ref(20)
const loading = ref(false)
const action = ref('')
const progress = ref(0)
const progressMsg = ref('')
const previewData = ref(null)
const feedback = ref('')
const feedbackType = ref('info')

const urlList = computed(() =>
  urlInput.value
    .split('\n')
    .map(u => u.trim())
    .filter(u => u.startsWith('http'))
    .slice(0, 10)
)

const currentModeHint = computed(
  () => modes.find(m => m.value === mode.value)?.hint || ''
)

function setFeedback(msg, type = 'info') {
  feedback.value = msg
  feedbackType.value = type
}

async function preview() {
  if (!urlList.value.length) return
  loading.value = true
  action.value = 'preview'
  previewData.value = null
  feedback.value = ''
  progress.value = 10
  progressMsg.value = 'Fetching pages…'

  try {
    const res = await fetchUrls(urlList.value, mode.value)
    previewData.value = res.data
    progress.value = 100
    progressMsg.value = 'Done'
  } catch (err) {
    setFeedback(`Fetch failed: ${err.message}`, 'error')
  } finally {
    loading.value = false
    progress.value = 0
  }
}

async function ingest() {
  if (!urlList.value.length || !props.projectId) return
  loading.value = true
  action.value = 'ingest'
  feedback.value = ''
  progress.value = 5
  progressMsg.value = 'Starting…'

  try {
    if (doCrawl.value && urlList.value.length === 1) {
      // async crawl via task polling
      const startRes = await crawlDomain(urlList.value[0], maxPages.value, mode.value)
      const taskId = startRes.data?.task_id
      if (!taskId) throw new Error('No task_id returned')

      await pollTask(taskId)
      // after crawl completes, ingest result
      const taskRes = await getScraperTask(taskId)
      const combinedText = taskRes.data?.result?.combined_text || ''
      if (!combinedText) throw new Error('Crawl returned no text')

      // direct ingest with crawled text (reuse fetch ingest endpoint)
      const ingestRes = await ingestToProject(props.projectId, urlList.value, {
        crawl: true, maxPages: maxPages.value, mode: mode.value,
      })
      handleIngestResult(ingestRes)
    } else {
      const res = await ingestToProject(props.projectId, urlList.value, {
        mode: mode.value,
      })
      handleIngestResult(res)
    }
  } catch (err) {
    setFeedback(`Ingest failed: ${err.message}`, 'error')
  } finally {
    loading.value = false
    progress.value = 0
  }
}

function handleIngestResult(res) {
  const d = res.data
  setFeedback(
    `Added ${d.pages_added} pages (${d.words_added?.toLocaleString()} words) to project. ` +
    `Total corpus: ${d.total_text_length?.toLocaleString()} chars. Ready to build graph.`,
    'success'
  )
  progress.value = 100
  emit('ingested', d)
}

async function pollTask(taskId) {
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 2000))
    const res = await getScraperTask(taskId)
    const task = res.data
    progress.value = task.progress || 0
    progressMsg.value = task.message || 'Crawling…'
    if (task.status === 'completed') return
    if (task.status === 'failed') throw new Error(task.error || 'Crawl failed')
  }
  throw new Error('Crawl timed out')
}
</script>

<style scoped>
.scraper-panel {
  background: #0f1117;
  border: 1px solid #1e2535;
  border-radius: 10px;
  padding: 18px 22px;
  color: #c9d1d9;
  font-size: 13px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.panel-icon  { font-size: 16px; }
.panel-title { font-size: 14px; font-weight: 600; color: #e6edf3; }
.panel-sub   { font-size: 11px; color: #6e7681; }

.description {
  color: #8b949e;
  line-height: 1.5;
  margin-bottom: 14px;
  font-size: 12px;
}

.field-group { margin-bottom: 14px; }
.field-group.inline { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }

.field-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}

.field-hint { font-size: 11px; color: #6e7681; margin-top: 4px; }

.mode-tabs { display: flex; gap: 4px; }

.mode-tab {
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid #30363d;
  background: #161b22;
  color: #8b949e;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-tab:hover  { border-color: #58a6ff; color: #58a6ff; }
.mode-tab.active { background: #1f3651; border-color: #58a6ff; color: #58a6ff; }

.url-textarea {
  width: 100%;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #c9d1d9;
  font-family: monospace;
  font-size: 12px;
  padding: 8px 10px;
  resize: vertical;
  box-sizing: border-box;
  transition: border-color 0.15s;
}
.url-textarea:focus { outline: none; border-color: #58a6ff; }
.url-textarea:disabled { opacity: 0.5; }

.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
}
.toggle-label input { cursor: pointer; }

.inline-field { display: flex; align-items: center; gap: 6px; }

.number-input {
  width: 60px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 4px;
  color: #c9d1d9;
  padding: 3px 6px;
  font-size: 12px;
  text-align: center;
}

.muted { color: #6e7681; }

.action-row { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }

.btn-secondary, .btn-primary {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: opacity 0.15s;
}
.btn-secondary:disabled, .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-secondary { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; }
.btn-secondary:not(:disabled):hover { background: #30363d; }
.btn-primary { background: #1f6feb; color: #fff; }
.btn-primary:not(:disabled):hover { background: #388bfd; }

.progress-bar-wrap {
  margin-top: 12px;
  background: #161b22;
  border-radius: 4px;
  height: 6px;
  position: relative;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #1f6feb, #58a6ff);
  border-radius: 4px;
  transition: width 0.3s ease;
}
.progress-label {
  font-size: 11px;
  color: #6e7681;
  margin-top: 4px;
  display: block;
}

.result-card {
  margin-top: 14px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 8px;
  overflow: hidden;
}

.result-meta {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: #161b22;
  font-size: 12px;
  color: #8b949e;
  border-bottom: 1px solid #21262d;
}

.text-preview {
  padding: 10px 12px;
  font-size: 11px;
  color: #8b949e;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
  border-bottom: 1px solid #21262d;
  margin: 0;
}

.page-list { padding: 8px 12px; display: flex; flex-direction: column; gap: 4px; }

.page-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.page-row.failed { opacity: 0.5; }
.page-status { width: 14px; flex-shrink: 0; }
.page-url { flex: 1; color: #58a6ff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-words { color: #6e7681; flex-shrink: 0; }

.feedback {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}
.feedback.success { background: #0f2d1a; color: #3fb950; }
.feedback.error   { background: #2d0f0f; color: #f85149; }
.feedback.info    { background: #161b22; color: #8b949e; }
</style>

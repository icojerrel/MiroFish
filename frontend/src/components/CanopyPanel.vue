<template>
  <div class="canopy-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span class="panel-icon">🌿</span>
        <span>Canopy Workspace</span>
        <span v-if="status.enabled" class="badge" :class="status.connected ? 'connected' : 'disconnected'">
          {{ status.connected ? 'Connected' : 'Offline' }}
        </span>
        <span v-else class="badge disabled">Not configured</span>
      </div>
      <button class="btn-icon" @click="refresh" :disabled="loading" title="Refresh">
        <span :class="{ spinning: loading }">↻</span>
      </button>
    </div>

    <!-- Not configured hint -->
    <div v-if="!status.enabled" class="hint-card">
      <p>
        Add <code>CANOPY_BASE_URL</code>, <code>CANOPY_API_KEY</code>, and
        <code>CANOPY_CHANNEL_ID</code> to your <code>.env</code> file to enable
        encrypted team collaboration via
        <a href="https://github.com/icojerrel/Canopy" target="_blank" rel="noopener">Canopy</a>.
      </p>
      <pre class="env-snippet">CANOPY_BASE_URL=http://localhost:7770
CANOPY_API_KEY=your_api_key_here
CANOPY_CHANNEL_ID=your_channel_id_here</pre>
    </div>

    <!-- Connected info -->
    <div v-else class="info-grid">
      <div class="info-row">
        <span class="info-label">Instance</span>
        <span class="info-value mono">{{ status.base_url }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Channel</span>
        <span class="info-value mono">{{ status.channel_id || '—' }}</span>
      </div>
      <div v-if="status.info" class="info-row">
        <span class="info-label">Version</span>
        <span class="info-value">{{ status.info.version || '—' }}</span>
      </div>
      <div v-if="!status.connected && status.error" class="error-row">
        {{ status.error }}
      </div>
    </div>

    <!-- Actions -->
    <div v-if="status.enabled" class="action-row">
      <button class="btn-secondary" @click="sendTest" :disabled="testLoading || !status.connected">
        {{ testLoading ? 'Sending…' : 'Send test message' }}
      </button>
      <button
        v-if="reportId"
        class="btn-primary"
        @click="pushReport"
        :disabled="pushLoading || !status.connected"
      >
        {{ pushLoading ? 'Pushing…' : 'Push report to Canopy' }}
      </button>
    </div>

    <!-- Feedback -->
    <div v-if="feedback" class="feedback" :class="feedbackType">
      {{ feedback }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCanopyStatus, testCanopyConnection, pushReportToCanopy } from '../api/canopy'

const props = defineProps({
  /** Pass a completed report_id to enable the "Push report" button */
  reportId: { type: String, default: '' },
})

const status = ref({
  enabled: false,
  connected: false,
  base_url: '',
  channel_id: '',
  info: null,
  error: null,
})
const loading = ref(false)
const testLoading = ref(false)
const pushLoading = ref(false)
const feedback = ref('')
const feedbackType = ref('info')

async function refresh() {
  loading.value = true
  feedback.value = ''
  try {
    const res = await getCanopyStatus()
    status.value = res.data || {}
  } catch (err) {
    feedback.value = `Status check failed: ${err.message}`
    feedbackType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function sendTest() {
  testLoading.value = true
  feedback.value = ''
  try {
    await testCanopyConnection()
    feedback.value = 'Test message sent to Canopy ✓'
    feedbackType.value = 'success'
  } catch (err) {
    feedback.value = `Test failed: ${err.message}`
    feedbackType.value = 'error'
  } finally {
    testLoading.value = false
  }
}

async function pushReport() {
  if (!props.reportId) return
  pushLoading.value = true
  feedback.value = ''
  try {
    await pushReportToCanopy(props.reportId)
    feedback.value = 'Report pushed to Canopy ✓'
    feedbackType.value = 'success'
  } catch (err) {
    feedback.value = `Push failed: ${err.message}`
    feedbackType.value = 'error'
  } finally {
    pushLoading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.canopy-panel {
  background: #0f1117;
  border: 1px solid #1e2535;
  border-radius: 10px;
  padding: 16px 20px;
  font-size: 13px;
  color: #c9d1d9;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #e6edf3;
}

.panel-icon { font-size: 16px; }

.badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 20px;
}

.badge.connected    { background: #1a3326; color: #3fb950; border: 1px solid #238636; }
.badge.disconnected { background: #3b1a1a; color: #f85149; border: 1px solid #6e2020; }
.badge.disabled     { background: #1c2128; color: #6e7681; border: 1px solid #30363d; }

.btn-icon {
  background: none;
  border: none;
  color: #6e7681;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 2px 4px;
  transition: color 0.2s;
}
.btn-icon:hover { color: #e6edf3; }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.hint-card {
  background: #161b22;
  border: 1px dashed #30363d;
  border-radius: 6px;
  padding: 12px 14px;
  color: #8b949e;
  line-height: 1.6;
}

.hint-card a { color: #58a6ff; text-decoration: none; }
.hint-card a:hover { text-decoration: underline; }

.env-snippet {
  margin-top: 8px;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 11px;
  color: #79c0ff;
  white-space: pre;
  overflow-x: auto;
}

.info-grid { display: flex; flex-direction: column; gap: 6px; }

.info-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
}

.info-label {
  width: 70px;
  flex-shrink: 0;
  color: #6e7681;
}

.info-value { color: #c9d1d9; }
.mono { font-family: monospace; font-size: 12px; }

.error-row {
  color: #f85149;
  font-size: 12px;
  margin-top: 2px;
}

.action-row {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.btn-secondary, .btn-primary {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: opacity 0.15s;
}

.btn-secondary:disabled, .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-secondary {
  background: #21262d;
  color: #c9d1d9;
  border: 1px solid #30363d;
}
.btn-secondary:not(:disabled):hover { background: #30363d; }

.btn-primary {
  background: #238636;
  color: #fff;
}
.btn-primary:not(:disabled):hover { background: #2ea043; }

.feedback {
  margin-top: 10px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 5px;
}

.feedback.success { background: #0f2d1a; color: #3fb950; }
.feedback.error   { background: #2d0f0f; color: #f85149; }
.feedback.info    { background: #161b22; color: #8b949e; }
</style>

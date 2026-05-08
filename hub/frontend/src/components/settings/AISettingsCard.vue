<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const form = reactive({
  provider: 'cli' as 'cli' | 'api',
  model:    '',
  api_key:  '',
})
const apiKeyAlreadySet = ref(false)
const showApiKey = ref(false)

const isApi = computed(() => form.provider === 'api')

const requirement = ref('')
const output = ref('')
const generating = ref(false)
const lastProvider = ref('')

async function loadSettings() {
  try {
    const cfg = await apiCall<{ provider: string; model: string; api_key_set: boolean }>('/api/config/ai')
    form.provider = (cfg.provider as 'cli' | 'api') || 'cli'
    form.model    = cfg.model || ''
    apiKeyAlreadySet.value = cfg.api_key_set
  } catch { /* apiCall toasted */ }
}

async function saveSettings() {
  const payload: Record<string, unknown> = { provider: form.provider, model: form.model }
  // Only send api_key if user typed one — empty means "keep existing"
  if (form.api_key.trim()) payload.api_key = form.api_key.trim()
  try {
    await apiCall('/api/config/ai/save', { body: payload })
    toast.show('💾 AI settings saved', 'ok')
    form.api_key = ''
    await loadSettings()
  } catch { /* apiCall toasted */ }
}

async function generate() {
  if (!requirement.value.trim()) {
    toast.show('Paste requirement ก่อน', 'warn')
    return
  }
  generating.value = true
  output.value = ''
  try {
    const d = await apiCall<{ provider: string; model: string; output: string }>(
      '/api/ai/generate-test-plan',
      { silent: true, body: { requirement: requirement.value.trim() } }
    )
    output.value = d.output
    lastProvider.value = `${d.provider}${d.model && d.model !== 'default' ? ' (' + d.model + ')' : ''}`
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'failed'
    toast.show(`Generation failed: ${msg}`, 'err')
  } finally {
    generating.value = false
  }
}

function copyOutput() {
  if (!output.value) return
  navigator.clipboard.writeText(output.value)
    .then(() => toast.show('📋 คัดลอกแล้ว', 'ok'))
    .catch(() => toast.show('คัดลอกไม่สำเร็จ', 'err'))
}

onMounted(loadSettings)
</script>

<template>
  <div class="card">
    <div class="card-title">🤖 AI Test Plan Generator</div>
    <p class="hint">
      ใช้ Claude ช่วย draft test scenarios จาก requirement — เลือก provider ตามที่ตั้งไว้
    </p>

    <div class="form-grid">
      <div class="field">
        <label>Provider</label>
        <select v-model="form.provider">
          <option value="cli">Claude CLI (subscription — ไม่มี API cost)</option>
          <option value="api">Anthropic API (ต้อง API key + คิดค่า tokens)</option>
        </select>
      </div>
      <div class="field">
        <label>Model (optional)</label>
        <input v-model="form.model" placeholder="claude-opus-4-7" />
      </div>
    </div>

    <div v-if="isApi" class="field" style="margin-top:10px">
      <label style="display:flex;align-items:center;gap:6px">
        API Key
        <span v-if="apiKeyAlreadySet" class="key-saved">— ✓ saved (เว้นว่างเพื่อใช้ค่าเดิม)</span>
        <button type="button" class="reveal-btn" @click="showApiKey = !showApiKey" tabindex="-1"
                :title="showApiKey ? 'Hide key' : 'Show key'">
          {{ showApiKey ? '🙈' : '👁' }}
        </button>
      </label>
      <input v-model="form.api_key" :type="showApiKey ? 'text' : 'password'" placeholder="sk-ant-..." />
    </div>

    <button class="btn btn-primary" @click="saveSettings" style="margin-top:12px">💾 Save AI Settings</button>

    <hr class="divider">

    <div class="card-title" style="margin-bottom:8px">✨ Generate Test Plan</div>
    <p class="hint">Paste requirement (markdown / plain text) แล้วกด Generate</p>
    <textarea v-model="requirement" rows="6"
              placeholder="Paste requirement document here..."
              class="req-area" />
    <div class="gen-row">
      <button class="btn btn-primary" @click="generate" :disabled="generating">
        <span v-if="generating">⏳ generating…</span>
        <span v-else>✨ Generate</span>
      </button>
      <span v-if="lastProvider" class="provider-tag">via {{ lastProvider }}</span>
    </div>

    <div v-if="output" class="output-wrap">
      <div class="output-header">
        <span class="output-label">Output</span>
        <button class="btn btn-sm" @click="copyOutput">📋 Copy</button>
      </div>
      <pre class="output">{{ output }}</pre>
    </div>
  </div>
</template>

<style scoped>
.hint { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 720px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field input, .field select { width: 100%; }
.divider { border: none; border-top: 1px solid var(--border-soft); margin: 18px 0; }
.key-saved {
  color: var(--success);
  font-weight: 400;
  font-size: 11.5px;
}
[data-theme="dark"] .key-saved { color: var(--success); }
.reveal-btn {
  background: none;
  border: none;
  font-size: 13px;
  cursor: pointer;
  padding: 0 2px;
  color: var(--muted);
  margin-left: auto;
  font-family: inherit;
}
.reveal-btn:hover { color: var(--text); }

.req-area {
  width: 100%;
  max-width: 920px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: 13px;
  color: var(--text);
  background: var(--card);
  resize: vertical;
  box-sizing: border-box;
}
.gen-row { display: flex; gap: 12px; align-items: center; margin-top: 10px; }
.provider-tag { color: var(--success); font-size: 12px; }
[data-theme="dark"] .provider-tag { color: var(--success); }

.output-wrap { margin-top: 16px; }
.output-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.output-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: .5px;
}
.output {
  background: #0d1117;  /* stylelint-disable-line color-no-hex */
  color: #c9d1d9;  /* stylelint-disable-line color-no-hex */
  padding: 14px;
  border-radius: var(--radius-sm);
  font-family: 'Cascadia Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 480px;
  overflow-y: auto;
  white-space: pre-wrap;
}
.btn-sm { padding: 3px 9px; font-size: 11px; }
</style>

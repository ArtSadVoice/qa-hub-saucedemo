<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'

interface Recipient { name: string; email: string }
interface EmailConfig {
  provider: 'smtp' | 'resend'
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_pass: string
  resend_api_key: string
  resend_from: string
  sender_name: string
  subject_template: string
  to: Recipient[]
  cc: Recipient[]
}

const toast = useToast()
const cfg = reactive<EmailConfig>({
  provider: 'smtp',
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_pass: '',
  resend_api_key: '',
  resend_from: '',
  sender_name: '',
  subject_template: '',
  to: [],
  cc: [],
})

const newTo = reactive({ name: '', email: '' })
const newCc = reactive({ name: '', email: '' })
const testResult = ref('')
const showSmtpPass = ref(false)
const showResendKey = ref(false)

const isResend = computed(() => cfg.provider === 'resend')

async function load() {
  try {
    const e = await apiCall<EmailConfig>('/api/config/email')
    Object.assign(cfg, e)
  } catch { /* apiCall toasted */ }
}

async function save() {
  try {
    await apiCall('/api/config/email/save', { body: cfg })
    toast.show('💾 Email settings saved (synced to all projects)', 'ok')
  } catch { /* apiCall toasted */ }
}

async function testConnection() {
  testResult.value = '⏳ testing…'
  try {
    const d = await apiCall<{ ok: boolean; detail?: string; error?: string }>(
      '/api/config/email/test',
      { silent: true, body: cfg }
    )
    testResult.value = d.ok ? `✅ ${d.detail || 'OK'}` : `❌ ${d.error || 'Failed'}`
  } catch (e: unknown) {
    testResult.value = `❌ ${e instanceof Error ? e.message : 'failed'}`
  }
}

function addRecipient(kind: 'to' | 'cc') {
  const src = kind === 'to' ? newTo : newCc
  const email = src.email.trim().toLowerCase()
  if (!email) return
  // Reject duplicates so the same address can't be added twice
  if (cfg[kind].some((r) => r.email.toLowerCase() === email)) {
    toast.show(`${email} อยู่ใน ${kind === 'to' ? 'To' : 'CC'} แล้ว`, 'warn')
    return
  }
  // Minimal email shape check — server still validates on send
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    toast.show('รูปแบบ email ไม่ถูกต้อง', 'warn')
    return
  }
  cfg[kind].push({ name: src.name.trim(), email: src.email.trim() })
  src.name = ''
  src.email = ''
}

function removeRecipient(kind: 'to' | 'cc', idx: number) {
  cfg[kind].splice(idx, 1)
}

// ── Bulk-paste parser ───────────────────────────────────────────────────
// Accepts mixed input separated by comma / semicolon / newline:
//   email@x.com
//   Name <email@x.com>
//   "Name" <email@x.com>
//   Name1 <e1>; Name2 <e2>, e3@x.com
const bulkInput = ref<{ to: string; cc: string }>({ to: '', cc: '' })

interface ParsedRecipient { name: string; email: string }
function parseBulkRecipients(raw: string): ParsedRecipient[] {
  const out: ParsedRecipient[] = []
  // Split on , ; or newlines; tolerate adjacent commas/spaces
  const tokens = raw.split(/[,;\n\r]+/).map((s) => s.trim()).filter(Boolean)
  for (const t of tokens) {
    // Match "Name <email>" form first; fall back to bare email
    const m = t.match(/^"?([^"<]+?)"?\s*<([^>]+)>$/)
    if (m) {
      out.push({ name: m[1].trim(), email: m[2].trim() })
    } else {
      out.push({ name: '', email: t.trim() })
    }
  }
  return out
}

function bulkAdd(kind: 'to' | 'cc') {
  const raw = bulkInput.value[kind]
  if (!raw.trim()) return
  const parsed = parseBulkRecipients(raw)
  const existing = new Set(cfg[kind].map((r) => r.email.toLowerCase()))
  let added = 0, dupes = 0, invalid = 0
  for (const r of parsed) {
    const email = r.email.toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { invalid++; continue }
    if (existing.has(email)) { dupes++; continue }
    cfg[kind].push(r)
    existing.add(email)
    added++
  }
  // Compose a single toast summarising the result
  const parts: string[] = []
  if (added)   parts.push(`✅ added ${added}`)
  if (dupes)   parts.push(`↺ ${dupes} duplicate`)
  if (invalid) parts.push(`✗ ${invalid} invalid`)
  toast.show(parts.join(' · ') || 'ไม่มีรายการที่ใช้ได้', added ? 'ok' : 'warn')
  if (added) bulkInput.value[kind] = ''
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="card-title">📧 Email Settings</div>
    <p class="hint">Email provider + ผู้รับ report — บันทึกแล้ว sync ไปทุก project</p>

    <!-- Provider toggle -->
    <div class="prov-toggle">
      <button class="btn" :class="{ active: cfg.provider === 'smtp' }" @click="cfg.provider = 'smtp'">📮 SMTP</button>
      <button class="btn" :class="{ active: cfg.provider === 'resend' }" @click="cfg.provider = 'resend'">⚡ Resend API</button>
    </div>

    <!-- SMTP fields -->
    <div v-if="!isResend" class="form-grid">
      <div class="field"><label>SMTP Host</label><input v-model="cfg.smtp_host" placeholder="smtp.gmail.com" /></div>
      <div class="field"><label>SMTP Port</label><input v-model.number="cfg.smtp_port" type="number" /></div>
      <div class="field"><label>Username (Email)</label><input v-model="cfg.smtp_user" type="email" /></div>
      <div class="field">
        <label style="display:flex;align-items:center;gap:6px">
          Password
          <span class="dim">— เก็บใน HUB_SMTP_PASS env var แทนได้</span>
          <button type="button" class="reveal-btn" @click="showSmtpPass = !showSmtpPass" tabindex="-1"
                  :title="showSmtpPass ? 'Hide password' : 'Show password'">
            {{ showSmtpPass ? '🙈' : '👁' }}
          </button>
        </label>
        <input v-model="cfg.smtp_pass" :type="showSmtpPass ? 'text' : 'password'" placeholder="xxxx xxxx xxxx xxxx" />
      </div>
    </div>

    <!-- Resend fields -->
    <div v-else class="form-grid">
      <div class="field">
        <label style="display:flex;align-items:center;gap:6px">
          Resend API Key
          <button type="button" class="reveal-btn" @click="showResendKey = !showResendKey" tabindex="-1"
                  :title="showResendKey ? 'Hide key' : 'Show key'">
            {{ showResendKey ? '🙈' : '👁' }}
          </button>
        </label>
        <input v-model="cfg.resend_api_key" :type="showResendKey ? 'text' : 'password'" placeholder="re_..." />
      </div>
      <div class="field"><label>From Address</label><input v-model="cfg.resend_from" placeholder="QA Hub <noreply@yourdomain.com>" /></div>
      <div class="hint" style="grid-column: span 2; margin-top:-4px">
        ฟรี 3,000 emails/month ที่ <a href="https://resend.com" target="_blank" rel="noopener noreferrer" class="ext-link">resend.com</a>
      </div>
    </div>

    <!-- Common fields -->
    <div class="form-grid" style="margin-top:12px">
      <div class="field"><label>Sender Name</label><input v-model="cfg.sender_name" placeholder="F180 QA Hub" /></div>
      <div class="field"><label>Subject Template</label><input v-model="cfg.subject_template" placeholder="[{result}] UAT Report" /></div>
    </div>

    <!-- Recipients -->
    <div class="recipients" style="margin-top:14px">
      <label>📨 To (ผู้รับ report)</label>
      <div v-for="(r, i) in cfg.to" :key="'to-'+i" class="recipient-row">
        <span><b>{{ r.name || r.email }}</b> <span v-if="r.name" class="email-dim">&lt;{{ r.email }}&gt;</span></span>
        <button class="btn btn-sm btn-danger" @click="removeRecipient('to', i)">×</button>
      </div>
      <div class="add-row">
        <input v-model="newTo.name" placeholder="Name" @keyup.enter="addRecipient('to')" />
        <input v-model="newTo.email" type="email" placeholder="email@example.com" @keyup.enter="addRecipient('to')" />
        <button class="btn btn-sm btn-primary" @click="addRecipient('to')">+ Add</button>
      </div>
      <details class="bulk-paste">
        <summary>📥 Bulk paste (comma / newline separated)</summary>
        <textarea v-model="bulkInput.to" rows="3"
                  placeholder='alice@x.com, "Bob Smith" <bob@x.com>&#10;carol@x.com' />
        <button class="btn btn-sm btn-primary" @click="bulkAdd('to')" :disabled="!bulkInput.to.trim()">
          📥 Bulk add to To
        </button>
      </details>
    </div>

    <div class="recipients">
      <label>📋 CC (optional)</label>
      <div v-for="(r, i) in cfg.cc" :key="'cc-'+i" class="recipient-row">
        <span><b>{{ r.name || r.email }}</b> <span v-if="r.name" class="email-dim">&lt;{{ r.email }}&gt;</span></span>
        <button class="btn btn-sm btn-danger" @click="removeRecipient('cc', i)">×</button>
      </div>
      <div class="add-row">
        <input v-model="newCc.name" placeholder="Name" @keyup.enter="addRecipient('cc')" />
        <input v-model="newCc.email" type="email" placeholder="email@example.com" @keyup.enter="addRecipient('cc')" />
        <button class="btn btn-sm btn-primary" @click="addRecipient('cc')">+ Add</button>
      </div>
      <details class="bulk-paste">
        <summary>📥 Bulk paste (comma / newline separated)</summary>
        <textarea v-model="bulkInput.cc" rows="3"
                  placeholder='alice@x.com, "Bob Smith" <bob@x.com>&#10;carol@x.com' />
        <button class="btn btn-sm btn-primary" @click="bulkAdd('cc')" :disabled="!bulkInput.cc.trim()">
          📥 Bulk add to CC
        </button>
      </details>
    </div>

    <div class="actions">
      <button class="btn btn-primary" @click="save">💾 Save Email Settings</button>
      <button class="btn btn-test" @click="testConnection">🔌 Test Connection</button>
      <span v-if="testResult" class="test-result">{{ testResult }}</span>
    </div>
    <p class="hint" style="margin-top:8px;margin-bottom:0">
      <b>Test ใช้ค่าใน form ปัจจุบัน</b> — ไม่ต้อง Save ก่อน. ผลลัพธ์ไม่บันทึกไว้.
    </p>
  </div>
</template>

<style scoped>
.hint { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }
.dim { font-weight: 400; color: var(--muted); font-size: 11.5px; }
.prov-toggle { display: flex; gap: 6px; margin-bottom: 14px; }
.prov-toggle .btn.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; max-width: 720px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field input { width: 100%; }
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
.ext-link { color: var(--primary); }

.recipients { margin-top: 12px; max-width: 720px; }
.recipients .add-row, .recipients > [class*="row"] { max-width: 720px; }
.recipients > label { font-size: 12px; color: var(--muted); margin-bottom: 6px; display: block; font-weight: 600; }
.recipient-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  margin-bottom: 4px;
  font-size: 13px;
}
.email-dim { color: var(--muted); }
.add-row { display: flex; gap: 6px; margin-top: 6px; }
.add-row input { flex: 1; }

.bulk-paste {
  margin-top: 8px;
  border: 1px dashed var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}
.bulk-paste summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--muted);
  font-weight: 500;
  user-select: none;
}
.bulk-paste summary:hover { color: var(--text); }
.bulk-paste textarea {
  width: 100%;
  margin-top: 8px;
  margin-bottom: 6px;
  font-family: "SF Mono", monospace;
  font-size: 12px;
  resize: vertical;
}
.actions { display: flex; gap: 8px; align-items: center; margin-top: 14px; flex-wrap: wrap; }
.btn-test {
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  border-color: rgba(0, 113, 227, 0.3);
}
.btn-test:hover { background: var(--primary); color: white; border-color: var(--primary); }
.test-result { font-size: 12px; }
.btn-sm { padding: 3px 9px; font-size: 11px; }
</style>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'

interface NotifConfig {
  slack_webhook: string
  teams_webhook: string
  discord_webhook: string
  notify_on: string[]
}

const toast = useToast()

const form = reactive<NotifConfig>({
  slack_webhook:   '',
  teams_webhook:   '',
  discord_webhook: '',
  notify_on:       ['fail', 'error'],
})

// UI radio binds to a label, then maps to the list shape on save
const filterMode = ref<'error-only' | 'fail-error' | 'all'>('fail-error')
const testStatus = ref<Record<string, string>>({ slack: '', teams: '', discord: '' })

function modeFromList(list: string[]): typeof filterMode.value {
  if (list.includes('all')) return 'all'
  if (list.length === 1 && list[0] === 'error') return 'error-only'
  return 'fail-error'
}

function listFromMode(m: typeof filterMode.value): string[] {
  if (m === 'all') return ['all']
  if (m === 'error-only') return ['error']
  return ['fail', 'error']
}

async function load() {
  try {
    const cfg = await apiCall<NotifConfig>('/api/config/notifications')
    Object.assign(form, cfg)
    filterMode.value = modeFromList(cfg.notify_on || ['fail', 'error'])
  } catch { /* apiCall toasted */ }
}

async function save() {
  try {
    await apiCall('/api/config/notifications/save', {
      body: { ...form, notify_on: listFromMode(filterMode.value) },
    })
    toast.show('💾 Notification settings saved', 'ok')
  } catch { /* apiCall toasted */ }
}

async function testService(svc: 'slack' | 'teams' | 'discord') {
  const url = form[`${svc}_webhook`]
  if (!url) {
    testStatus.value[svc] = '❌ URL ว่าง'
    return
  }
  testStatus.value[svc] = '⏳ ส่ง…'
  try {
    const d = await apiCall<{ ok: boolean; results: Record<string, boolean | null> }>(
      '/api/notifications/test',
      { silent: true, body: { [`${svc}_webhook`]: url } }
    )
    testStatus.value[svc] = d.results?.[svc] ? '✅ ส่งสำเร็จ' : '❌ ส่งไม่สำเร็จ'
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'failed'
    testStatus.value[svc] = `❌ ${msg}`
  }
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="card-title">🔔 Chat Notifications</div>
    <p class="hint">
      Webhook ไป Slack / Teams / Discord เมื่อ scheduled run เสร็จ — เว้นว่างเพื่อปิด.
      <b>Test ส่ง webhook ในช่องนั้นทันที</b> โดยไม่ต้อง Save ก่อน
    </p>

    <div class="webhook-list">
      <div v-for="svc in (['slack','teams','discord'] as const)" :key="svc" class="webhook-row">
        <div class="row-header">
          <label>
            <span v-if="svc === 'slack'">💬 Slack</span>
            <span v-else-if="svc === 'teams'">👥 Microsoft Teams</span>
            <span v-else>🎮 Discord</span>
            Webhook URL
          </label>
          <button class="btn btn-sm test-btn" @click="testService(svc)">Test</button>
        </div>
        <input v-model="form[`${svc}_webhook`]" type="text"
               :placeholder="svc === 'slack' ? 'https://hooks.slack.com/services/...'
                           : svc === 'teams' ? 'https://outlook.office.com/webhook/...'
                           : 'https://discord.com/api/webhooks/...'" />
        <span v-if="testStatus[svc]" class="test-result">{{ testStatus[svc] }}</span>
      </div>
    </div>

    <div class="filter-row">
      <label>เมื่อไหร่ส่ง notification</label>
      <div class="radio-group">
        <label><input type="radio" v-model="filterMode" value="error-only"> เฉพาะ error</label>
        <label><input type="radio" v-model="filterMode" value="fail-error"> fail + error <span class="dim">(default)</span></label>
        <label><input type="radio" v-model="filterMode" value="all"> ทุก event</label>
      </div>
    </div>

    <button class="btn btn-primary" @click="save">💾 Save Notifications</button>
  </div>
</template>

<style scoped>
.hint { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }
.webhook-list { display: flex; flex-direction: column; gap: 14px; margin-bottom: 14px; max-width: 720px; }
.webhook-row label { font-size: 12px; color: var(--muted); font-weight: 600; }
.row-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.test-btn {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--primary-soft);
  color: var(--primary-dk, var(--primary));
  border: 1px solid rgba(0, 113, 227, 0.3);
}
.test-btn:hover { background: var(--primary); color: white; border-color: var(--primary); }
.webhook-row input { width: 100%; }
.test-result { font-size: 11px; margin-left: 6px; display: inline-block; margin-top: 4px; }
.filter-row { margin-bottom: 14px; }
.filter-row > label { font-size: 12px; color: var(--muted); font-weight: 600; display: block; margin-bottom: 6px; }
.radio-group { display: flex; gap: 14px; flex-wrap: wrap; }
.radio-group label { display: flex; align-items: center; gap: 4px; font-size: 13px; cursor: pointer; }
.dim { color: var(--muted); }
</style>

<script setup lang="ts">
import { reactive, onMounted, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useBrandingStore } from '@/stores/branding'

interface Branding {
  app_name: string
  subtitle: string
  logo: string
  logo_url: string
  primary_color: string
  footer: string
  company: string
  favicon: string
}

const toast = useToast()
const { confirm } = useConfirm()
const brandingStore = useBrandingStore()
const form = reactive<Branding>({
  app_name: '', subtitle: '', logo: '', logo_url: '',
  primary_color: '', footer: '', company: '', favicon: '',
})

// Live preview while typing — primary colour updates instantly,
// other fields apply on save to avoid noise.
watch(() => form.primary_color, (val) => {
  if (val && /^#[0-9A-Fa-f]{6}$/.test(val)) {
    document.documentElement.style.setProperty('--primary', val)
  }
})

async function load() {
  try {
    const b = await apiCall<Branding>('/api/config/branding')
    Object.assign(form, b)
  } catch { /* apiCall toasted */ }
}

async function save() {
  try {
    await apiCall('/api/config/branding/save', { body: form })
    toast.show('✅ Branding saved', 'ok')
    brandingStore.apply(form)   // immediate topbar/sidebar update
  } catch { /* apiCall toasted */ }
}

async function reset() {
  const ok = await confirm({
    title: 'Reset branding?',
    desc: 'จะกลับไปใช้ค่า default ของ QA Hub Demo และล้าง logo / สี / footer ที่ตั้งไว้',
    okLabel: 'Reset',
    danger: true,
  })
  if (!ok) return
  Object.assign(form, {
    app_name: 'QA Hub Demo', subtitle: 'Multi-Project Dashboard',
    logo: '🔬', logo_url: '', primary_color: '', footer: '', company: '', favicon: '',
  })
  document.documentElement.style.removeProperty('--primary')
  try {
    await apiCall('/api/config/branding/save', { body: form })
    toast.show('↺ Reset to defaults', 'ok')
    brandingStore.apply(form)
  } catch { /* apiCall toasted */ }
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="card-title">🎨 White-Label / Branding</div>
    <p class="hint">ปรับชื่อ logo และสี — บันทึกใน config.json ใช้ได้ทันที</p>

    <div class="form-grid">
      <div class="field"><label>App Name</label><input v-model="form.app_name" placeholder="QA Hub Demo" /></div>
      <div class="field"><label>Subtitle</label><input v-model="form.subtitle" placeholder="Multi-Project Dashboard" /></div>
      <div class="field"><label>Logo (emoji or initial)</label><input v-model="form.logo" placeholder="🔬" /></div>
      <div class="field"><label>Logo URL (optional, replaces emoji)</label><input v-model="form.logo_url" placeholder="https://..." /></div>
      <div class="field">
        <label>Primary Color</label>
        <div style="display:flex;gap:6px">
          <input v-model="form.primary_color" type="color" style="width:50px;padding:2px" />
          <input v-model="form.primary_color" type="text" placeholder="#2E75B6" />
        </div>
      </div>
      <div class="field"><label>Company</label><input v-model="form.company" /></div>
      <div class="field" style="grid-column: span 2"><label>Footer Text</label><input v-model="form.footer" /></div>
    </div>

    <!-- Live preview -->
    <div class="preview" :style="{ borderColor: form.primary_color || 'var(--primary)' }">
      <div class="prev-logo" :style="{ background: form.primary_color || 'var(--primary)' }">
        <img v-if="form.logo_url" :src="form.logo_url" alt="logo" />
        <span v-else>{{ form.logo || '🔬' }}</span>
      </div>
      <div>
        <div class="prev-name">{{ form.app_name || 'QA Hub Demo' }}</div>
        <div class="prev-sub">{{ form.subtitle || 'Multi-Project Dashboard' }}</div>
        <div v-if="form.company" class="prev-company">— {{ form.company }}</div>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-primary" @click="save">💾 Save Branding</button>
      <button class="btn" @click="reset">↺ Reset</button>
    </div>
  </div>
</template>

<style scoped>
.hint { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; max-width: 720px; }
.field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
.field input { width: 100%; }
.preview {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg);
  border: 2px solid var(--primary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-top: 14px;
  max-width: 480px;
}
.prev-logo {
  width: 48px; height: 48px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: white;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.prev-logo img { width: 100%; height: 100%; object-fit: contain; border-radius: var(--radius-sm); }
.prev-name    { font-weight: 700; font-size: 14px; color: var(--text); letter-spacing: -0.01em; }
.prev-sub     { font-size: 12px; color: var(--muted); }
.prev-company { font-size: 11px; color: var(--muted); margin-top: 2px; }
.actions { display: flex; gap: 8px; margin-top: 14px; }
</style>

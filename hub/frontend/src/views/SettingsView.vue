<script setup lang="ts">
import { ref } from 'vue'
import BrandingCard from '@/components/settings/BrandingCard.vue'
import EmailSettingsCard from '@/components/settings/EmailSettingsCard.vue'
import NotificationsCard from '@/components/settings/NotificationsCard.vue'
import AISettingsCard from '@/components/settings/AISettingsCard.vue'
import BackupCard from '@/components/settings/BackupCard.vue'

const sections = [
  { id: 'branding',      label: '🎨 Branding' },
  { id: 'email',         label: '📧 Email' },
  { id: 'notifications', label: '🔔 Notifications' },
  { id: 'ai',            label: '🤖 AI' },
  { id: 'backup',        label: '💾 Backup' },
] as const

const active = ref<typeof sections[number]['id']>('branding')
</script>

<template>
  <div class="settings-tabs">
    <button v-for="s in sections" :key="s.id"
            class="tab-btn"
            :class="{ active: active === s.id }"
            @click="active = s.id">
      {{ s.label }}
    </button>
  </div>

  <BrandingCard      v-if="active === 'branding'" />
  <EmailSettingsCard v-else-if="active === 'email'" />
  <NotificationsCard v-else-if="active === 'notifications'" />
  <AISettingsCard    v-else-if="active === 'ai'" />
  <BackupCard        v-else-if="active === 'backup'" />
</template>

<style scoped>
.settings-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
  border-bottom: 2px solid var(--border-soft);
  padding-bottom: 0;
  flex-wrap: wrap;
}
.tab-btn {
  background: none;
  border: none;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  font-weight: 500;
  font-family: inherit;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active {
  color: var(--text);
  font-weight: 700;
  border-bottom-color: var(--primary);
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { useOnboardingStore } from '@/stores/onboarding'

interface Props {
  /** Stable ID for localStorage dismiss state */
  id: string
  /** 'info' | 'tip' | 'warn' | 'danger' */
  variant?: 'info' | 'tip' | 'warn' | 'danger'
  /** Show even after dismissed (e.g. for warnings that should stay) */
  persistent?: boolean
}

const props = withDefaults(defineProps<Props>(), { variant: 'tip' })

const onboarding = useOnboardingStore()
const visible = computed(() => props.persistent || !onboarding.isTipSeen(props.id))

const icon = computed(() => ({
  info: 'ℹ️',
  tip: '💡',
  warn: '⚠️',
  danger: '🚨',
}[props.variant]))

function dismiss() {
  onboarding.dismissTip(props.id)
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="tip-banner" :class="variant">
      <span class="tip-icon">{{ icon }}</span>
      <div class="tip-body"><slot /></div>
      <button v-if="!persistent" class="tip-dismiss" @click="dismiss" aria-label="Dismiss">×</button>
    </div>
  </Transition>
</template>

<style scoped>
.tip-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  font-size: 13px;
  line-height: 1.55;
  border: 1px solid;
  animation: slide-down var(--duration) var(--ease);
}
@keyframes slide-down {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
.tip-icon { font-size: 16px; flex-shrink: 0; line-height: 1.4; }
.tip-body { flex: 1; }
.tip-body :deep(b) { color: var(--text); }
.tip-body :deep(code) { background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 4px; font-size: 92%; }
.tip-dismiss {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: currentColor;
  opacity: 0.6;
  padding: 0 4px;
  line-height: 1;
}
.tip-dismiss:hover { opacity: 1; }

@media (max-width: 640px) {
  /* Compact banner on phones: smaller padding + font, larger dismiss tap target */
  .tip-banner { padding: 10px 12px; font-size: 12.5px; gap: 8px; }
  .tip-icon { font-size: 14px; }
  .tip-dismiss {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    margin: -4px -4px -4px 0;
    padding: 0;
  }
}

.tip-banner.tip {
  background: var(--primary-soft);
  border-color: rgba(0, 113, 227, 0.2);
  color: var(--primary-dk);
}
.tip-banner.info {
  background: var(--bg);
  border-color: var(--border);
  color: var(--text-secondary);
}
.tip-banner.warn {
  background: var(--warn-soft);
  border-color: rgba(255, 159, 10, 0.3);
  color: var(--warn);
}
.tip-banner.danger {
  background: var(--danger-soft);
  border-color: rgba(255, 59, 48, 0.3);
  color: var(--danger);
}

[data-theme="dark"] .tip-banner.warn { color: var(--warn); }
[data-theme="dark"] .tip-banner.danger { color: var(--danger); }
[data-theme="dark"] .tip-banner.tip { color: var(--primary); }
</style>

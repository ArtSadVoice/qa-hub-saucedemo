<script setup lang="ts">
import { usePipelineStore } from '@/stores/pipeline'

const pipeline = usePipelineStore()
</script>

<template>
  <span class="run-badge" :class="pipeline.state" :title="pipeline.label">
    <span class="dot"></span>
    <span class="text">{{ pipeline.label }}</span>
  </span>
</template>

<style scoped>
.run-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  background: var(--bg);
  border: 1px solid var(--border-soft);
  color: var(--muted);
  user-select: none;
}
.dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--muted);
}
.run-badge.idle    { /* default */ }
.run-badge.running { background: var(--primary-soft); color: var(--primary-dk); border-color: rgba(0, 113, 227, 0.25); }
.run-badge.running .dot { background: var(--primary); animation: pulse 1.4s ease-in-out infinite; }
.run-badge.success { background: var(--success-soft); color: var(--success); border-color: rgba(52, 199, 89, 0.3); }
.run-badge.success .dot { background: var(--success); }
.run-badge.failed  { background: var(--danger-soft); color: var(--danger); border-color: rgba(255, 59, 48, 0.3); }
.run-badge.failed .dot { background: var(--danger); }

[data-theme="dark"] .run-badge.success { color: var(--success); }
[data-theme="dark"] .run-badge.failed  { color: var(--danger); }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(1.4); }
}

/* Hide text on narrow screens — keep just the dot */
@media (max-width: 800px) {
  .run-badge .text { display: none; }
  .run-badge { padding: 6px 8px; }
}
</style>

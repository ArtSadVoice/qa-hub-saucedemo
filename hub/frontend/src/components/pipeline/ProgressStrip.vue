<script setup lang="ts">
import { computed } from 'vue'
import { usePipelineStore } from '@/stores/pipeline'

interface Props {
  stages: { id: string; num: number }[]
  status: Record<string, { ok?: boolean } | undefined>
  activeStage: string
}
const props = defineProps<Props>()
const pipeline = usePipelineStore()

// Map status: 'done' | 'active' | 'pending'
const stageStatus = computed(() =>
  props.stages.map((s) => {
    const st = props.status[s.id]
    if (props.activeStage === s.id || props.activeStage === 'all') return 'active'
    if (st?.ok) return 'done'
    return 'pending'
  })
)

const completed = computed(() => stageStatus.value.filter((s) => s === 'done').length)
const total = computed(() => props.stages.length)
const pct = computed(() => total.value ? Math.round((completed.value / total.value) * 100) : 0)

const label = computed(() => {
  if (pipeline.state === 'running') return pipeline.label
  if (completed.value === total.value && total.value > 0) return '✓ Complete'
  if (completed.value > 0) return `${completed.value} of ${total.value} stages done`
  return 'No stages completed yet'
})
</script>

<template>
  <div class="strip" :class="pipeline.state">
    <div class="row">
      <span class="label">{{ label }}</span>
      <span class="pct">{{ pct }}%</span>
    </div>
    <div class="bar"><div class="fill" :style="{ width: pct + '%' }"></div></div>
    <div class="dots">
      <div v-for="(s, i) in stages" :key="s.id"
           class="dot" :class="stageStatus[i]"
           :title="`Stage ${s.num} — ${stageStatus[i]}`">
        <span class="num">{{ s.num }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strip {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: var(--space-3);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 64px;
  z-index: 5;
  transition: box-shadow var(--duration-fast) var(--ease);
}
.strip.running { box-shadow: 0 0 0 2px var(--primary-soft), var(--shadow-sm); }
.strip.failed  { box-shadow: 0 0 0 2px var(--danger-soft), var(--shadow-sm); }
.row { display: flex; align-items: baseline; margin-bottom: 8px; }
.label { font-size: 13px; font-weight: 600; color: var(--text); }
.pct { font-size: 11px; color: var(--muted); margin-left: auto; }

.bar {
  height: 4px;
  background: var(--border-soft);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 10px;
}
.fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--success));
  border-radius: 2px;
  transition: width var(--duration-slow) var(--ease);
}
.strip.failed .fill { background: linear-gradient(90deg, var(--warn), var(--danger)); }

.dots { display: flex; gap: 4px; flex-wrap: wrap; }
.dot {
  flex: 1;
  min-width: 28px;
  height: 22px;
  border-radius: var(--radius-xs);
  background: var(--border-soft);
  display: flex; align-items: center; justify-content: center;
  font-size: 10.5px; font-weight: 700;
  transition: all var(--duration-fast) var(--ease);
}
.dot.done   { background: var(--success); color: white; }
.dot.active {
  background: var(--primary); color: white;
  animation: pulse-bg 1.6s ease-in-out infinite;
}
.dot.pending { color: var(--muted); }
@keyframes pulse-bg {
  0%, 100% { box-shadow: 0 0 0 0 rgba(0, 113, 227, 0.45); }
  50% { box-shadow: 0 0 0 4px rgba(0, 113, 227, 0); }
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import { usePipelineStore } from '@/stores/pipeline'

interface Gate {
  verdict: string
  go: boolean
  summary: { total: number; pass: number; warn: number; hard_fail: number }
}

const router = useRouter()
const projects = useProjectStore()
const pipeline = usePipelineStore()
const gate = ref<Gate | null>(null)

async function load() {
  if (!projects.current) return
  try {
    gate.value = await apiCall<Gate>(`/api/release-gate?p=${projects.current}`, { silent: true })
  } catch {
    gate.value = null
  }
}

onMounted(load)
watch(() => projects.current, load)
// Refresh after every pipeline run completes — verdict can flip from
// NOGO→GO once tests/bugs land in history. Watching pipeline.state instead
// of polling so the request only fires on actual transitions.
watch(() => pipeline.state, (next, prev) => {
  if (prev === 'running' && (next === 'success' || next === 'failed' || next === 'idle')) {
    load()
  }
})

const verdictStyle = computed(() => {
  const v = gate.value?.verdict
  if (v === 'GO')        return { bg: 'var(--success-soft)', fg: 'var(--success)', label: '✅ GO' }
  if (v === 'NOGO')      return { bg: 'var(--danger-soft)', fg: 'var(--danger)', label: '❌ NOGO' }
  if (v === 'NOT_READY') return { bg: 'var(--warn-soft)', fg: 'var(--warn)', label: '⏳ NOT READY' }
  return { bg: 'var(--bg)', fg: 'var(--muted)', label: '— SKIP' }
})
</script>

<template>
  <button v-if="gate" class="mini-gate" :style="{ background: verdictStyle.bg, color: verdictStyle.fg }"
          @click="router.push('/release')" title="Click to view full Release Gate">
    <span class="verdict">{{ verdictStyle.label }}</span>
    <span class="summary">
      <b>{{ gate.summary.pass }}</b>/{{ gate.summary.total }} pass
      <template v-if="gate.summary.warn">· <b>{{ gate.summary.warn }}</b> warn</template>
      <template v-if="gate.summary.hard_fail">· <b>{{ gate.summary.hard_fail }}</b> hard-fail</template>
    </span>
    <span class="more">→</span>
  </button>
</template>

<style scoped>
.mini-gate {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-soft);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  width: 100%;
  margin-bottom: var(--space-3);
  transition: transform var(--duration-fast) var(--ease),
              box-shadow var(--duration-fast) var(--ease);
}
.mini-gate:hover { transform: translateY(-1px); box-shadow: var(--shadow-sm); }
.verdict { font-weight: 700; font-size: 14px; }
.summary { font-size: 12.5px; opacity: 0.85; }
.more { margin-left: auto; font-size: 16px; opacity: 0.6; }
</style>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, provide } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '@/stores/projects'
import StatsRow from '@/components/dashboard/StatsRow.vue'
import TrendChart from '@/components/dashboard/TrendChart.vue'
import ProjectInformation from '@/components/dashboard/ProjectInformation.vue'
import ScenarioSummary from '@/components/dashboard/ScenarioSummary.vue'
import RunHistoryTable from '@/components/dashboard/RunHistoryTable.vue'
import TipBanner from '@/components/TipBanner.vue'

const router = useRouter()
function goPipelineRun() { router.push('/pipeline?action=run') }
function goAddBug()       { router.push('/bugs?action=add') }
function goSendReport()   { router.push('/pipeline?action=send-report') }
function goActivity()     { router.push('/activity') }

const projects = useProjectStore()
const refreshTick = ref(0)
provide('dashboardRefreshTick', refreshTick)

let timer: ReturnType<typeof setInterval> | null = null
function tick() {
  if (document.visibilityState === 'visible') refreshTick.value++
}

onMounted(() => {
  if (!projects.all.length) projects.load()
  timer = setInterval(tick, 60_000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div v-if="!projects.current" class="card empty-hint">
    <div style="font-size:42px;margin-bottom:12px">👋</div>
    <h2 style="margin-bottom:8px">ยินดีต้อนรับ</h2>
    <p>เลือก project จาก dropdown ในแถบบนเพื่อเริ่มดู dashboard</p>
  </div>
  <template v-else>
    <TipBanner id="dashboard-overview" variant="tip">
      <b>Dashboard auto-refresh</b> ทุก 60 วินาที (เมื่อ tab visible) — ดู trend
      และ pass rate ปัจจุบันของ project นี้ · กด <code>↻</code> ที่ card ใดก็ refresh ได้ทันที
    </TipBanner>

    <!-- Quick Action Bar — Apple-style segmented row of common actions -->
    <div class="quick-actions">
      <button class="qa-btn primary" @click="goPipelineRun">
        <span class="qa-icon">▶</span>
        <span class="qa-label">Run Tests</span>
        <span class="qa-hint">@smoke / @e2e</span>
      </button>
      <button class="qa-btn" @click="goAddBug">
        <span class="qa-icon">🐛</span>
        <span class="qa-label">Add Bug</span>
        <span class="qa-hint">log new defect</span>
      </button>
      <button class="qa-btn" @click="goSendReport">
        <span class="qa-icon">📤</span>
        <span class="qa-label">Send Report</span>
        <span class="qa-hint">email to team</span>
      </button>
      <button class="qa-btn" @click="goActivity">
        <span class="qa-icon">📋</span>
        <span class="qa-label">Activity</span>
        <span class="qa-hint">recent changes</span>
      </button>
    </div>

    <StatsRow />
    <TrendChart />
    <ProjectInformation />
    <ScenarioSummary />
    <RunHistoryTable />
  </template>
</template>

<style scoped>
.empty-hint { text-align: center; padding: 60px 24px; }
.empty-hint h2 { color: var(--text); }
.empty-hint p { color: var(--muted); font-size: 14px; }

.quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
@media (max-width: 480px) {
  /* On narrow phones (≤480) the 200px floor leaves a phantom inline-end gap;
     drop to 160 so a 320-360px viewport gets a clean single-column stack. */
  .quick-actions { grid-template-columns: 1fr; gap: 8px; }
}
.qa-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: transform var(--duration-fast) var(--ease),
              box-shadow var(--duration-fast) var(--ease),
              border-color var(--duration-fast) var(--ease);
  box-shadow: var(--shadow-sm);
}
.qa-btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--primary);
}
.qa-btn.primary { border-left: 4px solid var(--primary); }
.qa-icon {
  font-size: 22px;
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.qa-btn.primary .qa-icon { background: var(--primary-soft); color: var(--primary-dk); }
.qa-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}
.qa-hint {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-top: 1px;
}
.qa-btn .qa-label, .qa-btn .qa-hint { line-height: 1.3; }
</style>

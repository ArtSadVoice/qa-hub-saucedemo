<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const onboarding = useOnboardingStore()
const open = ref(false)
const step = ref(0)

const steps = [
  {
    icon: '👋',
    title: 'ยินดีต้อนรับสู่ QA Hub Demo',
    desc: 'Hub คือ central dashboard สำหรับ QA — รวม test pipeline, bug tracking, schedule, และ release readiness ของทุก project ในที่เดียว',
    tips: [
      'ใช้ topbar เพื่อสลับ project',
      'กด ⌘K เพื่อเปิด command palette ค้นหาทุกอย่างได้',
      'กด ? เพื่อดู keyboard shortcuts',
    ],
  },
  {
    icon: '🎯',
    title: 'เริ่มจากเลือก Project',
    desc: 'เลือก project ที่ต้องการจาก dropdown ในแถบบน — ทุก tab จะแสดงข้อมูลของ project นั้น',
    tips: [
      'Project มี 3 type: full-pipeline · manual-testing · playwright-only',
      'แต่ละ type มี pipeline stages ที่ต่างกัน',
      'เลือก project ใหม่ → ทุก tab refresh อัตโนมัติ',
    ],
  },
  {
    icon: '⚙️',
    title: 'รัน Pipeline แต่ละ stage',
    desc: 'Pipeline tab รวม 9 stages — Upload Excel → BA Agent → Generate Spec → Run Tests → Generate Report',
    tips: [
      'กด "▶ Run" ของแต่ละ stage หรือ "⚡ Run All" รันต่อเนื่อง',
      'เลือก tag (@smoke / @e2e / @regression) + env (UAT/Prod) ก่อนรัน',
      '👁️ Watch mode = auto-rerun เมื่อแก้ไฟล์',
    ],
  },
  {
    icon: '🚦',
    title: 'ก่อน Release ดู Release Gate',
    desc: 'Release Gate ตรวจ criteria ทุกข้อ — Pass rate ≥ 80%, ไม่มี Critical bug, screenshots ครบ ฯลฯ',
    tips: [
      '✅ GO = ปล่อย release ได้',
      '❌ NOGO = มี hard-fail ต้องแก้ก่อน',
      '⏳ NOT READY = ยังไม่ได้รัน test เลย',
    ],
  },
]

const current = computed(() => steps[step.value])
const isLast = computed(() => step.value === steps.length - 1)

function next() {
  if (isLast.value) finish()
  else step.value++
}

function back() {
  if (step.value > 0) step.value--
}

function skip() {
  finish()
}

function finish() {
  onboarding.markWelcomeSeen()
  open.value = false
}

function showAgain() {
  step.value = 0
  open.value = true
}

defineExpose({ showAgain })

onMounted(() => {
  if (!onboarding.state.welcomeSeen) {
    setTimeout(() => { open.value = true }, 600)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="welcome-overlay" @click.self="skip">
        <div class="welcome-box">
          <div class="welcome-header">
            <button class="skip" @click="skip">ข้าม tutorial</button>
            <div class="dots">
              <span v-for="(_, i) in steps" :key="i" class="dot" :class="{ active: i === step, done: i < step }"></span>
            </div>
            <button class="close-x" @click="skip" aria-label="ปิด tutorial">×</button>
          </div>

          <div class="welcome-body">
            <div class="welcome-icon">{{ current.icon }}</div>
            <h1>{{ current.title }}</h1>
            <p class="welcome-desc">{{ current.desc }}</p>
            <div class="tips">
              <div v-for="(tip, i) in current.tips" :key="i" class="tip">
                <span class="check">✓</span> {{ tip }}
              </div>
            </div>
          </div>

          <div class="welcome-footer">
            <button v-if="step > 0" class="btn" @click="back">← ย้อน</button>
            <span style="flex:1"></span>
            <span class="step-count">{{ step + 1 }} / {{ steps.length }}</span>
            <button class="btn btn-primary btn-lg" @click="next">
              {{ isLast ? 'เริ่มใช้งาน 🎉' : 'ถัดไป →' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.welcome-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 99998;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.welcome-box {
  background: var(--card);
  border-radius: var(--radius-xl);
  width: 560px; max-width: 100%;
  box-shadow: var(--shadow-modal);
  overflow: hidden;
  animation: pop-in var(--duration-slow) var(--ease-spring);
}
@keyframes pop-in {
  from { opacity: 0; transform: scale(0.92) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.welcome-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  border-bottom: 1px solid var(--border-soft);
}
.skip {
  background: none; border: none;
  font-size: 13px; color: var(--muted);
  cursor: pointer; padding: 8px 12px;
  border-radius: var(--radius-sm);
  min-height: 36px;
}
.skip:hover { color: var(--text); background: var(--bg); }
.close-x {
  background: none; border: none;
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  font-size: 24px; line-height: 1;
  color: var(--muted); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.close-x:hover { color: var(--text); background: var(--bg); }
.dots { display: flex; gap: 6px; flex: 1; justify-content: center; }
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--border);
  transition: all var(--duration) var(--ease);
}
.dot.active { background: var(--primary); width: 24px; border-radius: 4px; }
.dot.done { background: var(--success); }

.welcome-body {
  padding: var(--space-8) var(--space-8);
  text-align: center;
}
.welcome-icon { font-size: 56px; margin-bottom: var(--space-4); }
.welcome-body h1 {
  font-size: 24px; font-weight: 700;
  letter-spacing: -0.02em; margin-bottom: var(--space-3);
}
.welcome-desc {
  color: var(--text-secondary); font-size: 15px;
  line-height: 1.55; margin-bottom: var(--space-6);
}
.tips {
  display: flex; flex-direction: column; gap: 10px;
  text-align: left;
  background: var(--bg);
  border-radius: var(--radius-md);
  padding: var(--space-4) var(--space-5);
}
.tip {
  display: flex; align-items: center; gap: 10px;
  font-size: 13.5px; color: var(--text);
}
.check {
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px;
  background: var(--success); color: white;
  border-radius: 50%; font-size: 11px; font-weight: 700;
  flex-shrink: 0;
}

.welcome-footer {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-soft);
  background: var(--card-2);
}
.step-count { font-size: 12px; color: var(--muted); }

@media (max-width: 600px) {
  .welcome-box { width: 100%; border-radius: var(--radius-lg); }
  .welcome-body { padding: var(--space-6) var(--space-5); }
  .welcome-icon { font-size: 48px; }
  .welcome-body h1 { font-size: 20px; }
  /* Tap targets ≥ 44 on mobile per WCAG / Apple HIG */
  .skip { min-height: 44px; padding: 10px 14px; font-size: 14px; }
  .close-x { width: 44px; height: 44px; font-size: 28px; }
  .welcome-header { padding: var(--space-3) var(--space-4); }
}
</style>

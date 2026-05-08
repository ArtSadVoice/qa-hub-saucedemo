<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { useProjectStore } from '@/stores/projects'
import type { Project } from '@/api/types'
import Modal from '@/components/ui/Modal.vue'

// Three add flows, all routed through the existing /api/projects/add endpoint:
//   - "register" (init_mode=none): point Hub at an existing folder
//   - "scaffold" (init_mode=scaffold + create_folder=true): copy from
//     scaffold/<flavor>/ then customize CLAUDE.md
//   - "clone"    (init_mode=git    + create_folder=true): git clone the
//     supplied URL into the target path
//
// Backend already validates path safety, runs the subprocess, and returns
// `used_git` / `used_scaffold` flags. This component is pure UI.

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'added'): void }>()

const toast = useToast()
const projects = useProjectStore()

type Mode = 'register' | 'scaffold' | 'clone'

const form = reactive({
  id:             '',
  name:           '',
  path:           '',
  type:           'full-pipeline' as Project['type'],
  color:          '#0071E3',
  mode:           'register' as Mode,
  has_playwright: true,
  base_url:       '',
  git_url:        '',
  figma_url:      '',
  company:        '',
  category:       '',
})

const submitting = ref(false)
const idTouched = ref(false)

// Path validation — fired on blur. Cheap (~10ms backend); shows inline
// hint so the operator knows if the path is sane BEFORE hitting submit
// and waiting for a 5s subprocess to fail.
interface PathCheck {
  ok: boolean
  exists: boolean
  is_dir: boolean
  not_empty: boolean
  within_root: boolean
  registered: boolean
  message: string
}
const pathCheck = ref<PathCheck | null>(null)
const checkingPath = ref(false)

async function validatePath() {
  const p = form.path.trim()
  if (!p) {
    pathCheck.value = null
    return
  }
  checkingPath.value = true
  try {
    pathCheck.value = await apiCall<PathCheck>(
      `/api/projects/validate-path?path=${encodeURIComponent(p)}&mode=${form.mode}`,
      { silent: true },
    )
  } catch {
    pathCheck.value = null
  } finally {
    checkingPath.value = false
  }
}
// Re-validate when mode switches (because verdict depends on mode)
watch(() => form.mode, () => { if (form.path.trim()) validatePath() })

function slugify(s: string) {
  return s.toLowerCase().trim()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

watch(() => form.name, (n) => {
  if (!idTouched.value) form.id = slugify(n)
})

watch(() => props.open, (open) => {
  if (open) {
    Object.assign(form, {
      id: '', name: '', path: '', type: 'full-pipeline', color: '#0071E3',
      mode: 'register', has_playwright: true, base_url: '', git_url: '',
      figma_url: '', company: '', category: '',
    })
    idTouched.value = false
  }
})

// Companies suggestion list — derived from existing projects
const companyOptions = computed<string[]>(() => {
  const set = new Set<string>()
  for (const p of projects.all) if (p.company) set.add(p.company)
  return Array.from(set).sort()
})

const submitLabel = computed(() => {
  if (submitting.value) {
    return form.mode === 'clone' ? '⏳ Cloning…'
         : form.mode === 'scaffold' ? '⏳ Creating…'
         : '⏳ Registering…'
  }
  return form.mode === 'clone' ? 'Clone from Git'
       : form.mode === 'scaffold' ? 'Create from Scaffold'
       : 'Register Folder'
})

const validForm = computed(() => {
  if (!form.id.trim() || !form.name.trim() || !form.path.trim()) return false
  if (!/^[a-zA-Z0-9_-]+$/.test(form.id)) return false
  if (form.mode === 'clone' && !form.git_url.trim()) return false
  return true
})

async function submit() {
  if (!validForm.value) {
    toast.show('Fill ID, Name, Path (+ Git URL if Clone mode)', 'warn')
    return
  }
  submitting.value = true
  try {
    const r = await apiCall<{
      ok?: boolean
      used_git?: boolean
      used_scaffold?: boolean
      has_playwright?: boolean
      error?: string
    }>('/api/projects/add', {
      body: {
        id:             form.id.trim(),
        name:           form.name.trim(),
        path:           form.path.trim(),
        type:           form.type,
        color:          form.color,
        company:        form.company.trim(),
        category:       form.category.trim(),
        figma_url:      form.figma_url.trim(),
        // Init mode — backend interprets "none" as just-register
        create_folder:  form.mode !== 'register',
        init_mode:      form.mode === 'clone' ? 'git'
                       : form.mode === 'scaffold' ? 'scaffold'
                       : 'none',
        git_url:        form.git_url.trim(),
        base_url:       form.base_url.trim(),
        has_playwright: form.has_playwright,
      },
    })

    if (r.error) {
      toast.show(`Error: ${r.error}`, 'err')
      return
    }
    let msg = `Project "${form.name}" added ✓`
    if (r.used_git)            msg += ' — cloned from Git'
    else if (r.used_scaffold)  msg += ' — scaffold copied'
    if ((r.used_git || r.used_scaffold) && r.has_playwright) {
      toast.show(msg + ' · อย่าลืมรัน npm install ก่อนใช้ Playwright', 'ok', 6000)
    } else {
      toast.show(msg, 'ok')
    }
    await projects.load()
    emit('added')
    emit('close')
  } catch { /* apiCall toasted */ }
  finally {
    submitting.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="➕ Add Project" @close="emit('close')">
    <div class="form">
      <!-- Mode selector — segmented control -->
      <div class="mode-bar">
        <button v-for="m in (['register','scaffold','clone'] as const)" :key="m"
                class="mode-btn"
                :class="{ active: form.mode === m }"
                @click="form.mode = m">
          {{ m === 'register' ? '📁 Register Existing'
             : m === 'scaffold' ? '🆕 Scaffold New'
             : '🔗 Clone from Git' }}
        </button>
      </div>
      <div class="mode-hint">
        <span v-if="form.mode === 'register'">
          ชี้ Hub ไปยัง folder ที่มีอยู่แล้วในเครื่อง — ไม่สร้าง file ใหม่
        </span>
        <span v-else-if="form.mode === 'scaffold'">
          คัดลอก scaffold/{{ form.type }}/ ไปยัง path ที่ระบุ + customize CLAUDE.md
          (auto-fill App name = Display Name, Base URL ถ้ามี)
        </span>
        <span v-else>
          git clone จาก URL ที่ระบุไป path ที่ระบุ (ต้องมี git auth พร้อมในเครื่อง server)
        </span>
      </div>

      <!-- Common fields -->
      <div class="row two-col">
        <div>
          <label>Display Name *</label>
          <input v-model="form.name" placeholder="My New Project" />
        </div>
        <div>
          <label>ID * <small>(slug — auto from name)</small></label>
          <input v-model="form.id" @input="idTouched = true"
                 placeholder="my-new-project" />
        </div>
      </div>

      <div class="row">
        <label>Path *
          <small>{{ form.mode === 'register'
            ? '(must exist)'
            : '(target — will be created)' }}</small>
        </label>
        <input v-model="form.path"
               @blur="validatePath"
               placeholder="C:\\Automation\\Customer\\Project" />
        <div v-if="checkingPath" class="path-hint">⟳ Checking…</div>
        <div v-else-if="pathCheck"
             class="path-hint"
             :class="{ 'path-ok': pathCheck.ok, 'path-warn': !pathCheck.ok }">
          {{ pathCheck.ok ? '✓' : '✗' }} {{ pathCheck.message }}
        </div>
      </div>

      <div class="row two-col">
        <div>
          <label>Type</label>
          <select v-model="form.type">
            <option value="full-pipeline">full-pipeline</option>
            <option value="manual-testing">manual-testing</option>
            <option value="playwright-only">playwright-only</option>
            <option value="pytest-only">pytest-only</option>
          </select>
        </div>
        <div>
          <label>Color</label>
          <div style="display:flex;gap:6px">
            <input v-model="form.color" type="color" style="width:50px;padding:2px" />
            <input v-model="form.color" type="text" />
          </div>
        </div>
      </div>

      <!-- Mode-specific fields -->
      <div v-if="form.mode === 'clone'" class="row">
        <label>Git URL *</label>
        <input v-model="form.git_url"
               placeholder="https://github.com/org/repo.git or git@github.com:org/repo.git" />
      </div>

      <div v-if="form.mode !== 'register'" class="row">
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.has_playwright" />
          Has Playwright tests (configures Base URL placeholder)
        </label>
      </div>

      <div v-if="form.mode !== 'register' && form.has_playwright" class="row">
        <label>Base URL <small>(replaces <code>&#123;&#123;BASE_URL&#125;&#125;</code> placeholder in scaffold's CLAUDE.md)</small></label>
        <input v-model="form.base_url" placeholder="https://your-app.example.com" />
      </div>

      <div class="row two-col">
        <div>
          <label>Company (optional)</label>
          <input v-model="form.company" list="companies-add" placeholder="Acme Corp" />
          <datalist id="companies-add">
            <option v-for="c in companyOptions" :key="c" :value="c" />
          </datalist>
        </div>
        <div>
          <label>Category (optional)</label>
          <input v-model="form.category" placeholder="QA · Survey · Internal …" />
        </div>
      </div>

      <div class="row">
        <label>Figma URL (optional)</label>
        <input v-model="form.figma_url" placeholder="https://figma.com/…" />
      </div>

      <div class="actions">
        <button class="btn" @click="emit('close')" :disabled="submitting">Cancel</button>
        <button class="btn btn-primary" @click="submit"
                :disabled="!validForm || submitting">
          {{ submitLabel }}
        </button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 12px; }

.mode-bar {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  background: var(--bg);
  padding: 4px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-soft);
}
.mode-btn {
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 600;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--muted);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease),
              color var(--duration-fast) var(--ease);
}
.mode-btn:hover { color: var(--text); }
.mode-btn.active {
  background: var(--card);
  color: var(--primary);
  box-shadow: var(--shadow-sm);
}
.mode-hint {
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.4;
  padding: 4px 2px;
}

.row label {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 4px;
  font-weight: 600;
}
.row label small { font-weight: 400; opacity: 0.7; margin-left: 4px; }
.row input, .row select { width: 100%; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.checkbox-label {
  display: flex !important;
  align-items: center;
  gap: 8px;
  margin-bottom: 0 !important;
  cursor: pointer;
  font-weight: 500 !important;
  color: var(--text) !important;
}
.checkbox-label input[type="checkbox"] { width: auto; }

.actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.path-hint {
  margin-top: 4px;
  font-size: 11.5px;
  line-height: 1.4;
  color: var(--muted);
}
.path-hint.path-ok   { color: var(--success); }
.path-hint.path-warn { color: var(--warn); }
</style>

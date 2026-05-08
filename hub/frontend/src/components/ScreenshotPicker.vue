<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useProjectStore } from '@/stores/projects'
import Modal from '@/components/ui/Modal.vue'

interface Shot { filepath: string; name: string; tcid?: string }

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'pick', md: string): void }>()

const projects = useProjectStore()
const shots = ref<Shot[]>([])
const loading = ref(false)
const search = ref('')

async function load() {
  if (!projects.current) return
  loading.value = true
  try {
    const r = await apiCall<{ files?: Shot[] } | Shot[]>(
      `/api/screenshots/list?p=${projects.current}`,
      { silent: true }
    )
    shots.value = Array.isArray(r) ? r : (r as { files: Shot[] }).files || []
  } catch {
    shots.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (v) => { if (v) load() })
onMounted(() => { if (props.open) load() })

const filteredShots = () =>
  search.value.trim()
    ? shots.value.filter((s) => (s.name + ' ' + (s.tcid || '')).toLowerCase().includes(search.value.toLowerCase()))
    : shots.value

const shotUrl = (s: Shot) =>
  `/api/screenshots/${encodeURI(s.filepath || s.name)}?p=${encodeURIComponent(projects.current)}`

function pick(s: Shot) {
  // Emit markdown image snippet so caller can paste into a description field
  const md = `![${s.tcid || s.name}](${shotUrl(s)})`
  emit('pick', md)
  emit('close')
}
</script>

<template>
  <Modal :open="open" title="📷 Attach screenshot" @close="emit('close')">
    <div class="picker">
      <input v-model="search" type="text" placeholder="Search by TC ID or filename…" class="search" />

      <div v-if="loading" class="empty">Loading screenshots…</div>
      <div v-else-if="!shots.length" class="empty">
        <div style="font-size:32px;margin-bottom:6px">📭</div>
        <div>No screenshots in this project yet</div>
        <div style="font-size:11.5px;color:var(--muted);margin-top:4px">Run Pipeline Stage 5 to generate</div>
      </div>
      <div v-else class="grid">
        <button v-for="s in filteredShots()" :key="s.filepath" class="thumb" @click="pick(s)" :title="s.name">
          <img :src="shotUrl(s)" :alt="s.name" loading="lazy" />
          <span class="cap">{{ s.tcid || s.name }}</span>
        </button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.picker { display: flex; flex-direction: column; gap: 12px; }
.search { width: 100%; }
.empty { text-align: center; padding: 30px; color: var(--muted); }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  max-height: 380px;
  overflow-y: auto;
}
.thumb {
  background: var(--card);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-sm);
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  transition: transform var(--duration-fast) var(--ease),
              border-color var(--duration-fast) var(--ease);
}
.thumb:hover { transform: translateY(-2px); border-color: var(--primary); }
.thumb img { width: 100%; aspect-ratio: 16/10; object-fit: cover; display: block; }
.cap { display: block; padding: 4px 8px; font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>

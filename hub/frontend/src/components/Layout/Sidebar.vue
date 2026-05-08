<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useBugsStore } from '@/stores/bugs'
import { useNotificationsStore } from '@/stores/notifications'
import { useBrandingStore } from '@/stores/branding'

const bugs = useBugsStore()
const notifs = useNotificationsStore()
const branding = useBrandingStore()

interface NavItem { to: string; icon: string; label: string; group?: string }
const items: NavItem[] = [
  { to: '/dashboard',   icon: '🏠', label: 'Dashboard',     group: 'Main' },
  { to: '/overview',    icon: '🌐', label: 'All Projects',  group: 'Main' },
  { to: '/pipeline',    icon: '⚙️', label: 'Pipeline',      group: 'Main' },
  { to: '/release',     icon: '🚦', label: 'Release Gate',  group: 'Main' },

  { to: '/bugs',        icon: '🐛', label: 'Bug Tracker',   group: 'Tracking' },
  { to: '/schedule',    icon: '📅', label: 'Schedule',      group: 'Tracking' },
  { to: '/activity',    icon: '📋', label: 'Activity Feed', group: 'Tracking' },

  { to: '/input',       icon: '📥', label: 'Input',         group: 'Files' },
  { to: '/output',      icon: '📤', label: 'Output',        group: 'Files' },
  { to: '/screenshots', icon: '📷', label: 'Screenshots',   group: 'Files' },

  { to: '/projects',    icon: '🗂️', label: 'Projects',      group: 'System' },
  { to: '/syscheck',    icon: '🩺', label: 'System Check',  group: 'System' },
  { to: '/guide',       icon: '📖', label: 'User Guide',    group: 'System' },
  { to: '/settings',    icon: '⚙️', label: 'Settings',      group: 'System' },
]
import { computed } from 'vue'
const grouped = computed(() => {
  const groups: Record<string, NavItem[]> = {}
  for (const it of items) {
    const g = it.group || 'Other'
    ;(groups[g] ||= []).push(it)
  }
  return groups
})
</script>

<template>
  <aside class="sidebar">
    <div class="sb-logo">
      <div class="brand">
        <span v-if="branding.branding.logo_url"><img :src="branding.branding.logo_url" alt="" style="height:18px;vertical-align:-3px;margin-right:4px"></span>
        <span v-else>{{ branding.branding.logo || '🔬' }}</span>
        {{ branding.branding.app_name || 'QA Hub Demo' }}
      </div>
      <div class="sub">{{ branding.branding.subtitle || 'Vue 3 (v2)' }}</div>
    </div>
    <nav class="sb-nav">
      <template v-for="(grp, name) in grouped" :key="name">
        <div class="group-label">{{ name }}</div>
        <RouterLink v-for="it in grp" :key="it.to" :to="it.to" class="nav-item">
          <span class="nav-main">
            <span class="ico">{{ it.icon }}</span> {{ it.label }}
          </span>
          <span v-if="it.to === '/bugs' && bugs.openCount > 0"
                class="nav-badge"
                :class="{ critical: bugs.criticalOpenCount > 0 }"
                :title="`${bugs.openCount} open bugs`">
            {{ bugs.openCount }}
          </span>
          <span v-else-if="it.to === '/schedule' && notifs.unreadCount > 0"
                class="nav-badge sched"
                :title="`${notifs.unreadCount} unread schedule events`">
            {{ notifs.unreadCount }}
          </span>
        </RouterLink>
      </template>
    </nav>
    <div class="sb-footer">
      <a href="/">← Switch to legacy UI</a>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 240px;
  background: var(--card);
  border-right: 1px solid var(--border-soft);
  color: var(--text);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0;
  height: 100vh;
  z-index: 20;
}
[data-theme="dark"] .sidebar { background: #161618; border-color: var(--border-soft); }  /* stylelint-disable-line color-no-hex */
.sb-logo {
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-soft);
}
.brand { font-size: 16px; font-weight: 700; letter-spacing: -0.01em; color: var(--text); }
.sub   { font-size: 11px; color: var(--muted); margin-top: 2px; font-weight: 500; }
.sb-nav { flex: 1; padding: 8px 10px; overflow-y: auto; }
.group-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 12px 12px 6px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 12px;
  cursor: pointer;
  font-size: 13.5px;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: background-color var(--duration-fast) var(--ease),
              color var(--duration-fast) var(--ease);
  user-select: none;
  text-decoration: none;
  margin-bottom: 1px;
  justify-content: space-between;
}
.nav-main { display: flex; align-items: center; gap: 10px; flex: 1; }
.nav-item:hover { background: var(--bg); color: var(--text); }
.nav-item.router-link-active {
  background: var(--primary-soft);
  color: var(--primary-dk);
  font-weight: 600;
}
[data-theme="dark"] .nav-item.router-link-active { color: var(--primary); }
.nav-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 10px;
  background: var(--warn);
  color: white;
  min-width: 18px;
  text-align: center;
}
.nav-badge.critical { background: var(--danger); }
.nav-badge.sched { background: var(--primary); }
.ico { font-size: 15px; width: 20px; text-align: center; flex-shrink: 0; }
.sb-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-soft);
  font-size: 11px;
}
.sb-footer a { color: var(--muted); }
.sb-footer a:hover { color: var(--primary); }
</style>

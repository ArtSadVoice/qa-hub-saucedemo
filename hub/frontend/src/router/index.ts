import { createRouter, createWebHistory } from 'vue-router'
import BugTrackerView from '@/views/BugTrackerView.vue'
import DashboardView from '@/views/DashboardView.vue'
import ActivityFeedView from '@/views/ActivityFeedView.vue'
import HubOverviewView from '@/views/HubOverviewView.vue'
import ReleaseReadinessView from '@/views/ReleaseReadinessView.vue'
import ScheduleView from '@/views/ScheduleView.vue'
import ProjectsView from '@/views/ProjectsView.vue'
import SettingsView from '@/views/SettingsView.vue'
import PipelineView from '@/views/PipelineView.vue'
import SystemCheckView from '@/views/SystemCheckView.vue'
import InputView from '@/views/InputView.vue'
import OutputView from '@/views/OutputView.vue'
import ScreenshotsView from '@/views/ScreenshotsView.vue'
import UserGuideView from '@/views/UserGuideView.vue'

const router = createRouter({
  // Vue lives at /v2/* — base URL keeps router paths sane
  history: createWebHistory('/v2/'),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard',   name: 'dashboard',   component: DashboardView,        meta: { title: 'Dashboard' } },
    { path: '/overview',    name: 'overview',    component: HubOverviewView,      meta: { title: 'All Projects Overview' } },
    { path: '/pipeline',    name: 'pipeline',    component: PipelineView,         meta: { title: 'Pipeline' } },
    { path: '/release',     name: 'release',     component: ReleaseReadinessView, meta: { title: 'Release Readiness' } },
    { path: '/schedule',    name: 'schedule',    component: ScheduleView,         meta: { title: 'Schedule Runner' } },
    { path: '/projects',    name: 'projects',    component: ProjectsView,         meta: { title: 'Projects' } },
    { path: '/bugs',        name: 'bugs',        component: BugTrackerView,       meta: { title: 'Bug Tracker' } },
    { path: '/activity',    name: 'activity',    component: ActivityFeedView,     meta: { title: 'Activity Feed' } },
    { path: '/input',       name: 'input',       component: InputView,            meta: { title: 'Input Files' } },
    { path: '/output',      name: 'output',      component: OutputView,           meta: { title: 'Output / Reports' } },
    { path: '/screenshots', name: 'screenshots', component: ScreenshotsView,      meta: { title: 'Screenshots' } },
    { path: '/syscheck',    name: 'syscheck',    component: SystemCheckView,      meta: { title: 'System Check' } },
    { path: '/guide',       name: 'guide',       component: UserGuideView,        meta: { title: 'User Guide' } },
    { path: '/settings',    name: 'settings',    component: SettingsView,         meta: { title: 'Settings' } },
  ],
})

export default router

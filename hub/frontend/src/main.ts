import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useBrandingStore } from '@/stores/branding'
import './styles/app.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// Load branding once on boot so logo/title/primary colour reflect saved settings
useBrandingStore().load()

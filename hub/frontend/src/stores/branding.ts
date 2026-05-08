/**
 * Branding store — fetches branding config and applies it to the document
 * (CSS vars + favicon + topbar/sidebar text). Lets the BrandingCard live-update
 * the topbar without a page reload.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiCall } from '@/api/client'

export interface Branding {
  app_name?: string
  subtitle?: string
  logo?: string
  logo_url?: string
  primary_color?: string
  footer?: string
  company?: string
  favicon?: string
}

export const useBrandingStore = defineStore('branding', () => {
  const branding = ref<Branding>({})

  function apply(b: Branding) {
    branding.value = b
    if (b.primary_color) {
      document.documentElement.style.setProperty('--primary', b.primary_color)
    }
    if (b.app_name) document.title = `${b.app_name} | Hub v2`
    if (b.favicon)  setFavicon(b.favicon)
  }

  function setFavicon(href: string) {
    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']")
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = href
  }

  async function load() {
    try {
      const b = await apiCall<Branding>('/api/config/branding', { silent: true })
      apply(b || {})
    } catch { /* keep defaults */ }
  }

  return { branding, load, apply }
})

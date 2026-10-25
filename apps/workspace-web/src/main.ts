// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin, QueryClient } from '@tanstack/vue-query'
import App from './App.vue'
import { router } from './router'
import { applyTheme } from './ui/theme'
import '@dx/web-shared/style.css'
import './style.css'
import './collab.css'
import './shell.css'

applyTheme()
const app = createApp(App)
app.use(createPinia())
app.use(VueQueryPlugin, {
  queryClient: new QueryClient({
    defaultOptions: {
      queries: { retry: 1, staleTime: 20_000, refetchOnWindowFocus: true },
    },
  }),
})
app.use(router)
app.mount('#app')

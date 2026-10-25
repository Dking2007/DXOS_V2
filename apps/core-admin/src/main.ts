// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import '@dx/web-shared/style.css'
import './style.css'
const app = createApp(App)
app.use(createPinia())
app.use(VueQueryPlugin, {
  queryClient: new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 10_000 } },
  }),
})
app.mount('#app')

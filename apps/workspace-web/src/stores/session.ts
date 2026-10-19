import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '@dx/web-shared/types.ts'
import { ApiError } from '@dx/web-shared/api.ts'
import { api } from '../api'

export const useSession = defineStore('session', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  async function load() {
    try {
      user.value = await api.request<User>('/me')
      api.setCsrf(user.value.csrf_token ?? '')
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error
      user.value = null
    } finally {
      ready.value = true
    }
    return user.value
  }
  async function logout() {
    await api.request('/auth/logout', { method: 'POST' })
    user.value = null
    window.location.assign('/login')
  }
  function can(capability: string) {
    return user.value?.capabilities?.includes(capability) ?? false
  }
  return { user, ready, load, logout, can }
})

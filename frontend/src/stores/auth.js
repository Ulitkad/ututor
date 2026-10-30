import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, refreshAccess, setToken } from '../api'

export const useAuth = defineStore('auth', () => {
  const user = ref(null)
  let initialized = false
  async function init() {
    if (initialized) return
    try { user.value = (await refreshAccess()).user } catch { user.value = null }
    initialized = true
  }
  async function login(username, password) {
    const data = await api('/auth/login', { method: 'POST', body: { username, password } })
    setToken(data.access_token)
    user.value = data.user
  }
  async function logout() {
    await api('/auth/logout', { method: 'POST' })
    clear()
  }
  function clear() { user.value = null; setToken(null) }
  return { user, init, login, logout, clear }
})

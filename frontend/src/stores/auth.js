import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/axios'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = computed(() => !!localStorage.getItem('access_token'))

  async function login(email, password) {
    const { data } = await api.post('auth/login/', { email, password })
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    await fetchUser()
  }

  async function register(userData) {
    const { data } = await api.post('auth/register/', userData)
    localStorage.setItem('access_token', data.tokens.access)
    localStorage.setItem('refresh_token', data.tokens.refresh)
    user.value = data.user
  }

  async function logout() {
    try {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        await api.post('auth/logout/', { refresh })
      }
    } catch {
      // Ignore logout errors
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  async function fetchUser() {
    try {
      const { data } = await api.get('auth/me/')
      user.value = data
    } catch {
      user.value = null
    }
  }

  return { user, isAuthenticated, login, register, logout, fetchUser }
})

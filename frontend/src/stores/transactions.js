import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useTransactionStore = defineStore('transactions', () => {
  const rows = ref([])
  const count = ref(0)
  const page = ref(1)
  const pageSize = 50
  const loading = ref(false)

  async function fetch(params = {}, targetPage = 1) {
    loading.value = true
    try {
      const { data } = await api.get('transactions/', {
        params: { ...params, page: targetPage, page_size: pageSize, ordering: '-date' },
      })
      rows.value = data.results || data
      count.value = data.count ?? rows.value.length
      page.value = targetPage
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const { data } = await api.post('transactions/', payload)
    return data
  }

  async function update(id, payload) {
    const { data } = await api.patch(`transactions/${id}/`, payload)
    const idx = rows.value.findIndex((t) => t.id === id)
    if (idx !== -1) rows.value[idx] = data
    return data
  }

  async function remove(id) {
    await api.delete(`transactions/${id}/`)
    rows.value = rows.value.filter((t) => t.id !== id)
    count.value = Math.max(0, count.value - 1)
  }

  return { rows, count, page, pageSize, loading, fetch, create, update, remove }
})

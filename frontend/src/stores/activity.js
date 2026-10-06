import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useActivityStore = defineStore('activity', () => {
  const rows = ref([])
  const count = ref(0)
  const page = ref(1)
  const pageSize = 20
  const sessions = ref([])
  const loading = ref(false)

  async function fetchActivity(params = {}, targetPage = 1) {
    loading.value = true
    try {
      const { data } = await api.get('activity/', { params: { ...params, page: targetPage, page_size: pageSize } })
      rows.value = data.results || data
      count.value = data.count ?? rows.value.length
      page.value = targetPage
    } finally {
      loading.value = false
    }
  }

  async function fetchSessions() {
    const { data } = await api.get('agents/mcp-sessions/')
    sessions.value = data.results || data
  }

  // Unpaginated slice for an entity's history card.
  async function fetchEntityHistory(entityType, entityId) {
    const { data } = await api.get('activity/', {
      params: { entity_type: entityType, entity_id: entityId, page_size: 50 },
    })
    return data.results || data
  }

  return { rows, count, page, pageSize, sessions, loading, fetchActivity, fetchSessions, fetchEntityHistory }
})

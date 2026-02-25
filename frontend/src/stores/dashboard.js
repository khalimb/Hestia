import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useDashboardStore = defineStore('dashboard', () => {
  const summary = ref(null)
  const upcoming = ref([])
  const overdue = ref([])
  const loading = ref(false)

  async function fetchSummary() {
    loading.value = true
    try {
      const { data } = await api.get('dashboard/summary/')
      summary.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetchUpcoming() {
    const { data } = await api.get('dashboard/upcoming/')
    upcoming.value = data
  }

  async function fetchOverdue() {
    const { data } = await api.get('dashboard/overdue/')
    overdue.value = data
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchSummary(), fetchUpcoming(), fetchOverdue()])
    } finally {
      loading.value = false
    }
  }

  return { summary, upcoming, overdue, loading, fetchSummary, fetchUpcoming, fetchOverdue, fetchAll }
})

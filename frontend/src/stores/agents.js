import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useAgentStore = defineStore('agents', () => {
  const tokens = ref([])
  const assignments = ref([])
  const config = ref(null)
  const loading = ref(false)

  // --- MCP tokens -----------------------------------------------------------
  async function fetchTokens() {
    const { data } = await api.get('agents/mcp-tokens/')
    tokens.value = data
  }

  // Returns the full token + connector URL — shown once, never stored here.
  async function createToken(name) {
    const { data } = await api.post('agents/mcp-tokens/', { name })
    await fetchTokens()
    return data
  }

  async function revokeToken(id) {
    await api.delete(`agents/mcp-tokens/${id}/`)
    tokens.value = tokens.value.filter((t) => t.id !== id)
  }

  // --- Assignments ----------------------------------------------------------
  async function fetchAssignments() {
    loading.value = true
    try {
      const { data } = await api.get('agents/assignments/')
      assignments.value = data
    } finally {
      loading.value = false
    }
  }

  async function createAssignment(title) {
    const payload = title ? { title } : {}
    const { data } = await api.post('agents/assignments/', payload)
    await fetchAssignments()
    return data // includes rendered_prompt
  }

  async function fetchAssignment(id) {
    const { data } = await api.get(`agents/assignments/${id}/`)
    return data
  }

  async function fetchAssignmentPrompt(id) {
    const { data } = await api.get(`agents/assignments/${id}/prompt/`)
    return data.prompt
  }

  async function deleteAssignment(id) {
    await api.delete(`agents/assignments/${id}/`)
    assignments.value = assignments.value.filter((a) => a.id !== id)
  }

  // --- Prompt template config ----------------------------------------------
  async function fetchConfig() {
    const { data } = await api.get('agents/config/')
    config.value = data
    return data
  }

  async function saveTemplate(template) {
    const { data } = await api.patch('agents/config/', { assignment_template: template })
    config.value = data
    return data
  }

  return {
    tokens, assignments, config, loading,
    fetchTokens, createToken, revokeToken,
    fetchAssignments, createAssignment, fetchAssignment, fetchAssignmentPrompt, deleteAssignment,
    fetchConfig, saveTemplate,
  }
})

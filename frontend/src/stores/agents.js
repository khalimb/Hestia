import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useAgentStore = defineStore('agents', () => {
  const tokens = ref([])
  const config = ref(null)

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

  // --- The agent prompt -----------------------------------------------------
  async function fetchPrompt() {
    const { data } = await api.get('agents/prompt/')
    return data.prompt
  }

  async function fetchConfig() {
    const { data } = await api.get('agents/config/')
    config.value = data
    return data
  }

  async function saveTemplate(template) {
    const { data } = await api.patch('agents/config/', { prompt_template: template })
    config.value = data
    return data
  }

  return { tokens, config, fetchTokens, createToken, revokeToken, fetchPrompt, fetchConfig, saveTemplate }
})

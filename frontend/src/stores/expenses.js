import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/axios'

export const useExpenseStore = defineStore('expenses', () => {
  const expenses = ref([])
  const subjects = ref([])
  const expenseTypes = ref([])
  const paymentMethods = ref([])
  const paymentAccounts = ref([])
  const users = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchExpenses(params = {}) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('expenses/', { params })
      expenses.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch expenses'
    } finally {
      loading.value = false
    }
  }

  async function fetchSubjects() {
    try {
      const { data } = await api.get('subjects/')
      subjects.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch subjects'
    }
  }

  async function fetchExpenseTypes() {
    try {
      const { data } = await api.get('expense-types/')
      expenseTypes.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch expense types'
    }
  }

  async function fetchPaymentMethods() {
    try {
      const { data } = await api.get('payment-methods/')
      paymentMethods.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch payment methods'
    }
  }

  async function fetchPaymentAccounts() {
    try {
      const { data } = await api.get('payment-accounts/')
      paymentAccounts.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch accounts'
    }
  }

  async function fetchUsers() {
    try {
      const { data } = await api.get('auth/users/')
      users.value = data.results || data
    } catch (e) {
      error.value = e.response?.data || 'Failed to fetch users'
    }
  }

  async function createExpense(expenseData) {
    const { data } = await api.post('expenses/', expenseData)
    expenses.value.unshift(data)
    return data
  }

  async function updateExpense(id, expenseData) {
    const { data } = await api.patch(`expenses/${id}/`, expenseData)
    const idx = expenses.value.findIndex((e) => e.id === id)
    if (idx !== -1) expenses.value[idx] = data
    return data
  }

  async function deleteExpense(id) {
    await api.delete(`expenses/${id}/`)
    expenses.value = expenses.value.filter((e) => e.id !== id)
  }

  async function createSubject(subjectData) {
    const { data } = await api.post('subjects/', subjectData)
    subjects.value.push(data)
    return data
  }

  async function updateSubject(id, subjectData) {
    const { data } = await api.patch(`subjects/${id}/`, subjectData)
    const idx = subjects.value.findIndex((s) => s.id === id)
    if (idx !== -1) subjects.value[idx] = data
    return data
  }

  async function deleteSubject(id) {
    await api.delete(`subjects/${id}/`)
    subjects.value = subjects.value.filter((s) => s.id !== id)
  }

  async function createExpenseType(typeData) {
    const { data } = await api.post('expense-types/', typeData)
    expenseTypes.value.push(data)
    return data
  }

  async function updateExpenseType(id, typeData) {
    const { data } = await api.patch(`expense-types/${id}/`, typeData)
    const idx = expenseTypes.value.findIndex((t) => t.id === id)
    if (idx !== -1) expenseTypes.value[idx] = data
    return data
  }

  async function deleteExpenseType(id) {
    await api.delete(`expense-types/${id}/`)
    expenseTypes.value = expenseTypes.value.filter((t) => t.id !== id)
  }

  async function createPaymentMethod(methodData) {
    const { data } = await api.post('payment-methods/', methodData)
    paymentMethods.value.push(data)
    return data
  }

  async function updatePaymentMethod(id, methodData) {
    const { data } = await api.patch(`payment-methods/${id}/`, methodData)
    const idx = paymentMethods.value.findIndex((m) => m.id === id)
    if (idx !== -1) paymentMethods.value[idx] = data
    return data
  }

  async function deletePaymentMethod(id) {
    await api.delete(`payment-methods/${id}/`)
    paymentMethods.value = paymentMethods.value.filter((m) => m.id !== id)
  }

  async function createPaymentAccount(accountData) {
    const { data } = await api.post('payment-accounts/', accountData)
    paymentAccounts.value.push(data)
    return data
  }

  async function updatePaymentAccount(id, accountData) {
    const { data } = await api.patch(`payment-accounts/${id}/`, accountData)
    const idx = paymentAccounts.value.findIndex((a) => a.id === id)
    if (idx !== -1) paymentAccounts.value[idx] = data
    return data
  }

  async function deletePaymentAccount(id) {
    await api.delete(`payment-accounts/${id}/`)
    paymentAccounts.value = paymentAccounts.value.filter((a) => a.id !== id)
  }

  async function generateOccurrences() {
    const { data } = await api.post('expenses/generate_occurrences/')
    return data
  }

  return {
    expenses, subjects, expenseTypes, paymentMethods, paymentAccounts, users, loading, error,
    fetchExpenses, fetchSubjects, fetchExpenseTypes,
    fetchPaymentMethods, fetchPaymentAccounts, fetchUsers,
    createExpense, updateExpense, deleteExpense,
    createSubject, updateSubject, deleteSubject,
    createExpenseType, updateExpenseType, deleteExpenseType,
    createPaymentMethod, updatePaymentMethod, deletePaymentMethod,
    createPaymentAccount, updatePaymentAccount, deletePaymentAccount,
    generateOccurrences,
  }
})

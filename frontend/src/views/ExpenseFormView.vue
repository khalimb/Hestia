<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useExpenseStore } from '../stores/expenses'
import api from '../api/axios'

const router = useRouter()
const route = useRoute()
const store = useExpenseStore()

const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const error = ref('')

const CURRENCIES = ['GBP', 'EUR', 'USD', 'CAD', 'AUD', 'CHF', 'JPY', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'INR', 'BRL', 'ZAR', 'NZD', 'SGD', 'HKD', 'MXN']

const form = ref({
  name: '',
  description: '',
  subject: '',
  amount: '',
  currency: 'GBP',
  expense_type: '',
  recurrence_type: 'monthly',
  recurrence_day: 1,
  recurrence_month: null,
  start_date: new Date().toISOString().split('T')[0],
  end_date: '',
})

onMounted(async () => {
  await Promise.all([store.fetchSubjects(), store.fetchExpenseTypes()])
  if (isEdit.value) {
    try {
      const { data } = await api.get(`expenses/${route.params.id}/`)
      form.value = {
        name: data.name,
        description: data.description || '',
        subject: data.subject || '',
        amount: data.amount,
        currency: data.currency,
        expense_type: data.expense_type || '',
        recurrence_type: data.recurrence_type,
        recurrence_day: data.recurrence_day,
        recurrence_month: data.recurrence_month,
        start_date: data.start_date,
        end_date: data.end_date || '',
      }
    } catch {
      error.value = 'Failed to load expense.'
    }
  }
})

const showMonthField = computed(() =>
  ['quarterly', 'annual'].includes(form.value.recurrence_type)
)

const dayLabel = computed(() =>
  form.value.recurrence_type === 'weekly' ? 'Day of Week (0=Mon, 6=Sun)' : 'Day of Month'
)

async function handleSubmit() {
  error.value = ''
  loading.value = true
  const payload = { ...form.value }
  if (!payload.end_date) payload.end_date = null
  if (!payload.subject) payload.subject = null
  if (!payload.expense_type) payload.expense_type = null
  if (!payload.recurrence_month) payload.recurrence_month = null
  payload.amount = parseFloat(payload.amount)
  payload.recurrence_day = parseInt(payload.recurrence_day)
  if (payload.recurrence_month) payload.recurrence_month = parseInt(payload.recurrence_month)

  try {
    if (isEdit.value) {
      await store.updateExpense(route.params.id, payload)
      router.push(`/expenses/${route.params.id}`)
    } else {
      const data = await store.createExpense(payload)
      router.push(`/expenses/${data.id}`)
    }
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      error.value = Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('. ')
    } else {
      error.value = 'Failed to save expense.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>{{ isEdit ? 'Edit Expense' : 'New Expense' }}</h1>
    </div>

    <div class="card" style="max-width: 700px">
      <div class="card-body">
        <div v-if="error" class="alert alert-danger">{{ error }}</div>

        <form @submit.prevent="handleSubmit">
          <div class="form-group">
            <label class="form-label">Expense Name</label>
            <input v-model="form.name" type="text" class="form-input" placeholder="e.g. Electricity Bill" required />
          </div>

          <div class="form-group">
            <label class="form-label">Description</label>
            <textarea v-model="form.description" class="form-textarea" placeholder="Optional notes"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Subject <span class="text-muted text-xs">(optional)</span></label>
              <select v-model="form.subject" class="form-select">
                <option value="">None</option>
                <option v-for="s in store.subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Expense Type <span class="text-muted text-xs">(optional)</span></label>
              <select v-model="form.expense_type" class="form-select">
                <option value="">None</option>
                <option v-for="et in store.expenseTypes" :key="et.id" :value="et.id">{{ et.name }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Amount</label>
              <input v-model="form.amount" type="number" step="0.01" min="0" class="form-input" required />
            </div>
            <div class="form-group">
              <label class="form-label">Currency</label>
              <select v-model="form.currency" class="form-select">
                <option v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Recurrence</label>
              <select v-model="form.recurrence_type" class="form-select">
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="annual">Annual</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">{{ dayLabel }}</label>
              <input v-model="form.recurrence_day" type="number" :min="form.recurrence_type === 'weekly' ? 0 : 1" :max="form.recurrence_type === 'weekly' ? 6 : 31" class="form-input" required />
            </div>
          </div>

          <div v-if="showMonthField" class="form-group">
            <label class="form-label">Month (1-12)</label>
            <input v-model="form.recurrence_month" type="number" min="1" max="12" class="form-input" />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Start Date</label>
              <input v-model="form.start_date" type="date" class="form-input" required />
            </div>
            <div class="form-group">
              <label class="form-label">End Date (optional)</label>
              <input v-model="form.end_date" type="date" class="form-input" />
            </div>
          </div>

          <div class="flex gap-2" style="margin-top: 1.5rem">
            <button type="submit" class="btn btn-primary" :disabled="loading">
              {{ loading ? 'Saving...' : (isEdit ? 'Update Expense' : 'Create Expense') }}
            </button>
            <button type="button" class="btn btn-outline" @click="router.back()">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

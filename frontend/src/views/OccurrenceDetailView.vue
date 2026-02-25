<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { format, parseISO } from 'date-fns'
import api from '../api/axios'

const route = useRoute()
const router = useRouter()
const occurrence = ref(null)
const payments = ref([])
const loading = ref(true)
const error = ref('')
const showPaymentForm = ref(false)

const paymentForm = ref({
  amount_paid: '',
  currency: '',
  paid_date: new Date().toISOString().split('T')[0],
  payment_method: '',
  notes: '',
})
const paymentError = ref('')
const paymentLoading = ref(false)

onMounted(async () => {
  await fetchData()
})

async function fetchData() {
  loading.value = true
  try {
    const [occRes, payRes] = await Promise.all([
      api.get(`occurrences/${route.params.id}/`),
      api.get(`occurrences/${route.params.id}/payments/`),
    ])
    occurrence.value = occRes.data
    payments.value = payRes.data.results || payRes.data
    paymentForm.value.currency = occurrence.value.currency
  } catch {
    error.value = 'Failed to load occurrence.'
  } finally {
    loading.value = false
  }
}

const totalPaid = computed(() => {
  return payments.value.reduce((sum, p) => sum + parseFloat(p.amount_paid), 0)
})

const remaining = computed(() => {
  if (!occurrence.value) return 0
  return Math.max(0, parseFloat(occurrence.value.expected_amount) - totalPaid.value)
})

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`
  }
}

function openPaymentForm() {
  paymentForm.value = {
    amount_paid: remaining.value.toFixed(2),
    currency: occurrence.value.currency,
    paid_date: new Date().toISOString().split('T')[0],
    payment_method: '',
    notes: '',
  }
  paymentError.value = ''
  showPaymentForm.value = true
}

async function submitPayment() {
  paymentError.value = ''
  paymentLoading.value = true
  try {
    const payload = {
      ...paymentForm.value,
      amount_paid: parseFloat(paymentForm.value.amount_paid),
    }
    const { data } = await api.post(`occurrences/${route.params.id}/payments/`, payload)
    payments.value.unshift(data)
    showPaymentForm.value = false
    await fetchData()
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      paymentError.value = Object.values(data).flat().join(' ')
    } else {
      paymentError.value = 'Failed to save payment.'
    }
  } finally {
    paymentLoading.value = false
  }
}

async function deletePayment(payment) {
  if (!confirm('Delete this payment?')) return
  await api.delete(`payments/${payment.id}/`)
  payments.value = payments.value.filter((p) => p.id !== payment.id)
  await fetchData()
}
</script>

<template>
  <div>
    <div v-if="loading" class="loading-spinner">Loading...</div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>

    <template v-else-if="occurrence">
      <div class="page-header">
        <div>
          <h1>{{ occurrence.expense_name }}</h1>
          <p class="text-muted text-sm">Due: {{ format(parseISO(occurrence.due_date), 'dd MMMM yyyy') }}</p>
        </div>
        <div class="flex gap-2">
          <button @click="openPaymentForm" class="btn btn-primary">+ Log Payment</button>
          <RouterLink :to="`/expenses/${occurrence.expense}`" class="btn btn-outline">Back to Expense</RouterLink>
        </div>
      </div>

      <!-- Overdue alert -->
      <div v-if="occurrence.status === 'overdue'" class="alert alert-danger">
        This payment is overdue.
      </div>

      <!-- Summary cards -->
      <div class="grid-4 mb-4">
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Expected</p>
            <p style="font-size:1.25rem; font-weight:700" class="font-mono">
              {{ formatCurrency(occurrence.expected_amount, occurrence.currency) }}
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Total Paid</p>
            <p style="font-size:1.25rem; font-weight:700; color:var(--color-success)" class="font-mono">
              {{ formatCurrency(totalPaid, occurrence.currency) }}
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Remaining</p>
            <p style="font-size:1.25rem; font-weight:700" class="font-mono" :style="{ color: remaining > 0 ? 'var(--color-danger)' : 'var(--color-success)' }">
              {{ formatCurrency(remaining, occurrence.currency) }}
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Status</p>
            <span :class="`badge badge-${occurrence.status}`">{{ occurrence.status }}</span>
          </div>
        </div>
      </div>

      <!-- Payment log -->
      <div class="card">
        <div class="card-header">
          <h3>Payments</h3>
        </div>
        <div class="card-body" style="padding:0">
          <div v-if="!payments.length" class="empty-state">
            <p>No payments logged yet.</p>
          </div>
          <table v-else>
            <thead>
              <tr>
                <th>Date</th>
                <th class="text-right">Amount</th>
                <th>Method</th>
                <th>Notes</th>
                <th>Logged By</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="payment in payments" :key="payment.id">
                <td>{{ format(parseISO(payment.paid_date), 'dd MMM yyyy') }}</td>
                <td class="text-right font-mono">{{ formatCurrency(payment.amount_paid, payment.currency) }}</td>
                <td class="text-sm">{{ payment.payment_method || '—' }}</td>
                <td class="text-sm">{{ payment.notes || '—' }}</td>
                <td class="text-sm">{{ payment.logged_by_name }}</td>
                <td class="text-right">
                  <button @click="deletePayment(payment)" class="btn btn-sm btn-outline" style="color:var(--color-danger)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Payment modal -->
      <div v-if="showPaymentForm" class="modal-overlay" @click.self="showPaymentForm = false">
        <div class="modal">
          <div class="modal-header">
            <h3>Log Payment</h3>
            <button @click="showPaymentForm = false" class="btn btn-sm btn-outline">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="paymentError" class="alert alert-danger">{{ paymentError }}</div>
            <form @submit.prevent="submitPayment">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Amount</label>
                  <input v-model="paymentForm.amount_paid" type="number" step="0.01" class="form-input" required />
                </div>
                <div class="form-group">
                  <label class="form-label">Currency</label>
                  <input v-model="paymentForm.currency" type="text" class="form-input" maxlength="3" required />
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">Date Paid</label>
                <input v-model="paymentForm.paid_date" type="date" class="form-input" required />
              </div>
              <div class="form-group">
                <label class="form-label">Payment Method</label>
                <select v-model="paymentForm.payment_method" class="form-select">
                  <option value="">Select...</option>
                  <option value="Bank Transfer">Bank Transfer</option>
                  <option value="Direct Debit">Direct Debit</option>
                  <option value="Credit Card">Credit Card</option>
                  <option value="Debit Card">Debit Card</option>
                  <option value="Cash">Cash</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Notes</label>
                <textarea v-model="paymentForm.notes" class="form-textarea" placeholder="Optional notes"></textarea>
              </div>
              <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
                <button type="button" class="btn btn-outline" @click="showPaymentForm = false">Cancel</button>
                <button type="submit" class="btn btn-primary" :disabled="paymentLoading">
                  {{ paymentLoading ? 'Saving...' : 'Log Payment' }}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

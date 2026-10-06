<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { format, parseISO } from 'date-fns'
import { useTransactionStore } from '../stores/transactions'
import { useExpenseStore } from '../stores/expenses'
import { useAuthStore } from '../stores/auth'

// One-off spending (Deliveroo on Tuesday), as opposed to recurring expenses.
const store = useTransactionStore()
const dict = useExpenseStore()
const auth = useAuthStore()

const CURRENCIES = ['GBP', 'EUR', 'USD', 'CAD', 'AUD', 'CHF', 'JPY', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'INR', 'BRL', 'ZAR', 'NZD', 'SGD', 'HKD', 'MXN']

// --- filters -----------------------------------------------------------------
const today = new Date()
const month = ref(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`) // YYYY-MM
const filterType = ref('')
const filterPaidBy = ref('')
const search = ref('')

function monthBounds(ym) {
  const [y, m] = ym.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return { date_from: `${ym}-01`, date_to: `${ym}-${String(last).padStart(2, '0')}` }
}

function params() {
  const p = month.value ? monthBounds(month.value) : {}
  if (filterType.value) p.expense_type = filterType.value
  if (filterPaidBy.value) p.paid_by = filterPaidBy.value
  if (search.value.trim()) p.search = search.value.trim()
  return p
}

function load(page = 1) {
  store.fetch(params(), page).catch(() => { notice('Failed to load transactions.', true) })
}

watch([month, filterType, filterPaidBy], () => load(1))

onMounted(() => {
  dict.fetchExpenseTypes()
  dict.fetchSubjects()
  dict.fetchPaymentMethods()
  dict.fetchPaymentAccounts()
  dict.fetchUsers()
  load(1)
})

const totalPages = computed(() => Math.max(1, Math.ceil(store.count / store.pageSize)))

// Totals of the rows on screen, per currency.
const pageTotals = computed(() => {
  const t = {}
  for (const r of store.rows) t[r.currency] = (t[r.currency] || 0) + parseFloat(r.amount)
  return Object.entries(t)
})

// --- add / edit form ---------------------------------------------------------
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formError = ref('')
const form = ref(blankForm())

function blankForm() {
  return {
    date: new Date().toISOString().split('T')[0],
    amount: '',
    currency: 'GBP',
    merchant: '',
    notes: '',
    expense_type: '',
    subject: '',
    payment_method: '',
    account: '',
    paid_by: auth.user?.id || '',
  }
}

const selectedMethod = computed(() => dict.paymentMethods.find((m) => m.id === form.value.payment_method) || null)
const accountApplies = computed(() => !!selectedMethod.value?.requires_account)
watch(accountApplies, (applies) => { if (!applies) form.value.account = '' })

function openCreate() {
  editingId.value = null
  form.value = blankForm()
  formError.value = ''
  showForm.value = true
}

function openEdit(t) {
  editingId.value = t.id
  form.value = {
    date: t.date, amount: t.amount, currency: t.currency, merchant: t.merchant, notes: t.notes || '',
    expense_type: t.expense_type || '', subject: t.subject || '', payment_method: t.payment_method || '',
    account: t.account || '', paid_by: t.paid_by || '',
  }
  formError.value = ''
  showForm.value = true
}

async function submit(addAnother = false) {
  formError.value = ''
  saving.value = true
  const payload = { ...form.value, amount: parseFloat(form.value.amount) }
  for (const k of ['expense_type', 'subject', 'payment_method', 'account', 'paid_by']) {
    if (!payload[k]) payload[k] = null
  }
  if (!accountApplies.value) payload.account = null
  try {
    if (editingId.value) {
      await store.update(editingId.value, payload)
      showForm.value = false
    } else {
      await store.create(payload)
      if (addAnother) {
        const keep = { date: form.value.date, currency: form.value.currency, paid_by: form.value.paid_by, payment_method: form.value.payment_method, account: form.value.account }
        form.value = { ...blankForm(), ...keep }
      } else {
        showForm.value = false
      }
    }
    load(store.page)
  } catch (e) {
    const data = e.response?.data
    formError.value = data && typeof data === 'object'
      ? Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join('. ')
      : 'Failed to save transaction.'
  } finally {
    saving.value = false
  }
}

async function remove(t) {
  if (!confirm(`Delete "${t.merchant}" on ${t.date}?`)) return
  try {
    await store.remove(t.id)
  } catch {
    notice('Failed to delete transaction.', true)
  }
}

// --- notices -------------------------------------------------------------------
const noticeText = ref('')
const noticeError = ref(false)
let noticeTimer = null
function notice(message, isError = false) {
  noticeText.value = message
  noticeError.value = isError
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { noticeText.value = '' }, 6000)
}

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Transactions</h1>
        <p class="text-sm text-muted">One-off spending by category. Recurring bills live under Expenses.</p>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ New Transaction</button>
    </div>

    <div v-if="noticeText" :class="['alert', noticeError ? 'alert-danger' : 'alert-success']">{{ noticeText }}</div>

    <!-- Filters -->
    <div class="card mb-4">
      <div class="card-body flex gap-4 items-center" style="flex-wrap:wrap">
        <div class="form-group" style="margin:0">
          <input v-model="month" type="month" class="form-input" />
        </div>
        <div class="form-group" style="margin:0; flex:1; min-width:160px">
          <select v-model="filterType" class="form-select">
            <option value="">All categories</option>
            <option v-for="et in dict.expenseTypes" :key="et.id" :value="et.id">{{ et.name }}</option>
          </select>
        </div>
        <div class="form-group" style="margin:0; flex:1; min-width:160px">
          <select v-model="filterPaidBy" class="form-select">
            <option value="">Paid by anyone</option>
            <option v-for="u in dict.users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
        </div>
        <div class="form-group" style="margin:0; flex:1; min-width:180px">
          <input v-model="search" type="text" class="form-input" placeholder="Search merchant or notes" @keyup.enter="load(1)" />
        </div>
        <button class="btn btn-outline" @click="load(1)">Apply</button>
      </div>
    </div>

    <div v-if="store.loading && !store.rows.length" class="loading-spinner">Loading...</div>
    <div v-else-if="!store.rows.length" class="empty-state">
      <h3>No transactions</h3>
      <p>Nothing recorded for this selection. Add one above, or let the agent import a statement.</p>
    </div>
    <div v-else class="card">
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Merchant</th>
              <th>Category</th>
              <th class="text-right">Amount</th>
              <th>Paid by</th>
              <th>Paid with</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in store.rows" :key="t.id">
              <td class="text-sm" style="white-space:nowrap">{{ format(parseISO(t.date), 'dd MMM yyyy') }}</td>
              <td>
                <span style="font-weight:500">{{ t.merchant }}</span>
                <p v-if="t.notes" class="text-xs text-muted">{{ t.notes }}</p>
                <p v-if="t.subject_name" class="text-xs text-muted">{{ t.subject_name }}</p>
              </td>
              <td class="text-sm">{{ t.expense_type_name || '—' }}</td>
              <td class="text-right font-mono">{{ formatCurrency(t.amount, t.currency) }}</td>
              <td class="text-sm">{{ t.paid_by_name || '—' }}</td>
              <td class="text-sm">
                {{ t.payment_method_name || '—' }}
                <span v-if="t.account_name" class="text-xs text-muted">· {{ t.account_name }}</span>
              </td>
              <td class="text-right" style="white-space:nowrap">
                <button class="btn btn-sm btn-outline" @click="openEdit(t)">Edit</button>
                <button class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)" @click="remove(t)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-body flex items-center gap-2" style="justify-content:space-between; flex-wrap:wrap">
        <span class="text-sm">
          <span class="text-muted">{{ store.count }} transaction{{ store.count === 1 ? '' : 's' }}</span>
          <span v-for="[cur, total] in pageTotals" :key="cur" class="font-mono" style="margin-left:0.75rem">{{ formatCurrency(total, cur) }}</span>
          <span v-if="totalPages > 1" class="text-xs text-muted" style="margin-left:0.5rem">(this page)</span>
        </span>
        <div class="flex gap-2 items-center">
          <button class="btn btn-sm btn-outline" :disabled="store.page <= 1" @click="load(store.page - 1)">Previous</button>
          <span class="text-xs text-muted">Page {{ store.page }} of {{ totalPages }}</span>
          <button class="btn btn-sm btn-outline" :disabled="store.page >= totalPages" @click="load(store.page + 1)">Next</button>
        </div>
      </div>
    </div>

    <!-- Add / edit modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal" style="max-width:640px; width:95%">
        <div class="modal-header">
          <h3>{{ editingId ? 'Edit Transaction' : 'New Transaction' }}</h3>
          <button @click="showForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="formError" class="alert alert-danger">{{ formError }}</div>
          <form @submit.prevent="submit(false)">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Date</label>
                <input v-model="form.date" type="date" class="form-input" required />
              </div>
              <div class="form-group">
                <label class="form-label">Merchant</label>
                <input v-model="form.merchant" type="text" class="form-input" placeholder="e.g. Deliveroo" required />
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
                <label class="form-label">Category <span class="text-muted text-xs">(optional)</span></label>
                <select v-model="form.expense_type" class="form-select">
                  <option value="">None</option>
                  <option v-for="et in dict.expenseTypes" :key="et.id" :value="et.id">{{ et.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Subject <span class="text-muted text-xs">(optional)</span></label>
                <select v-model="form.subject" class="form-select">
                  <option value="">None</option>
                  <option v-for="s in dict.subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Payment Method <span class="text-muted text-xs">(optional)</span></label>
                <select v-model="form.payment_method" class="form-select">
                  <option value="">None</option>
                  <option v-for="m in dict.paymentMethods" :key="m.id" :value="m.id">{{ m.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">
                  Account <span class="text-muted text-xs">{{ accountApplies ? '(optional)' : '(n/a for this method)' }}</span>
                </label>
                <select v-model="form.account" class="form-select" :disabled="!accountApplies">
                  <option value="">None</option>
                  <option v-for="a in dict.paymentAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
                </select>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Paid by <span class="text-muted text-xs">(optional)</span></label>
                <select v-model="form.paid_by" class="form-select">
                  <option value="">Not recorded</option>
                  <option v-for="u in dict.users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Notes</label>
                <input v-model="form.notes" type="text" class="form-input" placeholder="Optional" />
              </div>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showForm = false">Cancel</button>
              <button v-if="!editingId" type="button" class="btn btn-outline" :disabled="saving" @click="submit(true)">Save &amp; add another</button>
              <button type="submit" class="btn btn-primary" :disabled="saving">
                {{ saving ? 'Saving...' : (editingId ? 'Update' : 'Save') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

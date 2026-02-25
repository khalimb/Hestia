<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { format, parseISO } from 'date-fns'
import api from '../api/axios'

const route = useRoute()
const router = useRouter()
const expense = ref(null)
const bills = ref([])
const loading = ref(true)
const error = ref('')

// Bill upload
const uploadingBill = ref(false)
const fileInput = ref(null)

onMounted(async () => {
  await fetchData()
})

async function fetchData() {
  loading.value = true
  try {
    const [expRes, billRes] = await Promise.all([
      api.get(`expenses/${route.params.id}/`),
      api.get(`expenses/${route.params.id}/bills/`),
    ])
    expense.value = expRes.data
    bills.value = billRes.data.results || billRes.data
  } catch {
    error.value = 'Failed to load expense.'
  } finally {
    loading.value = false
  }
}

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`
  }
}

function statusBadgeClass(status) {
  return `badge badge-${status}`
}

async function handleBillUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  uploadingBill.value = true
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post(`expenses/${route.params.id}/bills/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    bills.value.unshift(data)
  } catch (e) {
    const msg = e.response?.data?.file || e.response?.data?.detail || 'Upload failed'
    alert(Array.isArray(msg) ? msg.join(' ') : msg)
  } finally {
    uploadingBill.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function deleteBill(bill) {
  if (!confirm(`Delete "${bill.original_filename}"?`)) return
  await api.delete(`bills/${bill.id}/`)
  bills.value = bills.value.filter((b) => b.id !== bill.id)
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}
</script>

<template>
  <div>
    <div v-if="loading" class="loading-spinner">Loading...</div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>

    <template v-else-if="expense">
      <!-- Header -->
      <div class="page-header">
        <div>
          <h1>{{ expense.name }}</h1>
          <p v-if="expense.subject_name" class="text-sm" style="color:var(--color-gray-700); font-weight:500;">{{ expense.subject_name }}</p>
          <p class="text-muted text-sm">{{ expense.description }}</p>
        </div>
        <div class="flex gap-2">
          <RouterLink :to="`/expenses/${expense.id}/edit`" class="btn btn-outline">Edit</RouterLink>
          <button class="btn btn-outline" @click="router.back()">Back</button>
        </div>
      </div>

      <!-- Overdue alert -->
      <div v-if="expense.recent_occurrences?.some(o => o.status === 'overdue')" class="alert alert-danger">
        This expense has overdue payments.
      </div>

      <!-- Info cards -->
      <div class="grid-3 mb-4">
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Amount</p>
            <p style="font-size:1.25rem; font-weight:700" class="font-mono">
              {{ formatCurrency(expense.amount, expense.currency) }}
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Expense Type</p>
            <p style="font-weight:600">{{ expense.expense_type_name || '—' }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Recurrence</p>
            <p style="font-weight:600; text-transform:capitalize">{{ expense.recurrence_type }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-xs text-muted">Status</p>
            <span :class="['badge', expense.is_active ? 'badge-paid' : 'badge-overdue']">
              {{ expense.is_active ? 'Active' : 'Inactive' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Occurrences timeline -->
      <div class="card mb-4">
        <div class="card-header">
          <h3>Occurrences</h3>
        </div>
        <div class="card-body" style="padding:0">
          <div v-if="!expense.recent_occurrences?.length" class="empty-state">
            <p>No occurrences generated yet. Run the generation command.</p>
          </div>
          <table v-else>
            <thead>
              <tr>
                <th>Due Date</th>
                <th class="text-right">Expected</th>
                <th class="text-right">Paid</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="occ in expense.recent_occurrences" :key="occ.id">
                <td>{{ format(parseISO(occ.due_date), 'dd MMM yyyy') }}</td>
                <td class="text-right font-mono">{{ formatCurrency(occ.expected_amount, occ.currency) }}</td>
                <td class="text-right font-mono">{{ formatCurrency(occ.total_paid, occ.currency) }}</td>
                <td><span :class="statusBadgeClass(occ.status)">{{ occ.status }}</span></td>
                <td class="text-right">
                  <RouterLink :to="`/occurrences/${occ.id}`" class="btn btn-sm btn-outline">View</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Bills -->
      <div class="card">
        <div class="card-header">
          <h3>Bills & Documents</h3>
          <label class="btn btn-sm btn-primary" :class="{ 'btn-disabled': uploadingBill }">
            {{ uploadingBill ? 'Uploading...' : '+ Upload Bill' }}
            <input
              ref="fileInput"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              style="display:none"
              @change="handleBillUpload"
              :disabled="uploadingBill"
            />
          </label>
        </div>
        <div class="card-body" style="padding:0">
          <div v-if="!bills.length" class="empty-state">
            <p>No bills uploaded yet.</p>
          </div>
          <table v-else>
            <thead>
              <tr>
                <th>File</th>
                <th>Type</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="bill in bills" :key="bill.id">
                <td>
                  <a v-if="bill.download_url" :href="bill.download_url" target="_blank" style="color:var(--color-primary)">
                    {{ bill.original_filename }}
                  </a>
                  <span v-else>{{ bill.original_filename }}</span>
                </td>
                <td class="text-sm">{{ bill.content_type }}</td>
                <td class="text-sm">{{ formatFileSize(bill.file_size) }}</td>
                <td class="text-sm">{{ format(parseISO(bill.uploaded_at), 'dd MMM yyyy') }}</td>
                <td class="text-right">
                  <button @click="deleteBill(bill)" class="btn btn-sm btn-outline" style="color:var(--color-danger)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

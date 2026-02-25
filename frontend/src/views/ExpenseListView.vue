<script setup>
import { onMounted, ref } from 'vue'
import { useExpenseStore } from '../stores/expenses'

const store = useExpenseStore()
const filterSubject = ref('')
const filterStatus = ref('')

onMounted(() => {
  store.fetchExpenses()
  store.fetchSubjects()
})

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`
  }
}

function applyFilters() {
  const params = {}
  if (filterSubject.value) params.subject = filterSubject.value
  if (filterStatus.value === 'active') params.is_active = true
  if (filterStatus.value === 'inactive') params.is_active = false
  store.fetchExpenses(params)
}

async function handleDelete(expense) {
  if (confirm(`Deactivate "${expense.name}"?`)) {
    await store.deleteExpense(expense.id)
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Expenses</h1>
      <RouterLink to="/expenses/new" class="btn btn-primary">+ New Expense</RouterLink>
    </div>

    <!-- Filters -->
    <div class="card mb-4">
      <div class="card-body flex gap-4 items-center">
        <div class="form-group" style="margin:0; flex:1">
          <select v-model="filterSubject" class="form-select" @change="applyFilters">
            <option value="">All Subjects</option>
            <option v-for="s in store.subjects" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="form-group" style="margin:0; flex:1">
          <select v-model="filterStatus" class="form-select" @change="applyFilters">
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="store.loading" class="loading-spinner">Loading...</div>

    <div v-else-if="!store.expenses.length" class="empty-state">
      <h3>No expenses yet</h3>
      <p>Create your first recurring expense to get started.</p>
      <RouterLink to="/expenses/new" class="btn btn-primary mt-4">+ New Expense</RouterLink>
    </div>

    <div v-else class="card">
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Subject</th>
              <th>Type</th>
              <th class="text-right">Amount</th>
              <th>Recurrence</th>
              <th>Status</th>
              <th>Next Due</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="expense in store.expenses" :key="expense.id">
              <td>
                <RouterLink :to="`/expenses/${expense.id}`" style="text-decoration:none; color:var(--color-primary); font-weight:500;">
                  {{ expense.name }}
                </RouterLink>
              </td>
              <td>
                <span v-if="expense.subject_name" class="text-sm">{{ expense.subject_name }}</span>
                <span v-else class="text-xs text-muted">—</span>
              </td>
              <td>
                <span v-if="expense.expense_type_name" class="text-xs text-muted">{{ expense.expense_type_name }}</span>
                <span v-else class="text-xs text-muted">—</span>
              </td>
              <td class="text-right font-mono">{{ formatCurrency(expense.amount, expense.currency) }}</td>
              <td class="text-sm">{{ expense.recurrence_type }}</td>
              <td>
                <span :class="['badge', expense.is_active ? 'badge-paid' : 'badge-overdue']">
                  {{ expense.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="text-sm">
                {{ expense.next_occurrence ? expense.next_occurrence.due_date : '—' }}
              </td>
              <td class="text-right">
                <RouterLink :to="`/expenses/${expense.id}/edit`" class="btn btn-sm btn-outline">Edit</RouterLink>
                <button @click="handleDelete(expense)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger);">
                  Deactivate
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

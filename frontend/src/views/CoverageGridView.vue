<script setup>
import { onMounted, ref, computed } from 'vue'
import api from '../api/axios'

const loading = ref(true)
const error = ref(null)
const data = ref(null)

async function fetchCoverage() {
  loading.value = true
  error.value = null
  try {
    const res = await api.get('dashboard/coverage/')
    data.value = res.data
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load the coverage grid.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchCoverage)

const subjects = computed(() => data.value?.subjects || [])
const expenseTypes = computed(() => data.value?.expense_types || [])
const matrix = computed(() => data.value?.matrix || {})

// Active expenses linking a (subject, type) pair; 0 when none exist (a gap).
function cellCount(subjectId, typeId) {
  return matrix.value[subjectId]?.[typeId] || 0
}

// How many expense types a given subject has at least one expense for.
function typesCovered(subjectId) {
  const row = matrix.value[subjectId]
  if (!row) return 0
  return expenseTypes.value.filter((t) => row[t.id] > 0).length
}

// How many subjects have at least one expense of a given type.
function subjectsCovered(typeId) {
  return subjects.value.filter((s) => cellCount(s.id, typeId) > 0).length
}

const totalCells = computed(() => subjects.value.length * expenseTypes.value.length)
const filledCells = computed(() =>
  subjects.value.reduce((acc, s) => acc + typesCovered(s.id), 0),
)
const gapCount = computed(() => totalCells.value - filledCells.value)
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Expense Coverage</h1>
      <button class="btn btn-outline" :disabled="loading" @click="fetchCoverage">
        {{ loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <p class="text-muted mb-4 page-intro">
      Which subjects have which expense types. A check marks an existing active
      expense; empty cells are gaps where you may still need to add one.
    </p>

    <div v-if="error" class="alert alert-danger mb-4">{{ error }}</div>

    <div v-if="loading" class="loading-spinner">Loading...</div>

    <div v-else-if="!subjects.length || !expenseTypes.length" class="empty-state">
      <h3>Nothing to compare yet</h3>
      <p>
        You need at least one subject and one expense type before a grid can be
        built. Add them under
        <RouterLink to="/settings">Settings</RouterLink>.
      </p>
    </div>

    <template v-else>
      <!-- Headline stats -->
      <div class="grid-3 mb-4">
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Subjects × Types</p>
            <p class="summary-stat">{{ subjects.length }} × {{ expenseTypes.length }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Combinations covered</p>
            <p class="summary-stat">{{ filledCells }} / {{ totalCells }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Empty combinations</p>
            <p class="summary-stat" :class="{ 'stat-gap': gapCount > 0 }">{{ gapCount }}</p>
          </div>
        </div>
      </div>

      <!-- Coverage matrix -->
      <div class="card">
        <div class="table-wrapper">
          <table class="coverage-table">
            <thead>
              <tr>
                <th class="corner">Subject</th>
                <th v-for="t in expenseTypes" :key="t.id">{{ t.name }}</th>
                <th class="text-right">Covered</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in subjects" :key="s.id">
                <th scope="row" class="subject-col">{{ s.name }}</th>
                <td
                  v-for="t in expenseTypes"
                  :key="t.id"
                  class="cell"
                  :class="cellCount(s.id, t.id) ? 'cell-filled' : 'cell-gap'"
                  :title="`${s.name} — ${t.name}: ${cellCount(s.id, t.id) || 'no expense'}`"
                >
                  <span v-if="cellCount(s.id, t.id)">
                    ✓<span v-if="cellCount(s.id, t.id) > 1" class="cell-count">{{ cellCount(s.id, t.id) }}</span>
                  </span>
                  <span v-else class="gap-dash">—</span>
                </td>
                <td class="text-right text-sm text-muted">
                  {{ typesCovered(s.id) }}/{{ expenseTypes.length }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" class="subject-col text-muted">Subjects covered</th>
                <td v-for="t in expenseTypes" :key="t.id" class="cell text-sm text-muted">
                  {{ subjectsCovered(t.id) }}/{{ subjects.length }}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Expenses that can't be placed in the grid -->
      <p
        v-if="data.unassigned.no_subject || data.unassigned.no_type"
        class="text-sm text-muted mt-4"
      >
        <template v-if="data.unassigned.no_subject">
          {{ data.unassigned.no_subject }} active expense(s) have no subject assigned.
        </template>
        <template v-if="data.unassigned.no_type">
          {{ data.unassigned.no_type }} active expense(s) have no expense type assigned.
        </template>
        These are not shown in the grid above.
      </p>
    </template>
  </div>
</template>

<style scoped>
.page-intro {
  margin-top: -0.5rem;
  max-width: 60ch;
}
.summary-stat {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0.25rem 0 0;
}
.stat-gap {
  color: var(--color-warning, #f59e0b);
}

.coverage-table {
  width: 100%;
  border-collapse: collapse;
}
.coverage-table th,
.coverage-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--color-gray-200, #e5e7eb);
}
.coverage-table thead th {
  text-align: center;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--color-gray-500, #6b7280);
  white-space: nowrap;
}
.coverage-table thead th.corner,
.subject-col {
  text-align: left;
}
/* Keep the subject name visible when the grid scrolls horizontally. */
.corner,
.subject-col {
  position: sticky;
  left: 0;
  background: #fff;
  z-index: 1;
}
.corner {
  z-index: 2;
}
.subject-col {
  font-weight: 600;
  white-space: nowrap;
}
.cell {
  text-align: center;
  font-weight: 600;
}
.cell-filled {
  color: #065f46;
  background: var(--color-success-bg, #ecfdf5);
}
.gap-dash {
  color: var(--color-gray-300, #d1d5db);
  font-weight: 400;
}
.cell-count {
  font-size: 0.7rem;
  margin-left: 0.125rem;
  vertical-align: super;
}
/* Surface the gaps in whichever row you're scanning. */
.coverage-table tbody tr:hover td {
  background: var(--color-gray-50, #f9fafb);
}
.coverage-table tbody tr:hover .subject-col {
  background: var(--color-gray-50, #f9fafb);
}
.coverage-table tbody tr:hover .cell-gap {
  background: #fff7ed;
}
.coverage-table tfoot th,
.coverage-table tfoot td {
  border-top: 2px solid var(--color-gray-200, #e5e7eb);
  border-bottom: none;
  font-size: 0.8125rem;
}
</style>

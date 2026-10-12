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

// One section per subject type (plus "Untyped subjects" last, against every category).
const sections = computed(() => data.value?.sections || [])

function cellCount(section, subjectId, typeId) {
  return section.matrix[subjectId]?.[typeId] || 0
}

function typesCovered(section, subjectId) {
  const row = section.matrix[subjectId]
  if (!row) return 0
  return section.expense_types.filter((t) => row[t.id] > 0).length
}

function subjectsCovered(section, typeId) {
  return section.subjects.filter((s) => cellCount(section, s.id, typeId) > 0).length
}

function outsideSummary(section, subjectId) {
  const extra = section.outside?.[subjectId]
  if (!extra) return ''
  return Object.entries(extra).map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(', ')
}

function stats(section) {
  const total = section.subjects.length * section.expense_types.length
  const filled = section.subjects.reduce((acc, s) => acc + typesCovered(section, s.id), 0)
  return { total, filled, gaps: total - filled }
}

const overall = computed(() => {
  const typed = sections.value.filter((s) => s.subject_type)
  return typed.reduce((acc, s) => {
    const st = stats(s)
    return { total: acc.total + st.total, filled: acc.filled + st.filled, gaps: acc.gaps + st.gaps }
  }, { total: 0, filled: 0, gaps: 0 })
})

function sectionTitle(section) {
  return section.subject_type ? section.subject_type.name : 'Untyped subjects'
}
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
      One section per subject type, showing only the categories that apply to it. A check marks an
      existing active expense; empty cells are gaps. Define types and their categories under
      <RouterLink to="/settings">Settings</RouterLink>.
    </p>

    <div v-if="error" class="alert alert-danger mb-4">{{ error }}</div>

    <div v-if="loading" class="loading-spinner">Loading...</div>

    <div v-else-if="!sections.length" class="empty-state">
      <h3>Nothing to compare yet</h3>
      <p>
        Add subjects and give them a type under
        <RouterLink to="/settings">Settings</RouterLink>.
      </p>
    </div>

    <template v-else>
      <!-- Headline stats across typed sections -->
      <div class="grid-3 mb-4">
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Expected combinations</p>
            <p class="summary-stat">{{ overall.total }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Covered</p>
            <p class="summary-stat">{{ overall.filled }} / {{ overall.total }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Gaps</p>
            <p class="summary-stat" :class="{ 'stat-gap': overall.gaps > 0 }">{{ overall.gaps }}</p>
          </div>
        </div>
      </div>

      <!-- One grid per section -->
      <div v-for="section in sections" :key="section.subject_type ? section.subject_type.id : 'untyped'" class="card mb-4">
        <div class="card-header">
          <h3>{{ sectionTitle(section) }}</h3>
          <span class="text-xs text-muted">
            <template v-if="section.subject_type">
              {{ section.subjects.length }} subject{{ section.subjects.length === 1 ? '' : 's' }} ×
              {{ section.expense_types.length }} categor{{ section.expense_types.length === 1 ? 'y' : 'ies' }} ·
              {{ stats(section).gaps }} gap{{ stats(section).gaps === 1 ? '' : 's' }}
            </template>
            <template v-else>no type assigned — shown against every category</template>
          </span>
        </div>
        <div v-if="!section.expense_types.length" class="empty-state">
          <p>No categories are marked as applicable to this type yet. Edit it in Settings.</p>
        </div>
        <div v-else class="table-wrapper">
          <table class="coverage-table">
            <thead>
              <tr>
                <th class="corner">Subject</th>
                <th v-for="t in section.expense_types" :key="t.id">{{ t.name }}</th>
                <th class="text-right">Covered</th>
                <th>Outside type</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in section.subjects" :key="s.id">
                <th scope="row" class="subject-col">{{ s.name }}</th>
                <td
                  v-for="t in section.expense_types"
                  :key="t.id"
                  class="cell"
                  :class="cellCount(section, s.id, t.id) ? 'cell-filled' : 'cell-gap'"
                  :title="`${s.name} — ${t.name}: ${cellCount(section, s.id, t.id) || 'no expense'}`"
                >
                  <span v-if="cellCount(section, s.id, t.id)">
                    ✓<span v-if="cellCount(section, s.id, t.id) > 1" class="cell-count">{{ cellCount(section, s.id, t.id) }}</span>
                  </span>
                  <span v-else class="gap-dash">—</span>
                </td>
                <td class="text-right text-sm text-muted">
                  {{ typesCovered(section, s.id) }}/{{ section.expense_types.length }}
                </td>
                <td class="text-xs text-muted" :title="outsideSummary(section, s.id) ? 'Active expenses in categories not marked for this type' : ''">
                  {{ outsideSummary(section, s.id) || '' }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" class="subject-col text-muted">Subjects covered</th>
                <td v-for="t in section.expense_types" :key="t.id" class="cell text-sm text-muted">
                  {{ subjectsCovered(section, t.id) }}/{{ section.subjects.length }}
                </td>
                <td></td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- Expenses that can't be placed in any grid -->
      <p
        v-if="data.unassigned.no_subject || data.unassigned.no_type"
        class="text-sm text-muted mt-4"
      >
        <template v-if="data.unassigned.no_subject">
          {{ data.unassigned.no_subject }} active expense(s) have no subject assigned.
        </template>
        <template v-if="data.unassigned.no_type">
          {{ data.unassigned.no_type }} active expense(s) have no category assigned.
        </template>
        These are not shown in the grids above.
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

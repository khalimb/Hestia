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

// Manual mark on an empty cell: 'in_progress' | 'not_needed' | undefined.
function cellMark(section, subjectId, typeId) {
  return section.marks?.[subjectId]?.[typeId]
}

// Click cycles an empty cell: none → in progress → not needed → none.
const NEXT_MARK = { undefined: 'in_progress', in_progress: 'not_needed', not_needed: null }
const marking = ref(new Set())

async function cycleMark(section, subject, type) {
  if (cellCount(section, subject.id, type.id)) return   // a real expense: nothing to mark
  const key = `${subject.id}:${type.id}`
  if (marking.value.has(key)) return
  const current = cellMark(section, subject.id, type.id)
  const next = NEXT_MARK[current]
  marking.value.add(key)
  try {
    await api.post('dashboard/coverage/mark/', { subject: subject.id, expense_type: type.id, status: next })
    if (!section.marks) section.marks = {}
    if (!section.marks[subject.id]) section.marks[subject.id] = {}
    if (next) section.marks[subject.id][type.id] = next
    else delete section.marks[subject.id][type.id]
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save the mark.'
  } finally {
    marking.value.delete(key)
  }
}

function cellClass(section, subjectId, typeId) {
  if (cellCount(section, subjectId, typeId)) return 'cell-filled'
  const mark = cellMark(section, subjectId, typeId)
  if (mark === 'in_progress') return 'cell-progress'
  if (mark === 'not_needed') return 'cell-not-needed'
  return 'cell-gap'
}

function cellTitle(section, subject, type) {
  const n = cellCount(section, subject.id, type.id)
  if (n) return `${subject.name} — ${type.name}: ${n} active expense${n > 1 ? 's' : ''}`
  const mark = cellMark(section, subject.id, type.id)
  const state = mark === 'in_progress' ? 'in progress (will be entered soon)' : mark === 'not_needed' ? 'not needed' : 'gap'
  return `${subject.name} — ${type.name}: ${state}. Click to change.`
}

function typesCovered(section, subjectId) {
  const row = section.matrix[subjectId]
  if (!row) return 0
  return section.expense_types.filter((t) => row[t.id] > 0).length
}

// Cells that count as expected for a subject: all categories minus those marked not needed.
function typesExpected(section, subjectId) {
  return section.expense_types.filter((t) => cellMark(section, subjectId, t.id) !== 'not_needed').length
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
  let expected = 0, filled = 0, progress = 0
  for (const s of section.subjects) {
    for (const t of section.expense_types) {
      const mark = cellMark(section, s.id, t.id)
      if (cellCount(section, s.id, t.id)) { expected += 1; filled += 1 }
      else if (mark === 'not_needed') { /* excluded from expectations */ }
      else if (mark === 'in_progress') { expected += 1; progress += 1 }
      else expected += 1
    }
  }
  return { expected, filled, progress, gaps: expected - filled - progress }
}

const overall = computed(() => {
  const typed = sections.value.filter((s) => s.subject_type)
  return typed.reduce((acc, s) => {
    const st = stats(s)
    return { expected: acc.expected + st.expected, filled: acc.filled + st.filled,
             progress: acc.progress + st.progress, gaps: acc.gaps + st.gaps }
  }, { expected: 0, filled: 0, progress: 0, gaps: 0 })
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
      One section per subject type, showing only the categories that apply to it. Define types and their
      categories under <RouterLink to="/settings">Settings</RouterLink>. Click an empty cell to mark it.
    </p>
    <p class="text-sm mb-4 legend">
      <span class="legend-item"><span class="swatch cell-filled">✓</span> active expense</span>
      <span class="legend-item"><span class="swatch cell-progress">~</span> in progress, will be entered soon</span>
      <span class="legend-item"><span class="swatch cell-not-needed">×</span> not needed</span>
      <span class="legend-item"><span class="swatch cell-gap">—</span> gap</span>
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
            <p class="text-sm text-muted">Covered</p>
            <p class="summary-stat">{{ overall.filled }} / {{ overall.expected }}</p>
            <p class="text-xs text-muted">expected combinations, excluding "not needed"</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">In progress</p>
            <p class="summary-stat stat-progress">{{ overall.progress }}</p>
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
              {{ stats(section).gaps }} gap{{ stats(section).gaps === 1 ? '' : 's' }}<template v-if="stats(section).progress"> · {{ stats(section).progress }} in progress</template>
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
                  :class="[cellClass(section, s.id, t.id), cellCount(section, s.id, t.id) ? '' : 'cell-clickable']"
                  :title="cellTitle(section, s, t)"
                  @click="cycleMark(section, s, t)"
                >
                  <span v-if="cellCount(section, s.id, t.id)">
                    ✓<span v-if="cellCount(section, s.id, t.id) > 1" class="cell-count">{{ cellCount(section, s.id, t.id) }}</span>
                  </span>
                  <span v-else-if="cellMark(section, s.id, t.id) === 'in_progress'">~</span>
                  <span v-else-if="cellMark(section, s.id, t.id) === 'not_needed'">×</span>
                  <span v-else class="gap-dash">—</span>
                </td>
                <td class="text-right text-sm text-muted">
                  {{ typesCovered(section, s.id) }}/{{ typesExpected(section, s.id) }}
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
.cell-progress {
  color: #1d4ed8;
  background: #eff6ff;
}
.cell-not-needed {
  color: #b91c1c;
  background: #fef2f2;
}
.cell-clickable {
  cursor: pointer;
  user-select: none;
}
.stat-progress {
  color: #1d4ed8;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: -0.5rem;
  color: var(--color-gray-500, #6b7280);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}
.swatch {
  display: inline-block;
  width: 1.5rem;
  text-align: center;
  border-radius: 0.25rem;
  font-weight: 600;
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
.coverage-table tbody tr:hover .cell-progress {
  background: #dbeafe;
}
.coverage-table tbody tr:hover .cell-not-needed {
  background: #fee2e2;
}
.coverage-table tfoot th,
.coverage-table tfoot td {
  border-top: 2px solid var(--color-gray-200, #e5e7eb);
  border-bottom: none;
  font-size: 0.8125rem;
}
</style>

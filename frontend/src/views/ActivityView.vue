<script setup>
import { ref, onMounted, computed } from 'vue'
import { format, parseISO } from 'date-fns'
import { useActivityStore } from '../stores/activity'
import { useExpenseStore } from '../stores/expenses'

const activity = useActivityStore()
const expenses = useExpenseStore()

const filterSource = ref('')
const filterActor = ref('')
const filterSession = ref(null) // { id, label } when drilling into one agent session

onMounted(() => {
  expenses.fetchUsers()
  activity.fetchSessions().catch(() => {})
  load(1)
})

function params() {
  const p = {}
  if (filterSource.value) p.source = filterSource.value
  if (filterActor.value) p.actor = filterActor.value
  if (filterSession.value) p.session = filterSession.value.id
  return p
}

function load(page = 1) {
  activity.fetchActivity(params(), page).catch(() => {})
}

const totalPages = computed(() => Math.max(1, Math.ceil(activity.count / activity.pageSize)))

function viewSession(s) {
  filterSession.value = { id: s.id, label: sessionLabel(s) }
  filterSource.value = ''
  filterActor.value = ''
  load(1)
}

function clearSession() {
  filterSession.value = null
  load(1)
}

function sessionLabel(s) {
  const client = s.client_name ? `${s.client_name}${s.client_version ? ' ' + s.client_version : ''}` : 'unknown client'
  return `${client} · ${s.token_name} · ${s.user_name}`
}

function toolCallsSummary(s) {
  const entries = Object.entries(s.tool_calls || {})
  if (!entries.length) return '—'
  return entries.sort((a, b) => b[1] - a[1]).map(([name, n]) => `${name} ×${n}`).join(', ')
}

function when(iso) {
  return iso ? format(parseISO(iso), 'dd MMM yyyy HH:mm') : ''
}

const ENTITY_LABELS = {
  expense: 'Expense', subject: 'Subject', expense_type: 'Expense type',
  payment_method: 'Payment method', payment_account: 'Account',
  payment: 'Payment', assignment: 'Assignment',
}

function entityLabel(type) {
  return ENTITY_LABELS[type] || type
}

function actionClass(action) {
  return { create: 'badge badge-paid', update: 'badge badge-pending', delete: 'badge badge-overdue' }[action] || 'badge'
}

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (v === true) return 'yes'
  if (v === false) return 'no'
  return String(v)
}

// "amount: 150.00 → 160.00" lines; on create only the "to" side, on delete only "from".
function changeLines(row) {
  return Object.entries(row.changes || {}).map(([field, c]) => {
    if (row.action === 'create') return `${field}: ${fmt(c.to)}`
    if (row.action === 'delete') return `${field}: ${fmt(c.from)}`
    return `${field}: ${fmt(c.from)} → ${fmt(c.to)}`
  })
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Activity</h1>
        <p class="text-sm text-muted">Who changed what, through the web, an agent import, or an MCP agent session.</p>
      </div>
      <button class="btn btn-outline" :disabled="activity.loading" @click="activity.fetchSessions(); load(activity.page)">
        {{ activity.loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <!-- Agent sessions -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent sessions</h3>
        <span class="text-xs text-muted">{{ activity.sessions.length }} session{{ activity.sessions.length === 1 ? '' : 's' }}</span>
      </div>
      <div class="card-body" style="padding:0">
        <div v-if="!activity.sessions.length" class="empty-state">
          <p>No agent sessions yet. Sessions appear once an MCP client connects with a token from Settings.</p>
        </div>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Started</th>
                <th>Client</th>
                <th>Token · owner</th>
                <th>Tool calls</th>
                <th class="text-right">Changes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in activity.sessions" :key="s.id">
                <td class="text-sm">
                  {{ when(s.started_at) }}
                  <p class="text-xs text-muted">{{ s.ended_at ? 'ended ' + when(s.ended_at) : 'last seen ' + when(s.last_seen_at) }}</p>
                </td>
                <td class="text-sm">{{ s.client_name || '—' }} <span class="text-xs text-muted">{{ s.client_version }}</span></td>
                <td class="text-sm">{{ s.token_name }} <span class="text-xs text-muted">· {{ s.user_name }}</span></td>
                <td class="text-xs">{{ toolCallsSummary(s) }}</td>
                <td class="text-right font-mono">{{ s.activity_count }}</td>
                <td class="text-right">
                  <button class="btn btn-sm btn-outline" :disabled="!s.activity_count" @click="viewSession(s)">View changes</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-4">
      <div class="card-body flex gap-4 items-center" style="flex-wrap:wrap">
        <div v-if="filterSession" class="flex gap-2 items-center" style="flex:1 1 100%">
          <span class="badge badge-pending">Session: {{ filterSession.label }}</span>
          <button class="btn btn-sm btn-outline" @click="clearSession">Clear</button>
        </div>
        <div class="form-group" style="margin:0; flex:1">
          <select v-model="filterSource" class="form-select" :disabled="!!filterSession" @change="load(1)">
            <option value="">All sources</option>
            <option value="web">Web</option>
            <option value="mcp">MCP agent</option>
            <option value="import">Agent import</option>
          </select>
        </div>
        <div class="form-group" style="margin:0; flex:1">
          <select v-model="filterActor" class="form-select" :disabled="!!filterSession" @change="load(1)">
            <option value="">Anyone</option>
            <option v-for="u in expenses.users" :key="u.id" :value="u.id">{{ u.display_name }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Log -->
    <div v-if="activity.loading && !activity.rows.length" class="loading-spinner">Loading...</div>
    <div v-else-if="!activity.rows.length" class="empty-state">
      <h3>No activity</h3>
      <p>Changes made from now on are recorded here.</p>
    </div>
    <div v-else class="card">
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Via</th>
              <th>Action</th>
              <th>What</th>
              <th>Changes</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in activity.rows" :key="row.id">
              <td class="text-sm" style="white-space:nowrap">{{ when(row.created_at) }}</td>
              <td class="text-sm">{{ row.actor_name || '—' }}</td>
              <td class="text-sm">{{ row.via }}</td>
              <td><span :class="actionClass(row.action)">{{ row.action }}</span></td>
              <td class="text-sm">
                <span class="text-xs text-muted">{{ entityLabel(row.entity_type) }}</span><br />
                <RouterLink v-if="row.entity_type === 'expense' && row.action !== 'delete'" :to="`/expenses/${row.entity_id}`" style="color:var(--color-primary); text-decoration:none">{{ row.entity_label }}</RouterLink>
                <span v-else>{{ row.entity_label }}</span>
              </td>
              <td class="text-xs" style="max-width:420px">
                <div v-for="line in changeLines(row)" :key="line">{{ line }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-body flex items-center gap-2" style="justify-content:space-between">
        <span class="text-xs text-muted">{{ activity.count }} change{{ activity.count === 1 ? '' : 's' }}</span>
        <div class="flex gap-2 items-center">
          <button class="btn btn-sm btn-outline" :disabled="activity.page <= 1" @click="load(activity.page - 1)">Previous</button>
          <span class="text-xs text-muted">Page {{ activity.page }} of {{ totalPages }}</span>
          <button class="btn btn-sm btn-outline" :disabled="activity.page >= totalPages" @click="load(activity.page + 1)">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>

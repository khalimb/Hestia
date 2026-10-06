<script setup>
import { onMounted, computed, ref } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { format, differenceInDays, parseISO, isToday, isTomorrow } from 'date-fns'
import api from '../api/axios'
import { useAgentStore } from '../stores/agents'

ChartJS.register(ArcElement, Tooltip, Legend)

const dashboard = useDashboardStore()
const agents = useAgentStore()
const markingPaid = ref({})

// --- Agent prompts: generate here, edit templates in Settings ---------------
const assignmentTopic = ref('')
const promptBusy = ref('')        // '' | 'import' | 'assignment'
const promptNotice = ref('')
const promptNoticeError = ref(false)
const promptPreview = ref('')      // shown when the clipboard is blocked
let promptTimer = null

function flashPrompt(message, isError = false) {
  promptNotice.value = message
  promptNoticeError.value = isError
  clearTimeout(promptTimer)
  promptTimer = setTimeout(() => { promptNotice.value = '' }, isError ? 8000 : 5000)
}

async function copyOrPreview(text, okMessage) {
  try {
    await navigator.clipboard.writeText(text)
    promptPreview.value = ''
    flashPrompt(okMessage)
  } catch {
    promptPreview.value = text
    flashPrompt("Couldn't reach the clipboard — copy the prompt from the box below.", true)
  }
}

async function copyImportPrompt() {
  promptBusy.value = 'import'
  try {
    const { data } = await api.get('agent-import/prompt/')
    await copyOrPreview(data.prompt, 'Import prompt copied — paste it into your agent and upload the bill.')
  } catch (e) {
    flashPrompt(e.response?.data?.detail || 'Failed to build the import prompt. Generate an import token in Settings first.', true)
  } finally {
    promptBusy.value = ''
  }
}

async function startAssignment() {
  promptBusy.value = 'assignment'
  try {
    const data = await agents.createAssignment(assignmentTopic.value.trim())
    assignmentTopic.value = ''
    await copyOrPreview(data.rendered_prompt, 'Assignment prompt copied — paste it into your agent and give the brief. See Assignments for the result.')
  } catch (e) {
    flashPrompt('Failed to start assignment: ' + (e.response?.data?.detail || e.message), true)
  } finally {
    promptBusy.value = ''
  }
}

onMounted(() => {
  dashboard.fetchAll()
})

async function markAsPaid(item) {
  markingPaid.value[item.id] = true
  try {
    await api.post(`occurrences/${item.id}/payments/`, {
      amount_paid: item.expected_amount,
      currency: item.currency,
      paid_date: new Date().toISOString().split('T')[0],
      // Prefill from the expense's configured method (see dashboard/views.py).
      payment_method: item.payment_method_name || '',
    })
    await dashboard.fetchAll()
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to mark as paid')
  } finally {
    delete markingPaid.value[item.id]
  }
}

const CHART_COLORS = ['#f97316', '#10b981', '#3b82f6', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#06b6d4', '#84cc16']

const typeChartData = computed(() => {
  if (!dashboard.summary?.type_breakdown?.length) return null
  const items = dashboard.summary.type_breakdown
  return {
    labels: items.map((t) => t.expense__expense_type__name || 'Uncategorised'),
    datasets: [
      {
        data: items.map((t) => parseFloat(t.total)),
        backgroundColor: items.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  plugins: {
    legend: { position: 'bottom', labels: { padding: 16 } },
  },
}

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(amount)
  } catch {
    return `${currency} ${parseFloat(amount).toFixed(2)}`
  }
}

function formatDueDate(dateStr) {
  const date = parseISO(dateStr)
  if (isToday(date)) return 'Today'
  if (isTomorrow(date)) return 'Tomorrow'
  const days = differenceInDays(date, new Date())
  if (days < 0) return `${Math.abs(days)} days overdue`
  if (days <= 7) return `In ${days} days`
  return format(date, 'dd MMM yyyy')
}

// Secondary line under an item: "Subject · Direct Debit · V A" (non-empty parts only).
function metaLine(item) {
  return [item.subject_name, item.payment_method_name, item.responsible_name]
    .filter(Boolean)
    .join(' · ')
}

function dueDateClass(item) {
  if (item.status === 'overdue') return 'text-danger'
  const days = differenceInDays(parseISO(item.due_date), new Date())
  if (days <= 3) return 'text-warning'
  return ''
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Dashboard</h1>
      <span v-if="dashboard.summary" class="text-muted">{{ dashboard.summary.month }}</span>
    </div>

    <!-- Agent prompts (templates are edited in Settings) -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent prompts</h3>
        <RouterLink to="/settings" class="text-xs text-muted" style="text-decoration:none">Edit templates in Settings</RouterLink>
      </div>
      <div class="card-body">
        <div v-if="promptNotice" :class="['alert', promptNoticeError ? 'alert-danger' : 'alert-success']">{{ promptNotice }}</div>
        <div class="grid-2" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:1rem">
          <div>
            <p class="text-sm" style="font-weight:600">Import a bill</p>
            <p class="text-xs text-muted" style="margin-bottom:0.5rem">Prompt that asks the agent for a bill, reads it, and creates the expense.</p>
            <button class="btn btn-sm btn-primary" :disabled="promptBusy === 'import'" @click="copyImportPrompt">
              {{ promptBusy === 'import' ? 'Building…' : 'Copy import prompt' }}
            </button>
          </div>
          <div>
            <p class="text-sm" style="font-weight:600">New assignment</p>
            <p class="text-xs text-muted" style="margin-bottom:0.5rem">Prompt for a deliverable (bill review, budget draft, bulk edit) saved back to <RouterLink to="/assignments">Assignments</RouterLink>.</p>
            <div class="flex gap-2 items-center" style="flex-wrap:wrap">
              <input v-model="assignmentTopic" type="text" class="form-input" style="flex:1; min-width:180px" placeholder="Topic (optional)" @keyup.enter="startAssignment" />
              <button class="btn btn-sm btn-primary" :disabled="promptBusy === 'assignment'" @click="startAssignment">
                {{ promptBusy === 'assignment' ? 'Starting…' : 'Copy assignment prompt' }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="promptPreview" style="margin-top:0.75rem">
          <textarea :value="promptPreview" readonly class="form-input" rows="8" style="font-family:'SF Mono',Monaco,monospace; font-size:0.8125rem" @focus="$event.target.select()"></textarea>
        </div>
      </div>
    </div>

    <div v-if="dashboard.loading" class="loading-spinner">Loading...</div>

    <template v-else>
      <!-- Alert banners -->
      <div v-if="dashboard.overdue.length" class="alert alert-danger flex items-center justify-between">
        <span>{{ dashboard.overdue.length }} overdue payment{{ dashboard.overdue.length > 1 ? 's' : '' }} requiring attention</span>
        <RouterLink to="/expenses" class="btn btn-sm btn-danger">View All</RouterLink>
      </div>

      <!-- Summary cards -->
      <div class="grid-3 mb-4" v-if="dashboard.summary">
        <div class="card" v-for="ct in dashboard.summary.currency_totals" :key="ct.currency">
          <div class="card-body">
            <p class="text-sm text-muted">Monthly Total ({{ ct.currency }})</p>
            <p class="summary-amount">{{ formatCurrency(ct.total, ct.currency) }}</p>
            <p class="text-xs text-muted">{{ ct.count }} expense{{ ct.count !== 1 ? 's' : '' }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Due Today</p>
            <p class="summary-amount">{{ dashboard.summary.due_today_count }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Overdue</p>
            <p class="summary-amount" :class="{'text-danger': dashboard.summary.overdue_count > 0}">
              {{ dashboard.summary.overdue_count }}
            </p>
          </div>
        </div>
      </div>

      <div class="grid-2 mb-4">
        <!-- Expense type breakdown chart -->
        <div class="card" v-if="typeChartData">
          <div class="card-header"><h3>By Expense Type</h3></div>
          <div class="card-body" style="max-height: 350px; display: flex; justify-content: center;">
            <Pie :data="typeChartData" :options="chartOptions" />
          </div>
        </div>

        <!-- Upcoming payments -->
        <div class="card">
          <div class="card-header">
            <h3>Upcoming Payments</h3>
            <span class="badge badge-pending">Next 30 days</span>
          </div>
          <div class="card-body" style="padding: 0">
            <div v-if="!dashboard.upcoming.length" class="empty-state">
              <p>No upcoming payments</p>
            </div>
            <table v-else>
              <tbody>
                <tr v-for="item in dashboard.upcoming.slice(0, 10)" :key="item.id">
                  <td>
                    <RouterLink :to="`/occurrences/${item.id}`" style="text-decoration:none; color:inherit;">
                      <strong>{{ item.expense_name }}</strong>
                      <br />
                      <span v-if="metaLine(item)" class="text-xs text-muted">{{ metaLine(item) }}</span>
                    </RouterLink>
                  </td>
                  <td class="text-right">
                    <span class="font-mono">{{ formatCurrency(item.expected_amount, item.currency) }}</span>
                  </td>
                  <td class="text-right" :class="dueDateClass(item)">
                    <span class="text-sm">{{ formatDueDate(item.due_date) }}</span>
                  </td>
                  <td class="text-right">
                    <button
                      class="btn btn-sm btn-primary"
                      :disabled="markingPaid[item.id]"
                      @click="markAsPaid(item)"
                    >{{ markingPaid[item.id] ? 'Saving...' : 'Mark Paid' }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Overdue items -->
      <div class="card" v-if="dashboard.overdue.length">
        <div class="card-header">
          <h3>Overdue</h3>
          <span class="badge badge-overdue">{{ dashboard.overdue.length }} item{{ dashboard.overdue.length > 1 ? 's' : '' }}</span>
        </div>
        <div class="card-body" style="padding: 0">
          <table>
            <thead>
              <tr>
                <th>Expense</th>
                <th>Subject</th>
                <th>Paid By</th>
                <th class="text-right">Amount</th>
                <th class="text-right">Due Date</th>
                <th class="text-right">Days Overdue</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in dashboard.overdue" :key="item.id">
                <td>
                  <RouterLink :to="`/occurrences/${item.id}`" style="text-decoration:none; color: var(--color-primary); font-weight: 500;">
                    {{ item.expense_name }}
                  </RouterLink>
                </td>
                <td>
                  <span v-if="item.subject_name" class="text-sm">{{ item.subject_name }}</span>
                  <span v-else class="text-xs text-muted">—</span>
                </td>
                <td>
                  <span v-if="item.payment_method_name" class="text-sm">{{ item.payment_method_name }}</span>
                  <span v-else class="text-xs text-muted">—</span>
                  <span v-if="item.responsible_name" class="text-xs text-muted"> · {{ item.responsible_name }}</span>
                </td>
                <td class="text-right font-mono">{{ formatCurrency(item.expected_amount, item.currency) }}</td>
                <td class="text-right">{{ format(parseISO(item.due_date), 'dd MMM yyyy') }}</td>
                <td class="text-right text-danger font-mono">{{ item.days_overdue }}d</td>
                <td class="text-right">
                  <button
                    class="btn btn-sm btn-primary"
                    :disabled="markingPaid[item.id]"
                    @click="markAsPaid(item)"
                  >{{ markingPaid[item.id] ? 'Saving...' : 'Mark Paid' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.summary-amount {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0.25rem 0;
}
.text-danger { color: var(--color-danger); }
.text-warning { color: var(--color-warning); }
</style>

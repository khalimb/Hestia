<script setup>
import { onMounted, computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { Pie } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { format, differenceInDays, parseISO, isToday, isTomorrow } from 'date-fns'

ChartJS.register(ArcElement, Tooltip, Legend)

const dashboard = useDashboardStore()

onMounted(() => {
  dashboard.fetchAll()
})

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
                      <span v-if="item.subject_name" class="text-xs text-muted">{{ item.subject_name }}</span>
                    </RouterLink>
                  </td>
                  <td class="text-right">
                    <span class="font-mono">{{ formatCurrency(item.expected_amount, item.currency) }}</span>
                  </td>
                  <td class="text-right" :class="dueDateClass(item)">
                    <span class="text-sm">{{ formatDueDate(item.due_date) }}</span>
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
                <th class="text-right">Amount</th>
                <th class="text-right">Due Date</th>
                <th class="text-right">Days Overdue</th>
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
                <td class="text-right font-mono">{{ formatCurrency(item.expected_amount, item.currency) }}</td>
                <td class="text-right">{{ format(parseISO(item.due_date), 'dd MMM yyyy') }}</td>
                <td class="text-right text-danger font-mono">{{ item.days_overdue }}d</td>
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

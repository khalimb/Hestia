<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
import api from '../api/axios'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

// --- period selection -------------------------------------------------------
const today = new Date()
const kind = ref('month')                 // month | quarter | year | custom
const month = ref(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`)
const quarterYear = ref(today.getFullYear())
const quarter = ref(Math.floor(today.getMonth() / 3) + 1)
const year = ref(today.getFullYear())
const customFrom = ref(`${today.getFullYear()}-01-01`)
const customTo = ref(today.toISOString().split('T')[0])

function pad(n) { return String(n).padStart(2, '0') }
function lastDay(y, m) { return new Date(y, m, 0).getDate() } // m is 1-based

const range = computed(() => {
  if (kind.value === 'month') {
    const [y, m] = month.value.split('-').map(Number)
    return { date_from: `${y}-${pad(m)}-01`, date_to: `${y}-${pad(m)}-${pad(lastDay(y, m))}` }
  }
  if (kind.value === 'quarter') {
    const y = Number(quarterYear.value)
    const m1 = (quarter.value - 1) * 3 + 1
    const m3 = m1 + 2
    return { date_from: `${y}-${pad(m1)}-01`, date_to: `${y}-${pad(m3)}-${pad(lastDay(y, m3))}` }
  }
  if (kind.value === 'year') {
    const y = Number(year.value)
    return { date_from: `${y}-01-01`, date_to: `${y}-12-31` }
  }
  return { date_from: customFrom.value, date_to: customTo.value }
})

const periodLabel = computed(() => {
  if (kind.value === 'month') {
    const [y, m] = month.value.split('-').map(Number)
    return new Date(y, m - 1, 1).toLocaleString('en-GB', { month: 'long', year: 'numeric' })
  }
  if (kind.value === 'quarter') return `Q${quarter.value} ${quarterYear.value}`
  if (kind.value === 'year') return String(year.value)
  return `${customFrom.value} → ${customTo.value}`
})

function step(direction) {
  if (kind.value === 'month') {
    const [y, m] = month.value.split('-').map(Number)
    const d = new Date(y, m - 1 + direction, 1)
    month.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
  } else if (kind.value === 'quarter') {
    let q = quarter.value + direction
    let y = Number(quarterYear.value)
    if (q < 1) { q = 4; y -= 1 }
    if (q > 4) { q = 1; y += 1 }
    quarter.value = q
    quarterYear.value = y
  } else if (kind.value === 'year') {
    year.value = Number(year.value) + direction
  }
}

// --- data -------------------------------------------------------------------
const data = ref(null)
const loading = ref(false)
const error = ref('')
// Which bucket the detailed breakdowns show: 'USD*' = all currencies normalised, else one currency.
const view = ref('USD*')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data: payload } = await api.get('dashboard/analytics/', { params: { ...range.value, normalise: 'USD' } })
    data.value = payload
    const available = payload.currencies.map((c) => c.currency)
    const valid = ['USD*', ...available]
    if (!valid.includes(view.value)) view.value = 'USD*'
    // A single-currency household gets its own currency, not a conversion.
    if (available.length === 1 && view.value === 'USD*') view.value = available[0]
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load analytics.'
  } finally {
    loading.value = false
  }
}

watch(range, load)
onMounted(load)

const normalised = computed(() => data.value?.normalised || null)
const current = computed(() => {
  if (!data.value) return null
  if (view.value === 'USD*') return normalised.value
  return data.value.currencies.find((c) => c.currency === view.value) || null
})
const currency = computed(() => (view.value === 'USD*' ? 'USD' : view.value))

function money(amount, cur = currency.value) {
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency: cur }).format(amount)
  } catch {
    return `${cur} ${parseFloat(amount).toFixed(2)}`
  }
}

function monthLabel(ym) {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-GB', { month: 'short', year: '2-digit' })
}

const chartData = computed(() => {
  if (!current.value) return null
  return {
    labels: current.value.by_month.map((m) => monthLabel(m.month)),
    datasets: [
      { label: 'Recurring', data: current.value.by_month.map((m) => parseFloat(m.recurring)), backgroundColor: '#3b82f6' },
      { label: 'One-off', data: current.value.by_month.map((m) => parseFloat(m.one_off)), backgroundColor: '#f97316' },
    ],
  }
})

const chartOptions = {
  responsive: true,
  plugins: { legend: { position: 'bottom' } },
  scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
}

// --- drill-down: the items behind one category / subject row ----------------
const drill = ref(null)        // { group, name } while open
const drillData = ref(null)
const drillLoading = ref(false)
const drillError = ref('')

async function openDrill(group, row) {
  drill.value = { group, name: row.name }
  drillData.value = null
  drillError.value = ''
  drillLoading.value = true
  try {
    const params = { ...range.value, group, id: row.id || 'none' }
    if (view.value === 'USD*') params.normalise = 'USD'
    else params.currency = view.value
    const { data: payload } = await api.get('dashboard/analytics/items/', { params })
    drillData.value = payload
  } catch (e) {
    drillError.value = e.response?.data?.detail || 'Failed to load items.'
  } finally {
    drillLoading.value = false
  }
}

function closeDrill() {
  drill.value = null
  drillData.value = null
}

const drillTitle = computed(() => {
  if (!drill.value) return ''
  return `${drill.value.group === 'category' ? 'Category' : 'Subject'}: ${drill.value.name} · ${periodLabel.value}`
})

function itemDate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function paidShareOf(bucket) {
  if (!bucket || parseFloat(bucket.recurring_expected) === 0) return null
  return (parseFloat(bucket.recurring_paid) / parseFloat(bucket.recurring_expected)) * 100
}

const SOURCE_LABELS = { ecb: 'ECB', latest: "today's rate", manual: 'manual' }

// "1 GBP = 1.3225 USD (ECB)" for ordinary rates; "1 USD = 11,801 UZS" for tiny ones.
const ratesLine = computed(() => {
  if (!normalised.value) return ''
  return Object.entries(normalised.value.rates)
    .filter(([cur]) => cur !== 'USD')
    .map(([cur, rate]) => {
      const r = parseFloat(rate)
      const src = normalised.value.rate_sources?.[cur] || ''
      const label = SOURCE_LABELS[src] || src
      const text = r < 0.01
        ? `1 USD = ${(1 / r).toLocaleString('en-GB', { maximumFractionDigits: 2 })} ${cur}`
        : `1 ${cur} = ${r.toFixed(4)} USD`
      return label ? `${text} (${label})` : text
    })
    .join(' · ')
})
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Analytics</h1>
        <p class="text-sm text-muted">Spend for a period: recurring bills due in it plus one-off transactions dated in it.</p>
      </div>
    </div>

    <!-- Period controls -->
    <div class="card mb-4">
      <div class="card-body flex gap-4 items-center" style="flex-wrap:wrap">
        <div class="form-group" style="margin:0">
          <select v-model="kind" class="form-select">
            <option value="month">Month</option>
            <option value="quarter">Quarter</option>
            <option value="year">Year</option>
            <option value="custom">Custom range</option>
          </select>
        </div>
        <template v-if="kind === 'month'">
          <div class="form-group" style="margin:0"><input v-model="month" type="month" class="form-input" /></div>
        </template>
        <template v-else-if="kind === 'quarter'">
          <div class="form-group" style="margin:0">
            <select v-model.number="quarter" class="form-select">
              <option :value="1">Q1 (Jan–Mar)</option>
              <option :value="2">Q2 (Apr–Jun)</option>
              <option :value="3">Q3 (Jul–Sep)</option>
              <option :value="4">Q4 (Oct–Dec)</option>
            </select>
          </div>
          <div class="form-group" style="margin:0"><input v-model.number="quarterYear" type="number" class="form-input" style="width:110px" /></div>
        </template>
        <template v-else-if="kind === 'year'">
          <div class="form-group" style="margin:0"><input v-model.number="year" type="number" class="form-input" style="width:110px" /></div>
        </template>
        <template v-else>
          <div class="form-group" style="margin:0"><input v-model="customFrom" type="date" class="form-input" /></div>
          <span class="text-muted">to</span>
          <div class="form-group" style="margin:0"><input v-model="customTo" type="date" class="form-input" /></div>
        </template>
        <div v-if="kind !== 'custom'" class="flex gap-2">
          <button class="btn btn-sm btn-outline" @click="step(-1)">‹ Prev</button>
          <button class="btn btn-sm btn-outline" @click="step(1)">Next ›</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-if="loading && !data" class="loading-spinner">Loading...</div>

    <div v-else-if="data && !data.currencies.length" class="empty-state">
      <h3>Nothing in {{ periodLabel }}</h3>
      <p>No scheduled payments or transactions fall in this period.</p>
    </div>

    <template v-else-if="data">
      <!-- 1. Per currency, as recorded -->
      <div class="card mb-4">
        <div class="card-header"><h3>Spend by currency · {{ periodLabel }}</h3><span class="text-xs text-muted">as recorded, nothing converted</span></div>
        <div class="card-body" style="padding:0">
          <table>
            <thead>
              <tr>
                <th>Currency</th>
                <th class="text-right">Recurring (due)</th>
                <th class="text-right">of which paid</th>
                <th class="text-right">One-off</th>
                <th class="text-right">Total</th>
                <th class="text-right">Items</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in data.currencies" :key="c.currency">
                <td style="font-weight:600">{{ c.currency }}</td>
                <td class="text-right font-mono">{{ money(c.recurring_expected, c.currency) }}</td>
                <td class="text-right font-mono text-sm text-muted">
                  {{ money(c.recurring_paid, c.currency) }}<span v-if="paidShareOf(c) !== null"> ({{ paidShareOf(c).toFixed(0) }}%)</span>
                </td>
                <td class="text-right font-mono">{{ money(c.one_off, c.currency) }}</td>
                <td class="text-right font-mono" style="font-weight:600">{{ money(c.total, c.currency) }}</td>
                <td class="text-right text-sm text-muted">{{ c.recurring_count }} + {{ c.one_off_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 2. Everything in USD -->
      <div v-if="normalised" class="grid-3 mb-4">
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">All currencies in USD · total</p>
            <p class="summary-amount">{{ money(normalised.total, 'USD') }}</p>
            <p class="text-xs text-muted">{{ normalised.recurring_count }} scheduled payment{{ normalised.recurring_count === 1 ? '' : 's' }} + {{ normalised.one_off_count }} transaction{{ normalised.one_off_count === 1 ? '' : 's' }}</p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">Recurring (due in period)</p>
            <p class="summary-amount">{{ money(normalised.recurring_expected, 'USD') }}</p>
            <p class="text-xs text-muted">
              {{ money(normalised.recurring_paid, 'USD') }} paid<span v-if="paidShareOf(normalised) !== null"> ({{ paidShareOf(normalised).toFixed(0) }}%)</span>
            </p>
          </div>
        </div>
        <div class="card">
          <div class="card-body">
            <p class="text-sm text-muted">One-off transactions</p>
            <p class="summary-amount">{{ money(normalised.one_off, 'USD') }}</p>
            <p class="text-xs text-muted">
              {{ parseFloat(normalised.total) > 0 ? ((parseFloat(normalised.one_off) / parseFloat(normalised.total)) * 100).toFixed(0) : 0 }}% of total ·
              <RouterLink to="/transactions" style="color:var(--color-primary); text-decoration:none">view</RouterLink>
            </p>
          </div>
        </div>
      </div>
      <p v-if="normalised" class="text-xs text-muted mb-4" style="margin-top:-0.5rem">
        <span v-if="ratesLine">Rates as of {{ normalised.rate_date }}: {{ ratesLine }}.</span>
        <span v-else-if="data.currencies.length === 1 && !normalised.unconverted.length">Single currency, no conversion needed.</span>
        <span v-if="normalised.unconverted.length" style="color:var(--color-danger)"> No rate available for {{ normalised.unconverted.join(', ') }} — excluded from the USD figures. <RouterLink to="/settings" style="color:inherit">Set one in Settings</RouterLink>.</span>
      </p>

      <!-- 3. Breakdowns for one bucket -->
      <div v-if="current" class="flex items-center gap-2 mb-4" style="justify-content:space-between; flex-wrap:wrap">
        <h3 style="margin:0">Breakdown</h3>
        <div class="form-group" style="margin:0">
          <select v-model="view" class="form-select">
            <option v-if="data.currencies.length > 1" value="USD*">All currencies in USD</option>
            <option v-for="c in data.currencies" :key="c.currency" :value="c.currency">{{ c.currency }} only</option>
          </select>
        </div>
      </div>

      <!-- By month -->
      <div class="card mb-4" v-if="current && current.by_month.length > 1">
        <div class="card-header"><h3>By month</h3><span class="text-xs text-muted">recurring vs one-off · {{ currency }}</span></div>
        <div class="card-body">
          <Bar v-if="chartData" :data="chartData" :options="chartOptions" style="max-height:280px" />
        </div>
      </div>

      <div v-if="current" class="grid-2" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:1rem">
        <!-- By category -->
        <div class="card">
          <div class="card-header"><h3>By category</h3><span class="text-xs text-muted">click a row for its items</span></div>
          <div class="card-body" style="padding:0">
            <table>
              <thead>
                <tr><th>Category</th><th class="text-right">Recurring</th><th class="text-right">One-off</th><th class="text-right">Total</th><th class="text-right">Share</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in current.by_category" :key="row.id || 'none'" style="cursor:pointer" title="Show the items behind this figure" @click="openDrill('category', row)">
                  <td style="font-weight:500; color:var(--color-primary)">{{ row.name }}</td>
                  <td class="text-right font-mono text-sm">{{ parseFloat(row.recurring) ? money(row.recurring) : '—' }}</td>
                  <td class="text-right font-mono text-sm">{{ parseFloat(row.one_off) ? money(row.one_off) : '—' }}</td>
                  <td class="text-right font-mono">{{ money(row.total) }}</td>
                  <td class="text-right text-sm text-muted">{{ row.share.toFixed(1) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- By subject -->
        <div class="card">
          <div class="card-header"><h3>By subject</h3><span class="text-xs text-muted">click a row for its items</span></div>
          <div class="card-body" style="padding:0">
            <table>
              <thead>
                <tr><th>Subject</th><th class="text-right">Recurring</th><th class="text-right">One-off</th><th class="text-right">Total</th><th class="text-right">Share</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in current.by_subject" :key="row.id || 'none'" style="cursor:pointer" title="Show the items behind this figure" @click="openDrill('subject', row)">
                  <td style="font-weight:500; color:var(--color-primary)">{{ row.name }}</td>
                  <td class="text-right font-mono text-sm">{{ parseFloat(row.recurring) ? money(row.recurring) : '—' }}</td>
                  <td class="text-right font-mono text-sm">{{ parseFloat(row.one_off) ? money(row.one_off) : '—' }}</td>
                  <td class="text-right font-mono">{{ money(row.total) }}</td>
                  <td class="text-right text-sm text-muted">{{ row.share.toFixed(1) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Monthly table (always, for exact figures) -->
      <div class="card mt-4" style="margin-top:1rem" v-if="current && current.by_month.length > 1">
        <div class="card-header"><h3>Monthly totals</h3></div>
        <div class="card-body" style="padding:0">
          <table>
            <thead><tr><th>Month</th><th class="text-right">Recurring</th><th class="text-right">One-off</th><th class="text-right">Total</th></tr></thead>
            <tbody>
              <tr v-for="m in current.by_month" :key="m.month">
                <td>{{ monthLabel(m.month) }}</td>
                <td class="text-right font-mono text-sm">{{ money(m.recurring) }}</td>
                <td class="text-right font-mono text-sm">{{ money(m.one_off) }}</td>
                <td class="text-right font-mono">{{ money(m.total) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- Drill-down modal -->
    <div v-if="drill" class="modal-overlay" @click.self="closeDrill">
      <div class="modal" style="max-width:900px; width:95%">
        <div class="modal-header">
          <div>
            <h3>{{ drillTitle }}</h3>
            <p class="text-xs text-muted">
              {{ view === 'USD*' ? 'All currencies, with USD at the period rates' : view + ' only' }}
              · recurring bills due in the period and one-off transactions dated in it
            </p>
          </div>
          <button @click="closeDrill" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body" style="max-height:70vh; overflow:auto; padding:0">
          <div v-if="drillLoading" class="loading-spinner">Loading...</div>
          <div v-else-if="drillError" class="alert alert-danger" style="margin:1rem">{{ drillError }}</div>
          <div v-else-if="drillData && !drillData.items.length" class="empty-state"><p>No items.</p></div>
          <table v-else-if="drillData">
            <thead>
              <tr>
                <th>Date</th>
                <th>Kind</th>
                <th>Item</th>
                <th class="text-right">Amount</th>
                <th v-if="view === 'USD*'" class="text-right">USD</th>
                <th>Status / who</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in drillData.items" :key="item.kind + item.id">
                <td class="text-sm" style="white-space:nowrap">{{ itemDate(item.date) }}</td>
                <td><span :class="['badge', item.kind === 'recurring' ? 'badge-pending' : 'badge-paid']">{{ item.kind === 'recurring' ? 'Recurring' : 'One-off' }}</span></td>
                <td>
                  <RouterLink v-if="item.kind === 'recurring'" :to="`/expenses/${item.expense_id}`" style="color:var(--color-primary); text-decoration:none; font-weight:500">{{ item.name }}</RouterLink>
                  <RouterLink v-else to="/transactions" style="color:var(--color-primary); text-decoration:none; font-weight:500">{{ item.name }}</RouterLink>
                  <p class="text-xs text-muted">
                    <span v-if="item.subject">{{ item.subject }}</span>
                    <span v-if="item.subject && item.payment_method"> · </span>
                    <span v-if="item.payment_method">{{ item.payment_method }}</span>
                    <span v-if="item.notes"> · {{ item.notes }}</span>
                  </p>
                </td>
                <td class="text-right font-mono">{{ money(item.amount, item.currency) }}</td>
                <td v-if="view === 'USD*'" class="text-right font-mono text-sm">{{ item.amount_usd != null ? money(item.amount_usd, 'USD') : '—' }}</td>
                <td class="text-sm">
                  <template v-if="item.kind === 'recurring'">
                    <span :class="['badge', 'badge-' + item.status]">{{ item.status }}</span>
                    <span v-if="parseFloat(item.paid) > 0" class="text-xs text-muted"> {{ money(item.paid, item.currency) }} paid</span>
                  </template>
                  <template v-else>{{ item.paid_by || '—' }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="drillData && drillData.items.length" class="modal-footer" style="justify-content:space-between; flex-wrap:wrap; gap:0.5rem">
          <span class="text-sm text-muted">{{ drillData.count }} item{{ drillData.count === 1 ? '' : 's' }}</span>
          <span class="text-sm font-mono">
            <span v-for="(total, cur) in drillData.totals" :key="cur" style="margin-left:0.75rem">{{ money(total, cur) }}</span>
            <span v-if="drillData.total_usd != null" style="margin-left:0.75rem; font-weight:600">= {{ money(drillData.total_usd, 'USD') }}</span>
            <span v-if="drillData.unconverted && drillData.unconverted.length" class="text-xs" style="color:var(--color-danger); margin-left:0.5rem">({{ drillData.unconverted.join(', ') }} not converted)</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useExpenseStore } from '../stores/expenses'
import { useAgentStore } from '../stores/agents'
import api from '../api/axios'

const auth = useAuthStore()
const store = useExpenseStore()
const agents = useAgentStore()

const form = ref({
  first_name: '',
  last_name: '',
  username: '',
})
const success = ref('')
const error = ref('')
const loading = ref(false)

// Subject management
const showSubjectForm = ref(false)
const editingSubjectId = ref(null)
const subjectForm = ref({ name: '' })
const subjectError = ref('')

// Expense Type management
const showTypeForm = ref(false)
const editingTypeId = ref(null)
const typeForm = ref({ name: '' })
const typeError = ref('')

// Payment Method management
const showMethodForm = ref(false)
const editingMethodId = ref(null)
const methodForm = ref({ name: '', requires_account: false })
const methodError = ref('')

// Payment Account management
const showAccountForm = ref(false)
const editingAccountId = ref(null)
const accountForm = ref({ name: '', notes: '' })
const accountError = ref('')

// Agent Access (MCP) + Assignment prompt
const newTokenName = ref('')
const tokenBusyMcp = ref(false)
const tokenResult = ref(null) // { token, connector_url, name } shown once after minting
const agentError = ref('')
const agentSuccess = ref('')
const urlCopyState = ref('')
const assignmentTemplateDraft = ref('')
const savingAssignmentTemplate = ref(false)

// Agent Import
const importConfig = ref(null)
const templateDraft = ref('')
const importError = ref('')
const importSuccess = ref('')
const tokenBusy = ref(false)
const savingTemplate = ref(false)

onMounted(() => {
  if (auth.user) {
    form.value.first_name = auth.user.first_name || ''
    form.value.last_name = auth.user.last_name || ''
    form.value.username = auth.user.username || ''
  }
  store.fetchSubjects()
  store.fetchExpenseTypes()
  store.fetchPaymentMethods()
  store.fetchPaymentAccounts()
  fetchImportConfig()
  agents.fetchTokens().catch(() => { agentError.value = 'Failed to load MCP tokens.' })
  agents.fetchConfig()
    .then((cfg) => { assignmentTemplateDraft.value = cfg.assignment_template })
    .catch(() => { agentError.value = 'Failed to load assignment prompt settings.' })
})

async function handleSave() {
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    await api.patch('auth/me/', form.value)
    await auth.fetchUser()
    success.value = 'Profile updated successfully.'
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      error.value = Object.values(data).flat().join(' ')
    } else {
      error.value = 'Failed to update profile.'
    }
  } finally {
    loading.value = false
  }
}

// Subject CRUD
function openCreateSubject() {
  editingSubjectId.value = null
  subjectForm.value = { name: '' }
  subjectError.value = ''
  showSubjectForm.value = true
}

function openEditSubject(subject) {
  editingSubjectId.value = subject.id
  subjectForm.value = { name: subject.name }
  subjectError.value = ''
  showSubjectForm.value = true
}

async function handleSubjectSubmit() {
  subjectError.value = ''
  try {
    if (editingSubjectId.value) {
      await store.updateSubject(editingSubjectId.value, subjectForm.value)
    } else {
      await store.createSubject(subjectForm.value)
    }
    showSubjectForm.value = false
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      subjectError.value = Object.values(data).flat().join(' ')
    } else {
      subjectError.value = 'Failed to save subject.'
    }
  }
}

async function handleDeleteSubject(subject) {
  if (!confirm(`Delete subject "${subject.name}"?`)) return
  try {
    await store.deleteSubject(subject.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Cannot delete this subject.')
  }
}

// Expense Type CRUD
function openCreateType() {
  editingTypeId.value = null
  typeForm.value = { name: '' }
  typeError.value = ''
  showTypeForm.value = true
}

function openEditType(type) {
  editingTypeId.value = type.id
  typeForm.value = { name: type.name }
  typeError.value = ''
  showTypeForm.value = true
}

async function handleTypeSubmit() {
  typeError.value = ''
  try {
    if (editingTypeId.value) {
      await store.updateExpenseType(editingTypeId.value, typeForm.value)
    } else {
      await store.createExpenseType(typeForm.value)
    }
    showTypeForm.value = false
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      typeError.value = Object.values(data).flat().join(' ')
    } else {
      typeError.value = 'Failed to save expense type.'
    }
  }
}

async function handleDeleteType(type) {
  if (!confirm(`Delete expense type "${type.name}"?`)) return
  try {
    await store.deleteExpenseType(type.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Cannot delete this expense type.')
  }
}

// Payment Method CRUD
function openCreateMethod() {
  editingMethodId.value = null
  methodForm.value = { name: '', requires_account: false }
  methodError.value = ''
  showMethodForm.value = true
}

function openEditMethod(method) {
  editingMethodId.value = method.id
  methodForm.value = { name: method.name, requires_account: method.requires_account }
  methodError.value = ''
  showMethodForm.value = true
}

async function handleMethodSubmit() {
  methodError.value = ''
  try {
    if (editingMethodId.value) {
      await store.updatePaymentMethod(editingMethodId.value, methodForm.value)
    } else {
      await store.createPaymentMethod(methodForm.value)
    }
    showMethodForm.value = false
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      methodError.value = Object.values(data).flat().join(' ')
    } else {
      methodError.value = 'Failed to save payment method.'
    }
  }
}

async function handleDeleteMethod(method) {
  if (!confirm(`Delete payment method "${method.name}"?`)) return
  try {
    await store.deletePaymentMethod(method.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Cannot delete this payment method.')
  }
}

// Payment Account CRUD
function openCreateAccount() {
  editingAccountId.value = null
  accountForm.value = { name: '', notes: '' }
  accountError.value = ''
  showAccountForm.value = true
}

function openEditAccount(account) {
  editingAccountId.value = account.id
  accountForm.value = { name: account.name, notes: account.notes || '' }
  accountError.value = ''
  showAccountForm.value = true
}

async function handleAccountSubmit() {
  accountError.value = ''
  try {
    if (editingAccountId.value) {
      await store.updatePaymentAccount(editingAccountId.value, accountForm.value)
    } else {
      await store.createPaymentAccount(accountForm.value)
    }
    showAccountForm.value = false
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      accountError.value = Object.values(data).flat().join(' ')
    } else {
      accountError.value = 'Failed to save account.'
    }
  }
}

async function handleDeleteAccount(account) {
  if (!confirm(`Delete account "${account.name}"?`)) return
  try {
    await store.deletePaymentAccount(account.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Cannot delete this account.')
  }
}

// Agent Access (MCP)
async function createMcpToken() {
  const name = newTokenName.value.trim()
  if (!name) { agentError.value = 'Give the token a name (e.g. "claude.ai" or "Claude Code").'; return }
  agentError.value = ''
  agentSuccess.value = ''
  tokenBusyMcp.value = true
  try {
    tokenResult.value = await agents.createToken(name)
    newTokenName.value = ''
    urlCopyState.value = ''
  } catch (e) {
    agentError.value = e.response?.data?.name?.[0] || 'Failed to create token.'
  } finally {
    tokenBusyMcp.value = false
  }
}

async function revokeMcpToken(token) {
  if (!confirm(`Revoke "${token.name}"? Any client using it loses access immediately.`)) return
  agentError.value = ''
  try {
    await agents.revokeToken(token.id)
    if (tokenResult.value?.id === token.id) tokenResult.value = null
    agentSuccess.value = `Token "${token.name}" revoked.`
  } catch {
    agentError.value = 'Failed to revoke token.'
  }
}

async function copyConnectorUrl() {
  try {
    await navigator.clipboard.writeText(tokenResult.value.connector_url)
    urlCopyState.value = 'copied'
    setTimeout(() => { if (urlCopyState.value === 'copied') urlCopyState.value = '' }, 2500)
  } catch {
    urlCopyState.value = 'manual'
  }
}

function claudeCodeCommand() {
  return tokenResult.value ? `claude mcp add --transport http hestia ${tokenResult.value.connector_url}` : ''
}

async function saveAssignmentTemplate() {
  agentError.value = ''
  agentSuccess.value = ''
  savingAssignmentTemplate.value = true
  try {
    const cfg = await agents.saveTemplate(assignmentTemplateDraft.value)
    assignmentTemplateDraft.value = cfg.assignment_template
    agentSuccess.value = 'Assignment prompt template saved.'
  } catch {
    agentError.value = 'Failed to save assignment template.'
  } finally {
    savingAssignmentTemplate.value = false
  }
}

async function resetAssignmentTemplate() {
  if (!confirm('Reset the assignment prompt template to the system default?')) return
  agentError.value = ''
  agentSuccess.value = ''
  savingAssignmentTemplate.value = true
  try {
    const cfg = await agents.saveTemplate('')
    assignmentTemplateDraft.value = cfg.assignment_template
    agentSuccess.value = 'Assignment prompt template reset to default.'
  } catch {
    agentError.value = 'Failed to reset assignment template.'
  } finally {
    savingAssignmentTemplate.value = false
  }
}

// Agent Import
function varTag(name) {
  // Render a literal {{placeholder}} without tripping Vue's template parser.
  return `{{${name}}}`
}

async function fetchImportConfig(syncDraft = true) {
  try {
    const { data } = await api.get('agent-import/config/')
    importConfig.value = data
    if (syncDraft) templateDraft.value = data.prompt_template
  } catch {
    importError.value = 'Failed to load agent import settings.'
  }
}

async function generateToken() {
  importError.value = ''
  importSuccess.value = ''
  tokenBusy.value = true
  try {
    await api.post('agent-import/token/')
    await fetchImportConfig(false)
    importSuccess.value = 'Import token generated. Copy the prompt below to use it.'
  } catch {
    importError.value = 'Failed to generate token.'
  } finally {
    tokenBusy.value = false
  }
}

async function revokeToken() {
  if (!confirm('Revoke the current import token? Any prompt already shared will stop working.')) return
  importError.value = ''
  importSuccess.value = ''
  tokenBusy.value = true
  try {
    await api.delete('agent-import/token/')
    await fetchImportConfig(false)
    importSuccess.value = 'Import token revoked.'
  } catch {
    importError.value = 'Failed to revoke token.'
  } finally {
    tokenBusy.value = false
  }
}

async function saveTemplate() {
  importError.value = ''
  importSuccess.value = ''
  savingTemplate.value = true
  try {
    await api.patch('agent-import/config/', { prompt_template: templateDraft.value })
    await fetchImportConfig(true)
    importSuccess.value = 'Prompt template saved.'
  } catch {
    importError.value = 'Failed to save template.'
  } finally {
    savingTemplate.value = false
  }
}

async function resetTemplate() {
  if (!confirm('Reset the prompt template to the system default?')) return
  importError.value = ''
  importSuccess.value = ''
  savingTemplate.value = true
  try {
    await api.patch('agent-import/config/', { prompt_template: '' })
    await fetchImportConfig(true)
    importSuccess.value = 'Prompt template reset to default.'
  } catch {
    importError.value = 'Failed to reset template.'
  } finally {
    savingTemplate.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Settings</h1>
    </div>

    <!-- Profile -->
    <div class="card mb-4" style="max-width: 600px">
      <div class="card-header">
        <h3>Profile</h3>
      </div>
      <div class="card-body">
        <div v-if="success" class="alert alert-success">{{ success }}</div>
        <div v-if="error" class="alert alert-danger">{{ error }}</div>

        <form @submit.prevent="handleSave">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">First Name</label>
              <input v-model="form.first_name" type="text" class="form-input" />
            </div>
            <div class="form-group">
              <label class="form-label">Last Name</label>
              <input v-model="form.last_name" type="text" class="form-input" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="form.username" type="text" class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input :value="auth.user?.email" type="email" class="form-input" disabled />
            <p class="text-xs text-muted mt-1">Email cannot be changed.</p>
          </div>
          <button type="submit" class="btn btn-primary" :disabled="loading">
            {{ loading ? 'Saving...' : 'Save Changes' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Subjects -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Subjects</h3>
        <button @click="openCreateSubject" class="btn btn-sm btn-primary">+ New Subject</button>
      </div>
      <div class="card-body" style="padding:0">
        <div v-if="!store.subjects.length" class="empty-state">
          <p>No subjects configured yet. Add subjects like apartments, cars, etc.</p>
        </div>
        <table v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="subject in store.subjects" :key="subject.id">
              <td style="font-weight:500">{{ subject.name }}</td>
              <td>
                <span class="text-sm text-muted">{{ subject.is_default ? 'Default' : 'Custom' }}</span>
              </td>
              <td class="text-right">
                <button @click="openEditSubject(subject)" class="btn btn-sm btn-outline">Edit</button>
                <button v-if="!subject.is_default" @click="handleDeleteSubject(subject)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Expense Types -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Expense Types</h3>
        <button @click="openCreateType" class="btn btn-sm btn-primary">+ New Type</button>
      </div>
      <div class="card-body" style="padding:0">
        <div v-if="!store.expenseTypes.length" class="empty-state">
          <p>No expense types configured yet.</p>
        </div>
        <table v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="et in store.expenseTypes" :key="et.id">
              <td style="font-weight:500">{{ et.name }}</td>
              <td>
                <span class="text-sm text-muted">{{ et.is_default ? 'Default' : 'Custom' }}</span>
              </td>
              <td class="text-right">
                <button @click="openEditType(et)" class="btn btn-sm btn-outline">Edit</button>
                <button v-if="!et.is_default" @click="handleDeleteType(et)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Payment Methods -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Payment Methods</h3>
        <button @click="openCreateMethod" class="btn btn-sm btn-primary">+ New Method</button>
      </div>
      <div class="card-body" style="padding:0">
        <div v-if="!store.paymentMethods.length" class="empty-state">
          <p>No payment methods configured yet. Add how bills get paid: cash, card, direct debit, etc.</p>
        </div>
        <table v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Uses an account</th>
              <th>Type</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in store.paymentMethods" :key="m.id">
              <td style="font-weight:500">{{ m.name }}</td>
              <td class="text-sm">{{ m.requires_account ? 'Yes' : 'No' }}</td>
              <td>
                <span class="text-sm text-muted">{{ m.is_default ? 'Default' : 'Custom' }}</span>
              </td>
              <td class="text-right">
                <button @click="openEditMethod(m)" class="btn btn-sm btn-outline">Edit</button>
                <button v-if="!m.is_default" @click="handleDeleteMethod(m)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Accounts -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Accounts</h3>
        <button @click="openCreateAccount" class="btn btn-sm btn-primary">+ New Account</button>
      </div>
      <div class="card-body" style="padding:0">
        <div v-if="!store.paymentAccounts.length" class="empty-state">
          <p>No accounts configured yet. Add the bank accounts and cards that direct debits and card payments come from.</p>
        </div>
        <table v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Notes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in store.paymentAccounts" :key="a.id">
              <td style="font-weight:500">{{ a.name }}</td>
              <td class="text-sm text-muted">{{ a.notes || '—' }}</td>
              <td class="text-right">
                <button @click="openEditAccount(a)" class="btn btn-sm btn-outline">Edit</button>
                <button @click="handleDeleteAccount(a)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Agent Import -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent Import</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Token and prompt template for the bill-import agent. The prompt asks the agent to upload a bill,
          reads it, picks the matching subject, type and payment details, lets you confirm, then submits the
          expense to Hestia. Copy the prompt itself from the Dashboard.
        </p>

        <div v-if="importSuccess" class="alert alert-success">{{ importSuccess }}</div>
        <div v-if="importError" class="alert alert-danger">{{ importError }}</div>

        <!-- Submission token -->
        <div class="form-group">
          <label class="form-label">Submission token</label>
          <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            <code
              v-if="importConfig?.has_token"
              style="background:var(--color-gray-100,#f3f4f6); padding:0.25rem 0.5rem; border-radius:0.375rem; font-size:0.8125rem"
            >{{ importConfig.token_masked }}</code>
            <span v-else class="text-sm text-muted">No token yet — generate one to enable import.</span>
            <button class="btn btn-sm btn-primary" :disabled="tokenBusy" @click="generateToken">
              {{ importConfig?.has_token ? 'Regenerate' : 'Generate token' }}
            </button>
            <button
              v-if="importConfig?.has_token"
              class="btn btn-sm btn-outline"
              :disabled="tokenBusy"
              style="color:var(--color-danger)"
              @click="revokeToken"
            >
              Revoke
            </button>
          </div>
          <p class="text-xs text-muted mt-1">
            Scoped to creating expenses only — it can't read your data or change your account. The prompt
            embeds this token, so treat it as a secret and revoke it if it leaks.
          </p>
        </div>

        <!-- Prompt template -->
        <div class="form-group">
          <label class="form-label">Prompt template</label>
          <textarea
            v-model="templateDraft"
            class="form-input"
            rows="10"
            spellcheck="false"
            style="font-family:'SF Mono',Monaco,monospace; font-size:0.8125rem"
          ></textarea>
          <p class="text-xs text-muted mt-1">
            Variables filled in automatically:
            <code
              v-for="v in importConfig?.template_variables || []"
              :key="v"
              style="background:var(--color-gray-100,#f3f4f6); padding:0.0625rem 0.375rem; border-radius:0.25rem; margin-right:0.25rem; font-size:0.75rem"
            >{{ varTag(v) }}</code>
          </p>
          <div class="flex gap-2" style="margin-top:0.5rem">
            <button class="btn btn-sm btn-primary" :disabled="savingTemplate" @click="saveTemplate">
              {{ savingTemplate ? 'Saving...' : 'Save template' }}
            </button>
            <button class="btn btn-sm btn-outline" :disabled="savingTemplate" @click="resetTemplate">
              Reset to default
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- Agent Access (MCP) -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent Access (MCP)</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Let an AI agent read and change Hestia directly: list and edit expenses, maintain the
          dictionaries, and save assignment deliverables. Each token is a connector URL for one client.
          Anything the agent creates is attributed to you.
        </p>

        <div v-if="agentSuccess" class="alert alert-success">{{ agentSuccess }}</div>
        <div v-if="agentError" class="alert alert-danger">{{ agentError }}</div>

        <!-- One-time reveal -->
        <div v-if="tokenResult" class="alert alert-success" style="display:block">
          <p class="text-sm" style="font-weight:600; margin-bottom:0.5rem">
            Token "{{ tokenResult.name }}" created. Copy the connector URL now — it is not shown again.
          </p>
          <div class="flex gap-2 items-center" style="flex-wrap:wrap; margin-bottom:0.5rem">
            <code style="background:var(--color-gray-100,#f3f4f6); padding:0.25rem 0.5rem; border-radius:0.375rem; font-size:0.75rem; word-break:break-all">{{ tokenResult.connector_url }}</code>
            <button class="btn btn-sm btn-primary" @click="copyConnectorUrl">
              {{ urlCopyState === 'copied' ? '✓ Copied' : 'Copy URL' }}
            </button>
          </div>
          <p v-if="urlCopyState === 'manual'" class="text-xs text-muted">Clipboard blocked — select and copy the URL above.</p>
          <p class="text-xs" style="margin-top:0.5rem"><strong>claude.ai:</strong> Settings → Connectors → Add custom connector → paste the URL (no OAuth needed).</p>
          <p class="text-xs"><strong>Claude Code:</strong></p>
          <code style="display:block; background:var(--color-gray-100,#f3f4f6); padding:0.25rem 0.5rem; border-radius:0.375rem; font-size:0.75rem; word-break:break-all">{{ claudeCodeCommand() }}</code>
          <button class="btn btn-sm btn-outline" style="margin-top:0.5rem" @click="tokenResult = null">Dismiss</button>
        </div>

        <!-- Existing tokens -->
        <div class="form-group">
          <label class="form-label">Tokens</label>
          <p v-if="!agents.tokens.length" class="text-sm text-muted">No tokens yet.</p>
          <table v-else>
            <thead>
              <tr>
                <th>Client</th>
                <th>Token</th>
                <th>Created</th>
                <th>Last used</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in agents.tokens" :key="t.id">
                <td style="font-weight:500">{{ t.name }}</td>
                <td><code style="font-size:0.75rem">{{ t.token_masked }}</code></td>
                <td class="text-sm text-muted">{{ t.created_at.slice(0, 10) }}</td>
                <td class="text-sm text-muted">{{ t.last_used_at ? t.last_used_at.slice(0, 16).replace('T', ' ') : 'never' }}</td>
                <td class="text-right">
                  <button class="btn btn-sm btn-outline" style="color:var(--color-danger)" @click="revokeMcpToken(t)">Revoke</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- New token -->
        <div class="form-group" style="margin-bottom:0">
          <label class="form-label">New token</label>
          <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            <input v-model="newTokenName" type="text" class="form-input" style="max-width:280px" placeholder='Client name, e.g. "claude.ai"' @keyup.enter="createMcpToken" />
            <button class="btn btn-sm btn-primary" :disabled="tokenBusyMcp" @click="createMcpToken">
              {{ tokenBusyMcp ? 'Creating…' : 'Create token' }}
            </button>
          </div>
          <p class="text-xs text-muted mt-1">
            One token per client makes revoking painless. Treat the URL as a secret: anyone holding it can read and change your expenses.
          </p>
        </div>
      </div>
    </div>

    <!-- Assignment prompt -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Assignment Prompt</h3>
        <RouterLink to="/assignments" class="btn btn-sm btn-outline">Open Assignments</RouterLink>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Template for the prompt copied when you start a new assignment from the Dashboard or the Assignments
          page. It frames the agent as a practitioner producing a specific deliverable, points it at the MCP
          tools above for context and changes, and tells it how to save the result back here.
        </p>
        <div class="form-group" style="margin-bottom:0">
          <textarea
            v-model="assignmentTemplateDraft"
            class="form-input"
            rows="12"
            spellcheck="false"
            style="font-family:'SF Mono',Monaco,monospace; font-size:0.8125rem"
          ></textarea>
          <p class="text-xs text-muted mt-1">
            Variables filled in automatically:
            <code
              v-for="v in agents.config?.template_variables || []"
              :key="v"
              style="background:var(--color-gray-100,#f3f4f6); padding:0.0625rem 0.375rem; border-radius:0.25rem; margin-right:0.25rem; font-size:0.75rem"
            >{{ varTag(v) }}</code>
          </p>
          <div class="flex gap-2" style="margin-top:0.5rem">
            <button class="btn btn-sm btn-primary" :disabled="savingAssignmentTemplate" @click="saveAssignmentTemplate">
              {{ savingAssignmentTemplate ? 'Saving...' : 'Save template' }}
            </button>
            <button class="btn btn-sm btn-outline" :disabled="savingAssignmentTemplate" @click="resetAssignmentTemplate">
              Reset to default
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Subject Form Modal -->
    <div v-if="showSubjectForm" class="modal-overlay" @click.self="showSubjectForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingSubjectId ? 'Edit Subject' : 'New Subject' }}</h3>
          <button @click="showSubjectForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="subjectError" class="alert alert-danger">{{ subjectError }}</div>
          <form @submit.prevent="handleSubjectSubmit">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="subjectForm.name" type="text" class="form-input" placeholder="e.g. 42 Oak Street, Toyota Corolla" required />
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showSubjectForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary">
                {{ editingSubjectId ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Payment Method Form Modal -->
    <div v-if="showMethodForm" class="modal-overlay" @click.self="showMethodForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingMethodId ? 'Edit Payment Method' : 'New Payment Method' }}</h3>
          <button @click="showMethodForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="methodError" class="alert alert-danger">{{ methodError }}</div>
          <form @submit.prevent="handleMethodSubmit">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="methodForm.name" type="text" class="form-input" placeholder="e.g. Cheque, PayPal" required />
            </div>
            <div class="form-group">
              <label class="form-label" style="display:flex; align-items:center; gap:0.5rem; cursor:pointer">
                <input v-model="methodForm.requires_account" type="checkbox" />
                Paid from a specific account
              </label>
              <p class="text-xs text-muted mt-1">
                Tick for card, direct debit, and similar. Expenses using this method can then record which account they come from.
              </p>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showMethodForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary">
                {{ editingMethodId ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Account Form Modal -->
    <div v-if="showAccountForm" class="modal-overlay" @click.self="showAccountForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingAccountId ? 'Edit Account' : 'New Account' }}</h3>
          <button @click="showAccountForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="accountError" class="alert alert-danger">{{ accountError }}</div>
          <form @submit.prevent="handleAccountSubmit">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="accountForm.name" type="text" class="form-input" placeholder="e.g. Joint current account, Amex" required />
            </div>
            <div class="form-group">
              <label class="form-label">Notes <span class="text-muted text-xs">(optional)</span></label>
              <textarea v-model="accountForm.notes" class="form-textarea" placeholder="e.g. Bills account, topped up on the 1st"></textarea>
              <p class="text-xs text-muted mt-1">Don't store account or card numbers here.</p>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showAccountForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary">
                {{ editingAccountId ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Expense Type Form Modal -->
    <div v-if="showTypeForm" class="modal-overlay" @click.self="showTypeForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingTypeId ? 'Edit Expense Type' : 'New Expense Type' }}</h3>
          <button @click="showTypeForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="typeError" class="alert alert-danger">{{ typeError }}</div>
          <form @submit.prevent="handleTypeSubmit">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="typeForm.name" type="text" class="form-input" placeholder="e.g. Insurance, Subscription" required />
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showTypeForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary">
                {{ editingTypeId ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

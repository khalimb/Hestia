<script setup>
import { ref, computed, onMounted } from 'vue'
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

// Members + invites (admin manages; everyone can see the list)
const members = ref([])
const invites = ref([])
const memberError = ref('')
const memberSuccess = ref('')
const memberBusy = ref(false)
const isAdmin = computed(() => !!auth.user?.is_staff)
const showMemberForm = ref(false)
const memberForm = ref({ email: '', first_name: '', last_name: '', password: '', is_staff: false })
const showPasswordForm = ref(false)
const passwordTarget = ref(null)
const passwordForm = ref({ password: '' })
const inviteForm = ref({ email: '', note: '', make_admin: false })
const inviteResult = ref(null)   // { link, email } shown once after minting
const inviteCopyState = ref('')

// Exchange rates (manual overrides)
const fxRates = ref([])
const fxForm = ref({ currency: '', units_per_usd: '', note: '' })
const fxError = ref('')
const fxSuccess = ref('')
const fxBusy = ref(false)

// Agent Access (MCP) + agent prompt template
const newTokenName = ref('')
const tokenBusyMcp = ref(false)
const tokenResult = ref(null) // { token, connector_url, name } shown once after minting
const agentError = ref('')
const agentSuccess = ref('')
const urlCopyState = ref('')
const promptTemplateDraft = ref('')
const savingPromptTemplate = ref(false)

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
  fetchMembers()
  fetchFxRates()
  agents.fetchTokens().catch(() => { agentError.value = 'Failed to load MCP tokens.' })
  agents.fetchConfig()
    .then((cfg) => { promptTemplateDraft.value = cfg.prompt_template })
    .catch(() => { agentError.value = 'Failed to load agent prompt settings.' })
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

// Members + invites
function memberErrorText(e, fallback) {
  const data = e.response?.data
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}

async function fetchMembers() {
  try {
    const { data } = await api.get('auth/members/')
    members.value = data
    if (isAdmin.value) {
      const res = await api.get('auth/invites/')
      invites.value = res.data
    }
  } catch {
    memberError.value = 'Failed to load members.'
  }
}

function openCreateMember() {
  memberForm.value = { email: '', first_name: '', last_name: '', password: '', is_staff: false }
  memberError.value = ''
  showMemberForm.value = true
}

async function submitMember() {
  memberError.value = ''
  memberSuccess.value = ''
  memberBusy.value = true
  try {
    const { data } = await api.post('auth/members/', memberForm.value)
    showMemberForm.value = false
    memberSuccess.value = `Account created for ${data.display_name} (${data.email}). Give them the temporary password you set; they can change it in their profile.`
    await fetchMembers()
  } catch (e) {
    memberError.value = memberErrorText(e, 'Failed to create member.')
  } finally {
    memberBusy.value = false
  }
}

async function patchMember(member, changes, confirmText) {
  if (confirmText && !confirm(confirmText)) return
  memberError.value = ''
  memberSuccess.value = ''
  try {
    await api.patch(`auth/members/${member.id}/`, changes)
    await fetchMembers()
    if (member.id === auth.user?.id) await auth.fetchUser()
  } catch (e) {
    memberError.value = memberErrorText(e, 'Failed to update member.')
  }
}

function openPasswordForm(member) {
  passwordTarget.value = member
  passwordForm.value = { password: '' }
  memberError.value = ''
  showPasswordForm.value = true
}

async function submitPassword() {
  memberError.value = ''
  memberSuccess.value = ''
  memberBusy.value = true
  try {
    const { data } = await api.post(`auth/members/${passwordTarget.value.id}/password/`, passwordForm.value)
    showPasswordForm.value = false
    memberSuccess.value = data.detail
  } catch (e) {
    memberError.value = memberErrorText(e, 'Failed to set password.')
  } finally {
    memberBusy.value = false
  }
}

async function createInvite() {
  memberError.value = ''
  memberSuccess.value = ''
  memberBusy.value = true
  try {
    const { data } = await api.post('auth/invites/', inviteForm.value)
    inviteResult.value = data
    inviteCopyState.value = ''
    inviteForm.value = { email: '', note: '', make_admin: false }
    await fetchMembers()
  } catch (e) {
    memberError.value = memberErrorText(e, 'Failed to create invite.')
  } finally {
    memberBusy.value = false
  }
}

async function copyInviteLink() {
  try {
    await navigator.clipboard.writeText(inviteResult.value.link)
    inviteCopyState.value = 'copied'
    setTimeout(() => { if (inviteCopyState.value === 'copied') inviteCopyState.value = '' }, 2500)
  } catch {
    inviteCopyState.value = 'manual'
  }
}

async function revokeInvite(invite) {
  if (!confirm(`Revoke the invite${invite.note ? ' for ' + invite.note : ''}?`)) return
  try {
    await api.delete(`auth/invites/${invite.id}/`)
    invites.value = invites.value.filter((i) => i.id !== invite.id)
  } catch {
    memberError.value = 'Failed to revoke invite.'
  }
}

function formatWhen(iso) {
  return iso ? iso.slice(0, 16).replace('T', ' ') : 'never'
}

// Exchange rates
async function fetchFxRates() {
  try {
    const { data } = await api.get('fx/manual/')
    fxRates.value = data
  } catch {
    fxError.value = 'Failed to load exchange rates.'
  }
}

async function saveFxRate() {
  fxError.value = ''
  fxSuccess.value = ''
  fxBusy.value = true
  try {
    const payload = {
      currency: fxForm.value.currency.trim().toUpperCase(),
      units_per_usd: parseFloat(fxForm.value.units_per_usd),
      note: fxForm.value.note,
    }
    await api.post('fx/manual/', payload)
    fxSuccess.value = `Rate for ${payload.currency} saved. It now overrides the feeds for that currency.`
    fxForm.value = { currency: '', units_per_usd: '', note: '' }
    await fetchFxRates()
  } catch (e) {
    const data = e.response?.data
    fxError.value = data && typeof data === 'object' ? Object.values(data).flat().join(' ') : 'Failed to save rate.'
  } finally {
    fxBusy.value = false
  }
}

async function deleteFxRate(rate) {
  if (!confirm(`Remove the manual rate for ${rate.currency}? The feeds will be used again.`)) return
  fxError.value = ''
  try {
    await api.delete(`fx/manual/${rate.currency}/`)
    fxRates.value = fxRates.value.filter((r) => r.currency !== rate.currency)
  } catch {
    fxError.value = 'Failed to remove rate.'
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

async function savePromptTemplate() {
  agentError.value = ''
  agentSuccess.value = ''
  savingPromptTemplate.value = true
  try {
    const cfg = await agents.saveTemplate(promptTemplateDraft.value)
    promptTemplateDraft.value = cfg.prompt_template
    agentSuccess.value = 'Agent prompt template saved.'
  } catch {
    agentError.value = 'Failed to save the agent prompt template.'
  } finally {
    savingPromptTemplate.value = false
  }
}

async function resetPromptTemplate() {
  if (!confirm('Reset the agent prompt template to the system default?')) return
  agentError.value = ''
  agentSuccess.value = ''
  savingPromptTemplate.value = true
  try {
    const cfg = await agents.saveTemplate('')
    promptTemplateDraft.value = cfg.prompt_template
    agentSuccess.value = 'Agent prompt template reset to default.'
  } catch {
    agentError.value = 'Failed to reset the agent prompt template.'
  } finally {
    savingPromptTemplate.value = false
  }
}

// Render a literal {{placeholder}} without tripping Vue's template parser.
function varTag(name) {
  return `{{${name}}}`
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

    <!-- Members -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Members</h3>
        <div v-if="isAdmin" class="flex gap-2">
          <button class="btn btn-sm btn-primary" @click="openCreateMember">+ Add member</button>
        </div>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Everyone here shares the household's expenses, transactions and dictionaries, and every change is
          attributed to the person who made it. Registration is by invitation only.
          <template v-if="!isAdmin"> Ask an admin to add someone or send an invite link.</template>
        </p>
        <div v-if="memberSuccess" class="alert alert-success">{{ memberSuccess }}</div>
        <div v-if="memberError" class="alert alert-danger">{{ memberError }}</div>

        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Last login</th>
              <th v-if="isAdmin"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in members" :key="m.id" :style="m.is_active ? '' : 'opacity:0.55'">
              <td style="font-weight:500">
                {{ m.display_name }}
                <span v-if="m.id === auth.user?.id" class="text-xs text-muted">(you)</span>
              </td>
              <td class="text-sm">{{ m.email }}</td>
              <td>
                <span :class="['badge', m.is_active ? (m.is_staff ? 'badge-paid' : 'badge-pending') : 'badge-overdue']">
                  {{ !m.is_active ? 'Deactivated' : (m.is_staff ? 'Admin' : 'Member') }}
                </span>
              </td>
              <td class="text-sm text-muted">{{ formatWhen(m.last_login) }}</td>
              <td v-if="isAdmin" class="text-right" style="white-space:nowrap">
                <template v-if="m.id !== auth.user?.id">
                  <button v-if="m.is_active" class="btn btn-sm btn-outline" @click="patchMember(m, { is_staff: !m.is_staff })">
                    {{ m.is_staff ? 'Remove admin' : 'Make admin' }}
                  </button>
                  <button class="btn btn-sm btn-outline" style="margin-left:0.25rem" @click="openPasswordForm(m)">Reset password</button>
                  <button v-if="m.is_active" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)"
                          @click="patchMember(m, { is_active: false }, `Deactivate ${m.display_name}? They will no longer be able to sign in; their records stay.`)">Deactivate</button>
                  <button v-else class="btn btn-sm btn-outline" style="margin-left:0.25rem" @click="patchMember(m, { is_active: true })">Reactivate</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Invites (admin) -->
        <div v-if="isAdmin" class="form-group" style="margin-top:1.25rem; margin-bottom:0">
          <label class="form-label">Invite link</label>
          <div v-if="inviteResult" class="alert alert-success" style="display:block">
            <p class="text-sm" style="font-weight:600; margin-bottom:0.5rem">Invite created{{ inviteResult.email ? ' for ' + inviteResult.email : '' }}. Send this link — it works once and expires in 7 days.</p>
            <div class="flex gap-2 items-center" style="flex-wrap:wrap">
              <code style="background:var(--color-gray-100,#f3f4f6); padding:0.25rem 0.5rem; border-radius:0.375rem; font-size:0.75rem; word-break:break-all">{{ inviteResult.link }}</code>
              <button class="btn btn-sm btn-primary" @click="copyInviteLink">{{ inviteCopyState === 'copied' ? '✓ Copied' : 'Copy link' }}</button>
              <button class="btn btn-sm btn-outline" @click="inviteResult = null">Dismiss</button>
            </div>
            <p v-if="inviteCopyState === 'manual'" class="text-xs text-muted">Clipboard blocked — select and copy the link above.</p>
          </div>
          <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            <input v-model="inviteForm.note" type="text" class="form-input" style="max-width:160px" placeholder="Who it's for (e.g. Mum)" />
            <input v-model="inviteForm.email" type="email" class="form-input" style="max-width:240px" placeholder="Their email (optional)" />
            <label class="text-sm" style="display:flex; align-items:center; gap:0.375rem; cursor:pointer">
              <input v-model="inviteForm.make_admin" type="checkbox" /> admin
            </label>
            <button class="btn btn-sm btn-primary" :disabled="memberBusy" @click="createInvite">Create invite link</button>
          </div>
          <p class="text-xs text-muted mt-1">Or add the member yourself with a temporary password using "+ Add member" above.</p>

          <div v-if="invites.length" style="margin-top:0.75rem">
            <p class="text-xs text-muted" style="margin-bottom:0.25rem">Invites</p>
            <table>
              <tbody>
                <tr v-for="i in invites" :key="i.id">
                  <td class="text-sm">{{ i.note || '—' }} <span class="text-xs text-muted">{{ i.email }}</span></td>
                  <td class="text-xs text-muted">by {{ i.created_by_name }} · {{ formatWhen(i.created_at) }}</td>
                  <td>
                    <span :class="['badge', i.used_at ? 'badge-paid' : (i.is_valid ? 'badge-pending' : 'badge-overdue')]">
                      {{ i.used_at ? 'Used by ' + i.used_by_name : (i.is_valid ? 'Pending' : 'Expired') }}
                    </span>
                  </td>
                  <td class="text-right">
                    <button v-if="!i.used_at" class="btn btn-sm btn-outline" style="color:var(--color-danger)" @click="revokeInvite(i)">Revoke</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
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

    <!-- Exchange rates -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Exchange Rates</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Analytics converts everything to USD using daily rates: the European Central Bank feed for the
          30 currencies it publishes, and a broader daily feed for the rest. Set a manual rate here for
          anything neither covers, or to pin a rate. A manual rate wins for that currency until you remove it.
        </p>
        <div v-if="fxSuccess" class="alert alert-success">{{ fxSuccess }}</div>
        <div v-if="fxError" class="alert alert-danger">{{ fxError }}</div>

        <div class="form-group">
          <label class="form-label">Manual rates</label>
          <p v-if="!fxRates.length" class="text-sm text-muted">None set. Feeds are used for every currency.</p>
          <table v-else>
            <thead>
              <tr><th>Currency</th><th>Rate</th><th>Note</th><th>Set by</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="r in fxRates" :key="r.currency">
                <td style="font-weight:600">{{ r.currency }}</td>
                <td class="font-mono text-sm">1 USD = {{ parseFloat(r.units_per_usd).toLocaleString('en-GB', { maximumFractionDigits: 6 }) }} {{ r.currency }}</td>
                <td class="text-sm text-muted">{{ r.note || '—' }}</td>
                <td class="text-sm text-muted">{{ r.updated_by_name || '—' }} · {{ r.updated_at.slice(0, 10) }}</td>
                <td class="text-right"><button class="btn btn-sm btn-outline" style="color:var(--color-danger)" @click="deleteFxRate(r)">Remove</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <form class="form-group" style="margin-bottom:0" @submit.prevent="saveFxRate">
          <label class="form-label">Set a rate</label>
          <div class="flex gap-2 items-center" style="flex-wrap:wrap">
            <span class="text-sm">1 USD =</span>
            <input v-model="fxForm.units_per_usd" type="number" step="any" min="0" class="form-input" style="max-width:160px" placeholder="11800" required />
            <input v-model="fxForm.currency" type="text" class="form-input" style="max-width:90px; text-transform:uppercase" placeholder="UZS" maxlength="3" required />
            <input v-model="fxForm.note" type="text" class="form-input" style="max-width:220px" placeholder="Note (optional)" />
            <button type="submit" class="btn btn-sm btn-primary" :disabled="fxBusy">{{ fxBusy ? 'Saving…' : 'Save rate' }}</button>
          </div>
          <p class="text-xs text-muted mt-1">Enter how many units of the currency one US dollar buys. Saving an existing currency replaces its rate.</p>
        </form>
      </div>
    </div>

    <!-- Agent Access (MCP) -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent Access (MCP)</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Let an AI agent read and change Hestia directly: list, add and edit expenses and maintain the
          dictionaries. Each token is a connector URL for one client.
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

    <!-- Agent prompt template -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent Prompt</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Template for the prompt copied from the Dashboard. It tells the agent to treat your next message as
          the brief — bills to add, corrections, or a bulk change — to plan and confirm before writing, and to
          work only through the MCP tools above.
        </p>
        <div class="form-group" style="margin-bottom:0">
          <textarea
            v-model="promptTemplateDraft"
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
            <button class="btn btn-sm btn-primary" :disabled="savingPromptTemplate" @click="savePromptTemplate">
              {{ savingPromptTemplate ? 'Saving...' : 'Save template' }}
            </button>
            <button class="btn btn-sm btn-outline" :disabled="savingPromptTemplate" @click="resetPromptTemplate">
              Reset to default
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Member Modal -->
    <div v-if="showMemberForm" class="modal-overlay" @click.self="showMemberForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>Add Member</h3>
          <button @click="showMemberForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="memberError" class="alert alert-danger">{{ memberError }}</div>
          <form @submit.prevent="submitMember">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">First name</label>
                <input v-model="memberForm.first_name" type="text" class="form-input" required />
              </div>
              <div class="form-group">
                <label class="form-label">Last name</label>
                <input v-model="memberForm.last_name" type="text" class="form-input" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Email</label>
              <input v-model="memberForm.email" type="email" class="form-input" required />
            </div>
            <div class="form-group">
              <label class="form-label">Temporary password</label>
              <input v-model="memberForm.password" type="text" class="form-input" minlength="8" required placeholder="At least 8 characters; share it with them" />
            </div>
            <div class="form-group">
              <label class="form-label" style="display:flex; align-items:center; gap:0.5rem; cursor:pointer">
                <input v-model="memberForm.is_staff" type="checkbox" /> Household admin (can manage members)
              </label>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showMemberForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="memberBusy">{{ memberBusy ? 'Creating…' : 'Create account' }}</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Set Password Modal -->
    <div v-if="showPasswordForm" class="modal-overlay" @click.self="showPasswordForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>Reset password · {{ passwordTarget?.display_name }}</h3>
          <button @click="showPasswordForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="memberError" class="alert alert-danger">{{ memberError }}</div>
          <form @submit.prevent="submitPassword">
            <div class="form-group">
              <label class="form-label">New temporary password</label>
              <input v-model="passwordForm.password" type="text" class="form-input" minlength="8" required />
              <p class="text-xs text-muted mt-1">Share it with them; they can change it from their profile.</p>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showPasswordForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary" :disabled="memberBusy">{{ memberBusy ? 'Saving…' : 'Set password' }}</button>
            </div>
          </form>
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

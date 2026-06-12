<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useExpenseStore } from '../stores/expenses'
import api from '../api/axios'

const auth = useAuthStore()
const store = useExpenseStore()

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

// Agent Import
const importConfig = ref(null)
const templateDraft = ref('')
const importError = ref('')
const importSuccess = ref('')
const tokenBusy = ref(false)
const savingTemplate = ref(false)
const copyState = ref('') // '' | 'copying' | 'copied' | 'manual'
const showPrompt = ref(false)
const promptText = ref('')

onMounted(() => {
  if (auth.user) {
    form.value.first_name = auth.user.first_name || ''
    form.value.last_name = auth.user.last_name || ''
    form.value.username = auth.user.username || ''
  }
  store.fetchSubjects()
  store.fetchExpenseTypes()
  fetchImportConfig()
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
    showPrompt.value = false
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

async function copyPrompt() {
  importError.value = ''
  copyState.value = 'copying'
  try {
    const { data } = await api.get('agent-import/prompt/')
    promptText.value = data.prompt
    showPrompt.value = true
    try {
      await navigator.clipboard.writeText(data.prompt)
      copyState.value = 'copied'
      setTimeout(() => {
        if (copyState.value === 'copied') copyState.value = ''
      }, 2500)
    } catch {
      // Clipboard blocked (e.g. non-secure context) — preview shown for manual copy.
      copyState.value = 'manual'
    }
  } catch (e) {
    copyState.value = ''
    importError.value = e.response?.data?.detail || 'Failed to build the prompt.'
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

    <!-- Agent Import -->
    <div class="card mb-4">
      <div class="card-header">
        <h3>Agent Import</h3>
      </div>
      <div class="card-body">
        <p class="text-sm text-muted mb-4">
          Generate a prompt to paste into an AI agent (e.g. Claude Cowork). It asks you to upload a bill,
          reads it, picks the matching subject and expense type, lets you confirm, then submits the expense
          to Hestia — so you don't have to enter it by hand.
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

        <!-- Copy prompt -->
        <div class="form-group" style="margin-bottom:0">
          <button
            class="btn btn-primary"
            :disabled="!importConfig?.has_token || copyState === 'copying'"
            @click="copyPrompt"
          >
            {{ copyState === 'copied' ? '✓ Copied to clipboard' : copyState === 'copying' ? 'Building…' : 'Copy import prompt' }}
          </button>
          <span v-if="!importConfig?.has_token" class="text-xs text-muted" style="margin-left:0.5rem">
            Generate a token first.
          </span>

          <div v-if="showPrompt" style="margin-top:0.5rem">
            <p v-if="copyState === 'manual'" class="text-xs text-muted" style="margin-bottom:0.25rem">
              Couldn't reach the clipboard automatically — select and copy the text below.
            </p>
            <textarea
              :value="promptText"
              readonly
              class="form-input"
              rows="10"
              style="font-family:'SF Mono',Monaco,monospace; font-size:0.8125rem"
              @focus="$event.target.select()"
            ></textarea>
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

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

onMounted(() => {
  if (auth.user) {
    form.value.first_name = auth.user.first_name || ''
    form.value.last_name = auth.user.last_name || ''
    form.value.username = auth.user.username || ''
  }
  store.fetchSubjects()
  store.fetchExpenseTypes()
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

<script setup>
import { ref, onMounted } from 'vue'
import { useExpenseStore } from '../stores/expenses'

const store = useExpenseStore()
const showForm = ref(false)
const editingId = ref(null)
const error = ref('')

const form = ref({
  name: '',
  icon: '',
  colour: '#6366f1',
})

onMounted(() => {
  store.fetchCategories()
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', icon: '', colour: '#6366f1' }
  error.value = ''
  showForm.value = true
}

function openEdit(cat) {
  editingId.value = cat.id
  form.value = { name: cat.name, icon: cat.icon || '', colour: cat.colour || '#6366f1' }
  error.value = ''
  showForm.value = true
}

async function handleSubmit() {
  error.value = ''
  try {
    if (editingId.value) {
      await store.updateCategory(editingId.value, form.value)
    } else {
      await store.createCategory(form.value)
    }
    showForm.value = false
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      error.value = Object.values(data).flat().join(' ')
    } else {
      error.value = 'Failed to save category.'
    }
  }
}

async function handleDelete(cat) {
  if (!confirm(`Delete category "${cat.name}"?`)) return
  try {
    await store.deleteCategory(cat.id)
  } catch (e) {
    alert(e.response?.data?.detail || 'Cannot delete this category.')
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Categories</h1>
      <button @click="openCreate" class="btn btn-primary">+ New Category</button>
    </div>

    <div class="card">
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Colour</th>
              <th>Name</th>
              <th>Type</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="cat in store.categories" :key="cat.id">
              <td>
                <span class="color-swatch" :style="{ background: cat.colour || '#6b7280' }"></span>
              </td>
              <td>
                <span class="badge" :style="{ background: (cat.colour || '#6b7280') + '22', color: cat.colour || '#6b7280' }">
                  {{ cat.name }}
                </span>
              </td>
              <td>
                <span class="text-sm text-muted">{{ cat.is_default ? 'Default' : 'Custom' }}</span>
              </td>
              <td class="text-right">
                <template v-if="!cat.is_default">
                  <button @click="openEdit(cat)" class="btn btn-sm btn-outline">Edit</button>
                  <button @click="handleDelete(cat)" class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)">Delete</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Category Form Modal -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? 'Edit Category' : 'New Category' }}</h3>
          <button @click="showForm = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="error" class="alert alert-danger">{{ error }}</div>
          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">Name</label>
              <input v-model="form.name" type="text" class="form-input" required />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Icon Class (optional)</label>
                <input v-model="form.icon" type="text" class="form-input" placeholder="e.g. pi pi-home" />
              </div>
              <div class="form-group">
                <label class="form-label">Colour</label>
                <div class="flex items-center gap-2">
                  <input v-model="form.colour" type="color" style="width:40px; height:36px; border:none; cursor:pointer" />
                  <input v-model="form.colour" type="text" class="form-input" maxlength="7" style="flex:1" />
                </div>
              </div>
            </div>
            <div class="modal-footer" style="padding:0; border:none; margin-top:1rem">
              <button type="button" class="btn btn-outline" @click="showForm = false">Cancel</button>
              <button type="submit" class="btn btn-primary">
                {{ editingId ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.color-swatch {
  display: inline-block;
  width: 20px;
  height: 20px;
  border-radius: 4px;
}
</style>

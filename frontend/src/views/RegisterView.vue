<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api/axios'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = ref({
  email: '',
  username: '',
  first_name: '',
  last_name: '',
  password: '',
  invite: '',
})
const error = ref('')
const loading = ref(false)
// Registration is invite-only once the household has its first member.
const status = ref(null)   // { open, invite_required, invite_valid, invite_email }

onMounted(async () => {
  form.value.invite = (route.query.invite || '').toString()
  try {
    const { data } = await api.get('auth/register/', { params: form.value.invite ? { invite: form.value.invite } : {} })
    status.value = data
    if (data.invite_email && !form.value.email) form.value.email = data.invite_email
  } catch {
    status.value = { open: false, invite_required: true, invite_valid: false, invite_email: '' }
  }
})

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    await auth.register(form.value)
    router.push('/')
  } catch (e) {
    const data = e.response?.data
    if (data && typeof data === 'object') {
      error.value = Object.values(data).flat().join(' ')
    } else {
      error.value = 'Registration failed. Please try again.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card card">
      <div class="card-body">
        <h1 class="auth-title">Create Account</h1>
        <p class="text-muted mb-4">
          <template v-if="status?.open">You are the first member — this account becomes the household admin.</template>
          <template v-else>Join your family on Hestia</template>
        </p>

        <div v-if="error" class="alert alert-danger">{{ error }}</div>

        <div v-if="status && status.invite_required && !status.invite_valid" class="alert alert-danger">
          <template v-if="form.invite">This invite link is invalid, already used, or expired. Ask a household admin for a new one.</template>
          <template v-else>Registration is by invitation. Ask a household admin for an invite link.</template>
        </div>

        <form v-if="!status || status.open || status.invite_valid" @submit.prevent="handleRegister">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">First Name</label>
              <input v-model="form.first_name" type="text" class="form-input" required />
            </div>
            <div class="form-group">
              <label class="form-label">Last Name</label>
              <input v-model="form.last_name" type="text" class="form-input" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Username</label>
            <input v-model="form.username" type="text" class="form-input" required />
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input v-model="form.email" type="email" class="form-input" required />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input v-model="form.password" type="password" class="form-input" minlength="8" required />
          </div>
          <button type="submit" class="btn btn-primary btn-lg" style="width:100%" :disabled="loading">
            {{ loading ? 'Creating account...' : 'Create Account' }}
          </button>
        </form>

        <p v-if="status && status.invite_valid" class="text-xs text-muted" style="text-align:center; margin-top:0.5rem">Invite accepted — complete the form to join.</p>
        <p class="auth-footer">
          Already have an account? <RouterLink to="/login">Sign in</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 1rem;
  background: var(--color-gray-50);
}
.auth-card {
  width: 100%;
  max-width: 420px;
}
.auth-title {
  margin-bottom: 0.25rem;
}
.auth-footer {
  margin-top: 1.5rem;
  text-align: center;
  font-size: 0.875rem;
  color: var(--color-gray-500);
}
.auth-footer a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}
</style>

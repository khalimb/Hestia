<script setup>
import { RouterView, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useDashboardStore } from './stores/dashboard'
import { computed, onMounted, watch } from 'vue'

const router = useRouter()
const auth = useAuthStore()
const dashboard = useDashboardStore()

const showNav = computed(() => auth.isAuthenticated)
const overdueCount = computed(() => dashboard.overdue.length)
const dueTodayCount = computed(() => dashboard.summary?.due_today_count || 0)
const badgeCount = computed(() => overdueCount.value + dueTodayCount.value)

onMounted(async () => {
  if (auth.isAuthenticated) {
    await auth.fetchUser()
    await dashboard.fetchAll()
  }
})

watch(() => auth.isAuthenticated, async (val) => {
  if (val) {
    await auth.fetchUser()
    await dashboard.fetchAll()
  }
})

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div id="app">
    <nav v-if="showNav" class="navbar">
      <div class="nav-brand">
        <RouterLink to="/" class="brand-link">
          <span class="brand-icon">🏠</span>
          <span class="brand-name">Hestia</span>
        </RouterLink>
      </div>
      <div class="nav-links">
        <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
        <RouterLink to="/expenses" class="nav-link">Expenses</RouterLink>
        <RouterLink to="/settings" class="nav-link">Settings</RouterLink>
      </div>
      <div class="nav-right">
        <span v-if="badgeCount > 0" class="notification-badge" :title="`${overdueCount} overdue, ${dueTodayCount} due today`">
          {{ badgeCount }}
        </span>
        <span class="user-name">{{ auth.user?.first_name }}</span>
        <button @click="handleLogout" class="btn btn-sm btn-outline">Logout</button>
      </div>
    </nav>
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  padding: 0 1.5rem;
  height: 60px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 100;
}
.nav-brand { margin-right: 2rem; }
.brand-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: #111827;
  font-weight: 700;
  font-size: 1.25rem;
}
.brand-icon { font-size: 1.5rem; }
.nav-links {
  display: flex;
  gap: 0.25rem;
  flex: 1;
}
.nav-link {
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  text-decoration: none;
  color: #4b5563;
  font-weight: 500;
  transition: all 0.15s;
}
.nav-link:hover { background: #f3f4f6; color: #111827; }
.nav-link.router-link-active { background: var(--color-primary-bg); color: var(--color-primary); }
.nav-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.notification-badge {
  background: #ef4444;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  cursor: default;
}
.user-name { color: #6b7280; font-weight: 500; }
.main-content { padding: 1.5rem; max-width: 1200px; margin: 0 auto; }
</style>

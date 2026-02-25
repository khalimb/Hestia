import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/RegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
  },
  {
    path: '/expenses',
    name: 'ExpenseList',
    component: () => import('../views/ExpenseListView.vue'),
  },
  {
    path: '/expenses/new',
    name: 'ExpenseCreate',
    component: () => import('../views/ExpenseFormView.vue'),
  },
  {
    path: '/expenses/:id',
    name: 'ExpenseDetail',
    component: () => import('../views/ExpenseDetailView.vue'),
  },
  {
    path: '/expenses/:id/edit',
    name: 'ExpenseEdit',
    component: () => import('../views/ExpenseFormView.vue'),
  },
  {
    path: '/occurrences/:id',
    name: 'OccurrenceDetail',
    component: () => import('../views/OccurrenceDetailView.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth === false) {
    if (token && (to.name === 'Login' || to.name === 'Register')) {
      next({ name: 'Dashboard' })
    } else {
      next()
    }
  } else if (!token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router

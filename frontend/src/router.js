import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/', redirect: '/library' },
    { path: '/library', component: () => import('./views/LibraryView.vue') },
    { path: '/profiles', component: () => import('./views/ProfilesView.vue') },
    { path: '/profiles/:id', component: () => import('./views/ProfileView.vue') },
    { path: '/training', component: () => import('./views/TrainingView.vue') },
    { path: '/teachers', component: () => import('./views/TeachersView.vue'), meta: { admin: true } },
    { path: '/:pathMatch(.*)*', redirect: '/library' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
router.beforeEach(async to => {
  const auth = useAuth()
  await auth.init()
  if (!to.meta.public && !auth.user) return '/login'
  if (to.path === '/login' && auth.user) return '/library'
  if (to.meta.admin && auth.user?.role !== 'admin') return '/library'
})

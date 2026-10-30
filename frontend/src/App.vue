<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './stores/auth'
import { useUI } from './stores/ui'
import { initials } from './utils'
const auth = useAuth(), ui = useUI(), route = useRoute(), router = useRouter()
const mobileNav = ref(false)
const bare = computed(() => route.path === '/login' || route.path === '/training')
const section = computed(() => route.path.startsWith('/profiles') ? 'Учебные профили' : route.path.startsWith('/teachers') ? 'Преподаватели' : 'База заданий')
async function logout() {
  try { await auth.logout(); router.push('/login') } catch (e) { ui.notify(e.message, 'error') }
}
</script>
<template>
  <div v-if="auth.user && !bare" class="app-shell">
    <div v-if="mobileNav" class="sidebar-overlay" @click="mobileNav = false"></div>
    <aside class="sidebar" :class="{ open: mobileNav }">
      <RouterLink to="/library" class="brand" @click="mobileNav = false"><div class="brand-symbol">u<span></span></div><span>uTutor<span class="brand-dot">.</span></span></RouterLink>
      <div class="workspace-label">ПРОСТРАНСТВО ПРЕПОДАВАТЕЛЯ</div>
      <nav class="nav-items" aria-label="Основная навигация">
        <RouterLink to="/library" :class="{ active: route.path.startsWith('/library') }" @click="mobileNav = false"><Icon name="BookOpen" /><span>База заданий</span><span class="nav-active-dot"></span></RouterLink>
        <RouterLink to="/profiles" :class="{ active: route.path.startsWith('/profiles') }" @click="mobileNav = false"><Icon name="Users" /><span>Учебные профили</span><span class="nav-active-dot"></span></RouterLink>
        <RouterLink v-if="auth.user.role === 'admin'" to="/teachers" :class="{ active: route.path === '/teachers' }" @click="mobileNav = false"><Icon name="GraduationCap" /><span>Преподаватели</span><span class="nav-active-dot"></span></RouterLink>
      </nav>
      <div class="sidebar-bottom">
        <div class="user-block"><div class="avatar">{{ initials(auth.user.name) }}</div><div class="user-meta"><strong>{{ auth.user.name }}</strong><span>{{ auth.user.role === 'admin' ? 'Администратор' : 'Преподаватель' }}</span></div><button class="icon-btn" title="Выйти" aria-label="Выйти из аккаунта" @click="logout"><Icon name="LogOut" :size="18" /></button></div>
      </div>
    </aside>
    <div class="main-shell"><header class="topbar"><div class="flex items-center gap-3"><button class="icon-btn mobile-menu" aria-label="Открыть меню" @click="mobileNav = true"><Icon name="Menu" /></button><span>{{ section }}</span></div></header><main class="page-container"><RouterView /></main></div>
  </div>
  <RouterView v-else />
  <div class="toast-stack" aria-live="polite"><div v-for="toast in ui.toasts" :key="toast.id" class="toast" :class="toast.type"><Icon :name="toast.type === 'error' ? 'AlertCircle' : 'CircleCheck'" :size="20" /><span>{{ toast.message }}</span><button class="icon-btn" aria-label="Закрыть уведомление" @click="ui.toasts = ui.toasts.filter(t => t.id !== toast.id)"><Icon name="X" :size="15" /></button></div></div>
</template>

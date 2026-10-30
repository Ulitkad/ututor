import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { setExpiredHandler } from './api'
import { useAuth } from './stores/auth'
import Icon from './components/Icon.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.component('Icon', Icon)
setExpiredHandler(() => { useAuth().clear(); router.replace('/login') })
app.mount('#app')

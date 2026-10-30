<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { categories, categoryById, taskLabel } from '../utils'
import { useUI } from '../stores/ui'
import Modal from '../components/Modal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import EmptyState from '../components/EmptyState.vue'
import ListEditor from '../components/ListEditor.vue'

const ui = useUI(), library = ref({ folders: [], lists: [] }), loading = ref(true), error = ref('')
const category = ref('stress'), folderId = ref(null), search = ref(''), menu = ref(null)
const folderModal = ref(null), folderName = ref(''), saving = ref(false), formError = ref(''), deleting = ref(null), editor = ref(null)
const current = computed(() => categoryById(category.value))
const currentFolder = computed(() => library.value.folders.find(f => f.id === folderId.value))
const folders = computed(() => library.value.folders.filter(f => f.category === category.value && f.name.toLowerCase().includes(search.value.toLowerCase())))
const lists = computed(() => library.value.lists.filter(l => l.folder_id === folderId.value && l.name.toLowerCase().includes(search.value.toLowerCase())))
const total = computed(() => library.value.lists.reduce((a, l) => a + l.count, 0))
function categoryStats(id) {
  const ids = library.value.folders.filter(f => f.category === id).map(f => f.id)
  return library.value.lists.filter(l => ids.includes(l.folder_id)).reduce((a, l) => a + l.count, 0)
}
function folderStats(id) { const lists = library.value.lists.filter(l => l.folder_id === id); return { lists: lists.length, count: lists.reduce((a, l) => a + l.count, 0) } }
async function load() {
  error.value = ''
  try { library.value = await api('/library') } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
onMounted(load)
function selectCategory(id) { category.value = id; folderId.value = null; search.value = ''; menu.value = null }
function openFolderModal(folder = null) { folderModal.value = folder || {}; folderName.value = folder?.name || ''; formError.value = ''; menu.value = null }
async function saveFolder() {
  saving.value = true; formError.value = ''
  try {
    await api(folderModal.value.id ? `/folders/${folderModal.value.id}` : '/folders', { method: folderModal.value.id ? 'PUT' : 'POST', body: { name: folderName.value, category: category.value } })
    folderModal.value = null; await load(); ui.notify('Папка сохранена')
  } catch (e) { formError.value = e.message } finally { saving.value = false }
}
async function remove(done) {
  try { await api(`/${deleting.value.type}/${deleting.value.id}`, { method: 'DELETE' }); deleting.value = null; await load(); ui.notify('Удалено') }
  catch (e) { ui.notify(e.message, 'error') } finally { done() }
}
function openEditor(taskList = null, mode = 'visual') { editor.value = { id: taskList?.id, folderId: folderId.value, category: category.value, mode } }
async function saved() { editor.value = null; await load(); ui.notify('Список сохранён') }
</script>
<template>
  <section @click="menu = null">
    <div class="page-heading"><div><div class="eyebrow mb-3">ВСЁ ДЛЯ ВАШИХ ЗАНЯТИЙ</div><h1>База заданий<span class="heading-dot">.</span></h1><p>Собирайте материалы. Создавайте задания. Вдохновляйте учиться.</p></div><div class="heading-actions"><button v-if="folderId" class="btn secondary" @click="openEditor(null, 'import')"><Icon name="Upload" :size="16" />Импорт .txt</button><button class="btn primary" @click="folderId ? openEditor() : openFolderModal()"><Icon :name="folderId ? 'Plus' : 'FolderPlus'" :size="17" />{{ folderId ? 'Новый список' : 'Создать папку' }}</button></div></div>
    <div class="category-grid"><button v-for="cat in categories" :key="cat.id" class="category-card" :class="{ selected: category === cat.id }" @click="selectCategory(cat.id)"><span v-if="category === cat.id" class="category-check"><Icon name="Check" :size="11" /></span><div class="category-icon"><Icon :name="cat.icon" :size="21" /></div><h3>{{ cat.name }}</h3><p>{{ cat.description }}</p><div class="category-bottom"><span>{{ categoryStats(cat.id) }} {{ taskLabel(categoryStats(cat.id)) }}</span><Icon name="ArrowUpRight" :size="15" /></div></button></div>
    <div v-if="error" class="error-box mb-5">{{ error }} <button class="underline" @click="load">Повторить</button></div>
    <div v-if="loading" class="loading"><Icon name="LoaderCircle" class="spin" />Загружаем материалы…</div>
    <template v-else>
      <div v-if="folderId" class="breadcrumbs"><button @click="folderId = null; search = ''">{{ current.name }}</button><Icon name="ChevronRight" :size="13" /><span>{{ currentFolder?.name }}</span></div>
      <div class="section-heading"><h2>{{ folderId ? currentFolder?.name : 'Папки и классы' }}<span class="count-badge">{{ folderId ? lists.length : folders.length }}</span></h2><div class="flex items-center gap-3"><div class="search-field"><Icon name="Search" :size="15" /><input v-model="search" :placeholder="folderId ? 'Найти список…' : 'Найти папку…'" :aria-label="folderId ? 'Поиск списков' : 'Поиск папок'" /></div><span class="view-icon"><Icon :name="folderId ? 'ListFilter' : 'Layers'" :size="17" /></span></div></div>
      <template v-if="!folderId"><div class="folder-grid"><article v-for="folder in folders" :key="folder.id" class="folder-card card"><button class="folder-main" @click="folderId = folder.id; search = ''"><div class="folder-illustration"></div><h3>{{ folder.name }}</h3><p class="folder-meta">{{ folderStats(folder.id).lists }} списков<span class="mx-2 text-slate-300">·</span>{{ folderStats(folder.id).count }} {{ taskLabel(folderStats(folder.id).count) }}</p><Icon class="folder-arrow" name="ChevronRight" :size="15" /></button><button class="icon-btn folder-menu" :aria-label="`Действия с папкой ${folder.name}`" @click.stop="menu = menu === folder.id ? null : folder.id"><Icon name="MoreHorizontal" :size="18" /></button><div v-if="menu === folder.id" class="menu-popover" @click.stop><button @click="openFolderModal(folder)"><Icon name="Pencil" :size="14" />Переименовать</button><button class="text-rose-500" @click="deleting = { ...folder, type: 'folders' }; menu = null"><Icon name="Trash2" :size="14" />Удалить папку</button></div></article><button class="new-folder-card" @click="openFolderModal()"><span><Icon name="Plus" :size="20" /></span>Новая папка</button></div><p v-if="!folders.length && search" class="muted text-xs mt-5">По запросу «{{ search }}» папок не найдено.</p></template>
      <template v-else><div v-if="lists.length" class="card table-card"><article v-for="list in lists" :key="list.id" class="list-row"><div class="file-icon"><Icon name="FileText" :size="21" /></div><button class="list-info" @click="openEditor(list)"><h3>{{ list.name }}</h3><p>{{ list.count }} {{ taskLabel(list.count) }}<span class="mx-2">·</span>Обновлён {{ new Date(list.updated_at).toLocaleDateString('ru-RU') }}</p></button><span v-if="list.review" class="badge amber"><Icon name="AlertCircle" :size="11" />Проверить: {{ list.review }}</span><button class="icon-btn" aria-label="Редактировать список" @click="openEditor(list)"><Icon name="Pencil" :size="16" /></button><button class="icon-btn red" aria-label="Удалить список" @click="deleting = { ...list, type: 'lists' }"><Icon name="Trash2" :size="16" /></button><button class="icon-btn" aria-label="Открыть список" @click="openEditor(list)"><Icon name="ChevronRight" :size="17" /></button></article></div><EmptyState v-else icon="FileText" :title="search ? 'Ничего не нашлось' : 'Первый список — начало большого пути'" :text="search ? 'Попробуйте другое название.' : 'Создайте задания в визуальном редакторе или загрузите готовый текстовый файл.'" :action="search ? '' : 'Создать список'" @action="openEditor()" /></template>
      <div class="info-banner"><Icon name="CircleHelp" :size="17" /><p><strong>{{ folderId ? 'Ваши материалы — ваши правила.' : 'Порядок в материалах — лёгкость на занятиях.' }}</strong> {{ folderId ? 'Задания можно редактировать в наглядном конструкторе или текстовом режиме. Готовый список прикрепите к учебному профилю.' : 'Создавайте папки по классам, темам или уровню подготовки. Внутри храните списки заданий — всё будет под рукой.' }}</p></div>
      <div class="library-bottom"><span><Icon name="ShieldCheck" :size="13" />Ваши материалы доступны только вам</span><span>Всего в базе: <strong>{{ total }}</strong> {{ taskLabel(total) }}</span></div>
    </template>
  </section>
  <Modal v-if="folderModal" :title="folderModal.id ? 'Переименовать папку' : 'Новая папка'" :subtitle="current.name" @close="!saving && (folderModal = null)"><form @submit.prevent="saveFolder"><div class="modal-body"><div class="field"><label for="folder-name">Название папки</label><input id="folder-name" v-model="folderName" class="input" placeholder="Например, 11 класс (ЕГЭ)" required maxlength="120" autofocus /></div><div v-if="formError" class="error-box mt-4">{{ formError }}</div></div><footer class="modal-footer"><button type="button" class="btn secondary" :disabled="saving" @click="folderModal = null">Отмена</button><button class="btn primary" :disabled="saving || !folderName.trim()"><Icon v-if="saving" name="LoaderCircle" class="spin" :size="16" />{{ folderModal.id ? 'Сохранить' : 'Создать папку' }}</button></footer></form></Modal>
  <ConfirmDialog v-if="deleting" :title="deleting.type === 'folders' ? 'Удалить папку?' : 'Удалить список?'" :message="`«${deleting.name}» и связанные задания будут удалены вместе с прогрессом учеников. Это действие нельзя отменить.`" @close="deleting = null" @confirm="remove" />
  <ListEditor v-if="editor" :config="editor" @close="editor = null" @saved="saved" />
</template>
<style scoped>
.heading-dot{color:#0284c7}.library-bottom{display:flex;justify-content:space-between;color:#a4afbd;font-size:9px;margin-top:22px;gap:15px}.library-bottom>span:first-child{display:flex;gap:6px;align-items:center}.library-bottom strong{color:#7d8da3;font-weight:500}.view-icon{width:33px;height:33px;display:flex;align-items:center;justify-content:center;border:1px solid #e7edf4;border-radius:8px;color:#91a1b5;background:#fff}@media(max-width:760px){.library-bottom{flex-wrap:wrap}.view-icon{display:none}}
</style>

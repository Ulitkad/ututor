<script setup>
import { ref } from 'vue'
import { api } from '../api'
import Modal from './Modal.vue'
const props = defineProps({ profile: Object })
const emit = defineEmits(['close', 'saved'])
const name = ref(props.profile?.name || ''), kind = ref(props.profile?.kind || 'student'), note = ref(props.profile?.note || ''), busy = ref(false), error = ref('')
async function save() {
  busy.value = true; error.value = ''
  try {
    const result = await api(props.profile ? `/profiles/${props.profile.id}` : '/profiles', { method: props.profile ? 'PUT' : 'POST', body: { name: name.value, kind: kind.value, note: note.value } })
    emit('saved', result)
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template><Modal :title="profile ? 'Настройки профиля' : 'Новый учебный профиль'" @close="!busy && emit('close')"><form @submit.prevent="save"><div class="modal-body"><div class="field"><label>Тип профиля</label><div class="profile-kind"><button type="button" :class="{ selected: kind === 'student' }" @click="kind = 'student'"><Icon name="GraduationCap" :size="24" /><span>Ученик</span><Icon v-if="kind === 'student'" class="kind-check" name="CircleCheck" :size="14" /></button><button type="button" :class="{ selected: kind === 'group' }" @click="kind = 'group'"><Icon name="Users" :size="24" /><span>Группа</span><Icon v-if="kind === 'group'" class="kind-check" name="CircleCheck" :size="14" /></button></div></div><div class="field"><label for="profile-name">Название профиля</label><input id="profile-name" v-model="name" class="input" :placeholder="kind === 'group' ? 'Например, Группа ОГЭ Вт-Чт' : 'Например, Иван, 11 класс'" required maxlength="120" autofocus /></div><div class="field"><label for="profile-note">Заметка <span class="muted font-normal">· необязательно</span></label><textarea id="profile-note" v-model="note" class="input" placeholder="Цели занятий, расписание или что-то важное…" maxlength="1000"></textarea></div><div v-if="error" class="error-box mt-4">{{ error }}</div></div><footer class="modal-footer"><button type="button" class="btn secondary" :disabled="busy" @click="emit('close')">Отмена</button><button class="btn primary" :disabled="busy || !name.trim()"><Icon :name="busy ? 'LoaderCircle' : 'Check'" :class="{ spin: busy }" :size="16" />{{ profile ? 'Сохранить' : 'Создать профиль' }}</button></footer></form></Modal></template>
<style scoped>
.profile-kind{display:grid;grid-template-columns:1fr 1fr;gap:12px}.profile-kind button{border:1px solid #e4ebf4;border-radius:12px;padding:18px;display:flex;flex-direction:column;align-items:center;gap:10px;background:#fff;color:#9bacc0;position:relative;font-size:12px}.profile-kind button.selected{border-color:#a6d6f2;background:#f3faff;color:#4798ca}.kind-check{position:absolute;top:10px;right:10px}
</style>

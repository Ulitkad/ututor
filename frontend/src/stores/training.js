import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'

export const useTraining = defineStore('training', () => {
  const session = ref(null)
  async function start(profileId, listIds, itemIds) {
    session.value = await api(`/profiles/${profileId}/sessions`, { method: 'POST', body: { list_ids: Array.isArray(listIds) ? listIds : [listIds], item_ids: itemIds } })
  }
  async function resume(id) { session.value = await api(`/sessions/${id}`) }
  return { session, start, resume }
})

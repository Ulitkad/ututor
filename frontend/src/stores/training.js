import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'

export const useTraining = defineStore('training', () => {
  const session = ref(null)
  async function start(profileId, listId, itemIds) {
    session.value = await api(`/profiles/${profileId}/sessions`, { method: 'POST', body: { list_id: listId, item_ids: itemIds } })
  }
  return { session, start }
})

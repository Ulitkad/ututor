let accessToken = null
let refreshing = null
let onExpired = () => {}

export function setToken(token) { accessToken = token }
export function setExpiredHandler(handler) { onExpired = handler }

export async function refreshAccess() {
  if (!refreshing) {
    refreshing = fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin' })
      .then(async response => {
        if (!response.ok) throw new Error('Сессия истекла. Войдите снова.')
        const data = await response.json()
        accessToken = data.access_token
        return data
      }).finally(() => { refreshing = null })
  }
  return refreshing
}

export async function api(path, options = {}, retry = true) {
  const headers = new Headers(options.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, {
    ...options, headers, credentials: 'same-origin',
    body: options.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body,
  })
  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    try { await refreshAccess() } catch (error) { accessToken = null; onExpired(); throw error }
    return api(path, options, false)
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('\n') : data.detail
    throw new Error(detail || (response.status >= 500 ? 'Сервер временно недоступен. Попробуйте ещё раз.' : 'Не удалось выполнить запрос.'))
  }
  return response.status === 204 ? null : response.json()
}

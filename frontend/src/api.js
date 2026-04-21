const BASE = import.meta.env.VITE_API_URL ?? ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, options)
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    const message = data.detail || data.message || 'Something went wrong'
    throw new Error(message)
  }

  return data
}

function query(params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value)
    }
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  getRecipes: (q = '', tag = '') => request(`/api/recipes${query({ q, tag })}`),
  getRecipe: (id) => request(`/api/recipes/${id}`),
  scaleRecipe: (id, servings, unit) =>
    request(`/api/recipes/${id}/scale${query({ servings, unit })}`),
  updateRecipe: (id, data) =>
    request(`/api/recipes/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  addByUrl: (url) =>
    request('/api/recipes/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    }),
  addByUpload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/recipes/upload', {
      method: 'POST',
      body: form,
    })
  },
  deleteRecipe: (id) =>
    request(`/api/recipes/${id}`, {
      method: 'DELETE',
    }),
}

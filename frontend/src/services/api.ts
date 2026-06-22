import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/api/auth/refresh', null, {
            params: { refresh_token: refresh },
          })
          localStorage.setItem('access_token', data.access_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return axios(error.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api

// ─── Document APIs ────────────────────────────────────────────────────────────

export const uploadFile = (file: File, department?: string) => {
  const form = new FormData()
  form.append('file', file)
  if (department) form.append('department', department)
  return api.post('/upload', form)
}

export const uploadBulk = (files: File[], department?: string) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  if (department) form.append('department', department)
  return api.post('/upload/bulk', form)
}

export const getDocuments = (params?: { status?: string; department?: string }) =>
  api.get('/documents', { params }).then((r) => r.data)

export const getDocument = (id: number) =>
  api.get(`/documents/${id}`).then((r) => r.data)

export const deleteDocument = (id: number) => api.delete(`/documents/${id}`)

// ─── Chunk APIs ───────────────────────────────────────────────────────────────

export const chunkDocument = (id: number) => api.post(`/documents/${id}/chunk`)
export const chunkAll = () => api.post('/chunk/all')
export const getChunks = (docId: number) =>
  api.get(`/documents/${docId}/chunks`).then((r) => r.data)

// ─── Embedding APIs ───────────────────────────────────────────────────────────

export const embedDocument = (id: number) => api.post(`/documents/${id}/embed`)
export const embedAll = () => api.post('/embed/all')
export const getEmbeddingStatus = (id: number) =>
  api.get(`/documents/${id}/embedding-status`).then((r) => r.data)
export const getQdrantStats = () => api.get('/qdrant/stats').then((r) => r.data)
export const reprocessDocument = (id: number) => api.post(`/documents/${id}/reprocess`)

// ─── Auth APIs ────────────────────────────────────────────────────────────────

export const login = (email: string, password: string) =>
  api.post('/auth/login', { email, password }).then((r) => r.data)

export const logout = () => api.post('/auth/logout')
export const getMe = () => api.get('/auth/me').then((r) => r.data)
export const getUsers = () => api.get('/users').then((r) => r.data)
export const updateRole = (userId: number, role: string) =>
  api.put(`/users/${userId}/role`, { role })
export const disableUser = (userId: number) => api.put(`/users/${userId}/disable`)

// ─── Drive APIs ───────────────────────────────────────────────────────────────

export const getDriveFiles = (folderId?: string) =>
  api.get('/drive/files', { params: { folder_id: folderId } }).then((r) => r.data)

export const importDriveFile = (fileId: string) => api.post(`/drive/import/${fileId}`)
export const importAllDriveFiles = () => api.post('/drive/import-all')

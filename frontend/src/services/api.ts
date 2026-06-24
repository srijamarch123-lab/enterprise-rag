import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

export default api


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

export const chunkDocument = (id: number) => api.post(`/documents/${id}/chunk`)
export const chunkAll = () => api.post('/chunk/all')
export const getChunks = (docId: number) =>
  api.get(`/documents/${docId}/chunks`).then((r) => r.data)

export const embedDocument = (id: number) => api.post(`/documents/${id}/embed`)
export const embedAll = () => api.post('/embed/all')
export const getEmbeddingStatus = (id: number) =>
  api.get(`/documents/${id}/embedding-status`).then((r) => r.data)
export const getQdrantStats = () => api.get('/qdrant/stats').then((r) => r.data)
export const reprocessDocument = (id: number) => api.post(`/documents/${id}/reprocess`)

export const register = (email: string, password: string, full_name: string) =>
  api.post('/auth/register', { email, password, full_name }).then((r) => r.data)

export const login = (email: string, password: string) =>
  api.post('/auth/login', { email, password }).then((r) => r.data)

export const logout = () => api.post('/auth/logout')

export const getMe = () => api.get('/auth/me').then((r) => r.data)
export const getUsers = () => api.get('/users').then((r) => r.data)
export const updateRole = (userId: number, role: string) =>
  api.put(`/users/${userId}/role`, { role })
export const disableUser = (userId: number) => api.put(`/users/${userId}/disable`)
export const enableUser = (userId: number) => api.put(`/users/${userId}/enable`)

export const getDriveFiles = (folderId?: string) =>
  api.get('/drive/files', { params: { folder_id: folderId } }).then((r) => r.data)

export const importDriveFile = (fileId: string) => api.post(`/drive/import/${fileId}`)
export const importAllDriveFiles = () => api.post('/drive/import-all')

import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000', // ✅ FIXED
  timeout: 30000,
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle auth errors globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    // Only redirect to login for protected routes, not the login route itself
    if (err.response?.status === 401 && !err.config.url.includes('/auth/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('user_id') // ✅ FIXED
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const authAPI = {
  login: (email, password) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password })),
  register: (data) => api.post('/auth/register', data),
}

export const studentAPI = {
  getProfile: (id) => api.get(`/student/${id}/profile`),
  getMastery: (id) => api.get(`/student/${id}/mastery`),
}

export const learningAPI = {
  getPath: (id, n = 5) => api.get(`/learning-path/${id}?n=${n}`),
  getAllTopics: () => api.get('/learning-path/topics/all'),
  completeSession: (data) => api.post('/learning-path/session/complete', data),
  getPrereqs: (topicId) => api.get(`/learning-path/topics/${topicId}/prerequisites`),
}

export const assessmentAPI = {
  startAdaptive: (data) => api.post('/assessment/adaptive/start', data),
  submitAnswer: (data) => api.post('/assessment/adaptive/submit', data),
  generateQ: (data) => api.post('/assessment/generate', data),
  getHistory: (id, t) =>
    api.get(`/assessment/${id}/history${t ? `?topic_id=${t}` : ''}`),
}

export const tutorAPI = {
  chat: (data) => api.post('/tutor/chat', data),
  evaluateAnswer: (s, c) =>
    api.post('/tutor/evaluate', null, {
      params: { student_answer: s, correct_answer: c },
    }),
}

export const analyticsAPI = {
  getHeatmap: (id) => api.get(`/analytics/${id}/heatmap`),
  getPredict: (id) => api.get(`/analytics/${id}/predict`),
  getProgress: (id) => api.get(`/analytics/${id}/progress`),
}

export const engagementAPI = {
  logEvent: (data) => api.post('/engagement/event', data),
  getScore: (id) => api.get(`/engagement/${id}/score`),
  getAttention: (id) => api.get(`/engagement/${id}/attention`),
}

export default api

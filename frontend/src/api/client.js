import axios from 'axios'

// In production (Railway), VITE_API_URL points to the backend service URL.
// In dev, it's unset so we fall back to '/api' which Vite proxies to localhost:8000.
const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({
  baseURL,
  timeout: 30_000,
})

export default api

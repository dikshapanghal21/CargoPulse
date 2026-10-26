import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

/**
 * Normalise any API/network failure into { message, status, fieldErrors }.
 * FastAPI returns either {detail: "text", field?} or {detail: [{loc, msg}, ...]}.
 */
export function parseApiError(error) {
  if (!error) return { message: 'Unknown error', status: null, fieldErrors: {} }
  if (error.code === 'ECONNABORTED') {
    return { message: 'The server took too long to respond. Try again.', status: null, fieldErrors: {} }
  }
  if (!error.response) {
    return {
      message: 'Cannot reach the CargoPulse API. Check that the backend is running.',
      status: null,
      fieldErrors: {},
    }
  }
  const { status, data } = error.response
  const fieldErrors = {}
  let message = `Request failed (${status})`
  if (data && typeof data.detail === 'string') {
    message = data.detail
    if (data.field) fieldErrors[data.field] = data.detail
  } else if (data && Array.isArray(data.detail)) {
    const parts = data.detail.map((d) => {
      const loc = (d.loc || []).filter((p) => p !== 'body' && p !== 'query')
      const field = loc[loc.length - 1]
      const msg = (d.msg || 'Invalid value').replace(/^Value error, /, '')
      if (field && typeof field === 'string') fieldErrors[field] = msg
      return field ? `${String(field).replace(/_/g, ' ')}: ${msg}` : msg
    })
    message = parts.join('; ')
  }
  return { message, status, fieldErrors }
}

export default client

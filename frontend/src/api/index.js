import client from './client'

const data = (p) => p.then((r) => r.data)

/** Drop empty params so URLs stay clean and the API never sees blank filters. */
function clean(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  )
}

export const api = {
  health: () => data(client.get('/health')),

  dashboard: (params) => data(client.get('/dashboard', { params: clean(params) })),

  shipments: {
    list: (params) => data(client.get('/shipments', { params: clean(params) })),
    get: (id) => data(client.get(`/shipments/${id}`)),
    byTracking: (trackingId) => data(client.get(`/shipments/tracking/${encodeURIComponent(trackingId)}`)),
    create: (body) => data(client.post('/shipments', body)),
    update: (id, body) => data(client.patch(`/shipments/${id}`, body)),
    remove: (id) => data(client.delete(`/shipments/${id}`)),
    changeStatus: (id, body) => data(client.post(`/shipments/${id}/status`, body)),
    lifecycle: () => data(client.get('/shipments/lifecycle')),
  },

  carriers: {
    list: (params) => data(client.get('/carriers', { params: clean(params) })),
    get: (id) => data(client.get(`/carriers/${id}`)),
    create: (body) => data(client.post('/carriers', body)),
    update: (id, body) => data(client.patch(`/carriers/${id}`, body)),
    remove: (id) => data(client.delete(`/carriers/${id}`)),
  },

  routes: {
    list: (params) => data(client.get('/routes', { params: clean(params) })),
    get: (id) => data(client.get(`/routes/${id}`)),
    create: (body) => data(client.post('/routes', body)),
    update: (id, body) => data(client.patch(`/routes/${id}`, body)),
    remove: (id) => data(client.delete(`/routes/${id}`)),
  },

  alerts: {
    list: (params) => data(client.get('/alerts', { params: clean(params) })),
    counts: () => data(client.get('/alerts/counts')),
    resolve: (id, note) => data(client.post(`/alerts/${id}/resolve`, { note: note || null })),
    queueScan: () => data(client.post('/alerts/scan')),
    scanStatus: (taskId) => data(client.get(`/alerts/scan/${taskId}`)),
    lastScan: () => data(client.get('/alerts/scan/last')),
  },
}

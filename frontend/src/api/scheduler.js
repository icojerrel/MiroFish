/**
 * Scheduler API module — manage automated scrape-ingest sources.
 */
import service from './index'

export const listSources = (projectId) =>
  service.get('/api/scheduler/sources', { params: projectId ? { project_id: projectId } : {} })

export const createSource = (payload) =>
  service.post('/api/scheduler/sources', payload)

export const getSource = (sourceId) =>
  service.get(`/api/scheduler/sources/${sourceId}`)

export const toggleSource = (sourceId, enabled) =>
  service.patch(`/api/scheduler/sources/${sourceId}`, { enabled })

export const deleteSource = (sourceId) =>
  service.delete(`/api/scheduler/sources/${sourceId}`)

export const runSourceNow = (sourceId) =>
  service.post(`/api/scheduler/sources/${sourceId}/run`)

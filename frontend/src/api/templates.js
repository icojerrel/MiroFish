/**
 * Templates API module — use-case simulation templates.
 */
import service from './index'

export const listTemplates = () => service.get('/api/templates')

export const getTemplate = (templateId) => service.get(`/api/templates/${templateId}`)

export const applyTemplate = (templateId, projectId, opts = {}) =>
  service.post(`/api/templates/${templateId}/apply`, {
    project_id: projectId,
    create_schedule: opts.createSchedule || false,
    interval_minutes: opts.intervalMinutes || 60,
  })

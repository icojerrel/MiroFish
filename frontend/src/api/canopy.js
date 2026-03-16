/**
 * Canopy Integration API module
 * Calls MiroFish backend endpoints that proxy to the Canopy workspace.
 */

import service from './index'

/** Check Canopy connection status */
export const getCanopyStatus = () => service.get('/api/canopy/status')

/** Post a test message to the configured Canopy channel */
export const testCanopyConnection = (message) =>
  service.post('/api/canopy/test', { message })

/** Manually push a completed report to Canopy */
export const pushReportToCanopy = (reportId) =>
  service.post('/api/canopy/push-report', { report_id: reportId })

/**
 * Scraper API module
 * Fetch and ingest web content into MiroFish projects via Scrapling.
 */

import service from './index'

/**
 * Scrape 1–10 URLs and return combined clean text.
 * @param {string[]} urls
 * @param {'auto'|'basic'|'stealthy'|'dynamic'} mode
 */
export const fetchUrls = (urls, mode = 'auto') =>
  service.post('/api/scraper/fetch', { urls, mode })

/**
 * Start an async domain crawl.
 * @param {string} url
 * @param {number} maxPages
 * @param {'basic'|'stealthy'|'dynamic'} mode
 */
export const crawlDomain = (url, maxPages = 20, mode = 'basic') =>
  service.post('/api/scraper/crawl', { url, max_pages: maxPages, mode })

/**
 * Scrape URLs and append text to a project (ready for graph building).
 * @param {string} projectId
 * @param {string[]} urls
 * @param {object} opts
 */
export const ingestToProject = (projectId, urls, opts = {}) =>
  service.post('/api/scraper/ingest', {
    project_id: projectId,
    urls,
    mode: opts.mode || 'auto',
    crawl: opts.crawl || false,
    max_pages: opts.maxPages || 20,
  })

/**
 * Poll a crawl task's status.
 * @param {string} taskId
 */
export const getScraperTask = (taskId) =>
  service.get(`/api/scraper/tasks/${taskId}`)

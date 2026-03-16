"""
Scraper API routes
Provides web scraping endpoints that feed directly into the MiroFish
graph building pipeline.

Flow:
  POST /api/scraper/fetch    → scrape 1-N URLs, return text preview
  POST /api/scraper/crawl    → async domain crawl (task-based)
  POST /api/scraper/ingest   → scrape URLs and append to project's text
  GET  /api/scraper/tasks/:id → poll crawl task status
"""

import threading
import traceback
from flask import request, jsonify

from . import scraper_bp
from ..config import Config
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..services.scraper_service import ScraperService
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.scraper')


# ---------------------------------------------------------------------------
# Single / batch fetch (synchronous, returns text preview)
# ---------------------------------------------------------------------------

@scraper_bp.route('/fetch', methods=['POST'])
def fetch_urls():
    """
    Scrape 1–10 URLs and return combined clean text.

    Request (JSON):
        {
            "urls":  ["https://example.com/article"],  // required, max 10
            "mode":  "auto"                            // auto|basic|stealthy|dynamic
        }

    Response:
        {
            "success": true,
            "data": {
                "pages_scraped": 3,
                "total_words": 12400,
                "preview": "first 500 chars...",
                "pages": [{ "url":..., "word_count":..., "success":... }]
            }
        }
    """
    try:
        data = request.get_json() or {}
        urls = data.get('urls', [])
        mode = data.get('mode', 'auto')

        if not urls:
            return jsonify({'success': False, 'error': 'urls required'}), 400
        if len(urls) > 10:
            return jsonify({'success': False, 'error': 'max 10 URLs per fetch'}), 400

        svc = ScraperService()
        result = svc.fetch_urls(urls, mode=mode)

        return jsonify({
            'success': True,
            'data': {
                **result.to_dict(),
                'preview': result.combined_text[:500],
                'combined_text': result.combined_text,
            }
        })

    except Exception as exc:
        logger.error(f'Scraper fetch failed: {exc}')
        return jsonify({'success': False, 'error': str(exc),
                        'traceback': traceback.format_exc()}), 500


# ---------------------------------------------------------------------------
# Domain crawl (async task)
# ---------------------------------------------------------------------------

@scraper_bp.route('/crawl', methods=['POST'])
def crawl_domain():
    """
    Start an async domain crawl (returns task_id immediately).

    Request (JSON):
        {
            "url":       "https://example.com",  // required
            "max_pages": 20,                     // default 20, max 100
            "mode":      "basic"                 // fetcher mode
        }

    Response:
        { "success": true, "data": { "task_id": "task_xxxx" } }
    """
    try:
        data = request.get_json() or {}
        url = data.get('url')
        max_pages = min(int(data.get('max_pages', 20)), 100)
        mode = data.get('mode', 'basic')

        if not url:
            return jsonify({'success': False, 'error': 'url required'}), 400

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type='scraper_crawl',
            metadata={'url': url, 'max_pages': max_pages, 'mode': mode},
        )

        def run_crawl():
            try:
                task_manager.update_task(task_id, status=TaskStatus.PROCESSING,
                                         progress=0, message=f'Crawling {url}…')
                svc = ScraperService()

                def on_progress(done, total, page_url):
                    pct = int(done / total * 100)
                    task_manager.update_task(task_id, progress=pct,
                                             message=f'[{done}/{total}] {page_url}')

                result = svc.crawl_domain(url, max_pages=max_pages, mode=mode,
                                          progress_callback=on_progress)
                task_manager.complete_task(task_id, result={
                    **result.to_dict(),
                    'combined_text': result.combined_text,
                })
            except Exception as exc:
                logger.error(f'Crawl task failed: {exc}')
                task_manager.fail_task(task_id, str(exc))

        threading.Thread(target=run_crawl, daemon=True).start()

        return jsonify({'success': True, 'data': {'task_id': task_id}})

    except Exception as exc:
        logger.error(f'Crawl start failed: {exc}')
        return jsonify({'success': False, 'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Ingest: scrape → append to project extracted text
# ---------------------------------------------------------------------------

@scraper_bp.route('/ingest', methods=['POST'])
def ingest_to_project():
    """
    Scrape URLs and append the clean text to a project's document corpus.
    After this, call /api/graph/build-graph as usual.

    Request (JSON):
        {
            "project_id": "proj_xxxx",
            "urls":        ["https://...", "https://..."],
            "mode":        "auto",
            "crawl":       false,   // true = crawl domain instead of single URLs
            "max_pages":   20       // only used when crawl=true
        }

    Response:
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "pages_added": 4,
                "words_added": 9800,
                "total_text_length": 45000
            }
        }
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        urls = data.get('urls', [])
        mode = data.get('mode', 'auto')
        do_crawl = data.get('crawl', False)
        max_pages = min(int(data.get('max_pages', 20)), 100)

        if not project_id:
            return jsonify({'success': False, 'error': 'project_id required'}), 400
        if not urls:
            return jsonify({'success': False, 'error': 'urls required'}), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': f'Project not found: {project_id}'}), 404

        svc = ScraperService()

        if do_crawl and len(urls) == 1:
            result = svc.crawl_domain(urls[0], max_pages=max_pages, mode=mode)
        else:
            result = svc.fetch_urls(urls, mode=mode)

        if not result.combined_text.strip():
            return jsonify({'success': False,
                            'error': 'No text could be extracted from the provided URLs'}), 422

        # Append scraped text to existing project text
        existing = ProjectManager.get_extracted_text(project_id) or ''
        separator = '\n\n--- WEB SOURCES ---\n\n' if existing and '--- WEB SOURCES ---' not in existing else '\n\n'
        updated_text = existing + separator + result.combined_text
        ProjectManager.save_extracted_text(project_id, updated_text)

        logger.info(f'Ingested {result.words_added if hasattr(result, "words_added") else result.total_words} '
                    f'words into project {project_id}')

        return jsonify({
            'success': True,
            'data': {
                'project_id': project_id,
                'pages_added': result.pages_scraped,
                'words_added': result.total_words,
                'total_text_length': len(updated_text),
            }
        })

    except Exception as exc:
        logger.error(f'Ingest failed: {exc}')
        return jsonify({'success': False, 'error': str(exc),
                        'traceback': traceback.format_exc()}), 500


# ---------------------------------------------------------------------------
# Task status poll
# ---------------------------------------------------------------------------

@scraper_bp.route('/tasks/<task_id>', methods=['GET'])
def get_scraper_task(task_id: str):
    """Poll the status of a crawl task."""
    try:
        task = TaskManager().get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': f'Task not found: {task_id}'}), 404
        return jsonify({'success': True, 'data': task.to_dict()})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500

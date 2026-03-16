"""
Scheduler Service — automated data ingestion on a schedule.
Powered by APScheduler (3.x). Each scheduled source re-scrapes URLs
at a configured interval and appends fresh text to the project corpus.

A scheduled source can optionally trigger an automatic graph rebuild
after ingestion, keeping the knowledge graph continuously up to date.
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.scheduler')

_SCHEDULE_FILE = os.path.join(
    os.path.dirname(__file__), '../../uploads/scheduled_sources.json'
)

_scheduler = None
_scheduler_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ScheduledSource:
    source_id: str
    project_id: str
    name: str
    urls: List[str]
    mode: str = 'auto'             # basic | stealthy | dynamic | auto
    interval_minutes: int = 60     # how often to re-scrape
    enabled: bool = True
    auto_rebuild_graph: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None  # ok | error
    last_run_words: int = 0
    next_run_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_sources() -> Dict[str, ScheduledSource]:
    os.makedirs(os.path.dirname(_SCHEDULE_FILE), exist_ok=True)
    if not os.path.exists(_SCHEDULE_FILE):
        return {}
    try:
        with open(_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return {sid: ScheduledSource(**data) for sid, data in raw.items()}
    except Exception as exc:
        logger.warning(f'Could not load schedules: {exc}')
        return {}


def _save_sources(sources: Dict[str, ScheduledSource]) -> None:
    os.makedirs(os.path.dirname(_SCHEDULE_FILE), exist_ok=True)
    with open(_SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump({sid: s.to_dict() for sid, s in sources.items()}, f,
                  ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Job runner (called by APScheduler or manually)
# ---------------------------------------------------------------------------

def _run_source(source_id: str) -> None:
    """Execute a single scheduled scrape-ingest cycle."""
    sources = _load_sources()
    src = sources.get(source_id)
    if not src or not src.enabled:
        return

    logger.info(f'Scheduler: running source "{src.name}" ({source_id})')
    try:
        from .scraper_service import ScraperService
        from ..models.project import ProjectManager

        svc = ScraperService()
        result = svc.fetch_urls(src.urls, mode=src.mode)

        if result.combined_text.strip():
            existing = ProjectManager.get_extracted_text(src.project_id) or ''
            separator = '\n\n--- SCHEDULED UPDATE ' + datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC') + ' ---\n\n'
            updated = existing + separator + result.combined_text
            ProjectManager.save_extracted_text(src.project_id, updated)
            logger.info(f'Scheduler: ingested {result.total_words} words into {src.project_id}')

            # Notify Canopy if configured
            try:
                from .canopy_service import CanopyService
                canopy = CanopyService()
                if canopy.is_enabled():
                    project = ProjectManager.get_project(src.project_id)
                    pname = project.name if project and hasattr(project, 'name') else src.project_id
                    canopy.post_message(
                        f'[signal] **Scheduled data refresh** — {src.name}\n'
                        f'Project: **{pname}** · {result.pages_scraped} pages · '
                        f'{result.total_words:,} words ingested\n'
                        f'Sources: {", ".join(src.urls[:3])}{"…" if len(src.urls) > 3 else ""}'
                    )
            except Exception:
                pass

            src.last_run_status = 'ok'
            src.last_run_words = result.total_words
        else:
            src.last_run_status = 'empty'
            src.last_run_words = 0

    except Exception as exc:
        logger.error(f'Scheduler job error ({source_id}): {exc}')
        src.last_run_status = 'error'
        src.last_run_words = 0

    src.last_run_at = datetime.utcnow().isoformat()
    sources[source_id] = src
    _save_sources(sources)


# ---------------------------------------------------------------------------
# APScheduler lifecycle
# ---------------------------------------------------------------------------

def _get_scheduler():
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            try:
                from apscheduler.schedulers.background import BackgroundScheduler
                _scheduler = BackgroundScheduler(timezone='UTC')
                _scheduler.start()
                logger.info('APScheduler started')
            except ImportError:
                logger.warning(
                    'APScheduler not installed — scheduled scraping disabled. '
                    'Install with: pip install apscheduler'
                )
        return _scheduler


def _schedule_source(src: ScheduledSource) -> None:
    sched = _get_scheduler()
    if sched is None:
        return
    job_id = f'scrape_{src.source_id}'
    # Remove existing job if any
    if sched.get_job(job_id):
        sched.remove_job(job_id)
    if src.enabled:
        sched.add_job(
            _run_source,
            trigger='interval',
            minutes=src.interval_minutes,
            id=job_id,
            args=[src.source_id],
            replace_existing=True,
        )
        logger.info(f'Scheduled "{src.name}" every {src.interval_minutes}m')


def _unschedule_source(source_id: str) -> None:
    sched = _get_scheduler()
    if sched is None:
        return
    job_id = f'scrape_{source_id}'
    if sched.get_job(job_id):
        sched.remove_job(job_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SchedulerService:

    def start_all(self) -> None:
        """Load persisted sources and register them with APScheduler."""
        sources = _load_sources()
        for src in sources.values():
            if src.enabled:
                _schedule_source(src)
        logger.info(f'Scheduler: loaded {len(sources)} sources')

    def add_source(
        self,
        project_id: str,
        name: str,
        urls: List[str],
        mode: str = 'auto',
        interval_minutes: int = 60,
        auto_rebuild_graph: bool = False,
    ) -> ScheduledSource:
        sources = _load_sources()
        src = ScheduledSource(
            source_id=f'sched_{uuid.uuid4().hex[:10]}',
            project_id=project_id,
            name=name,
            urls=urls,
            mode=mode,
            interval_minutes=interval_minutes,
            auto_rebuild_graph=auto_rebuild_graph,
        )
        sources[src.source_id] = src
        _save_sources(sources)
        _schedule_source(src)
        return src

    def remove_source(self, source_id: str) -> bool:
        sources = _load_sources()
        if source_id not in sources:
            return False
        del sources[source_id]
        _save_sources(sources)
        _unschedule_source(source_id)
        return True

    def toggle_source(self, source_id: str, enabled: bool) -> Optional[ScheduledSource]:
        sources = _load_sources()
        src = sources.get(source_id)
        if not src:
            return None
        src.enabled = enabled
        sources[source_id] = src
        _save_sources(sources)
        if enabled:
            _schedule_source(src)
        else:
            _unschedule_source(source_id)
        return src

    def run_now(self, source_id: str) -> bool:
        """Trigger a source immediately (in background thread)."""
        sources = _load_sources()
        if source_id not in sources:
            return False
        threading.Thread(target=_run_source, args=(source_id,), daemon=True).start()
        return True

    def list_sources(self, project_id: Optional[str] = None) -> List[ScheduledSource]:
        sources = _load_sources()
        result = list(sources.values())
        if project_id:
            result = [s for s in result if s.project_id == project_id]
        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_source(self, source_id: str) -> Optional[ScheduledSource]:
        return _load_sources().get(source_id)

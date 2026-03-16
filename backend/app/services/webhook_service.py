"""
Webhook Notification Service
Fires HTTP POST events to configured endpoints when MiroFish events occur.

Supported events:
  report.completed      — prediction report generated
  simulation.completed  — OASIS simulation finished
  simulation.failed     — simulation error
  graph.built           — knowledge graph construction done
  scrape.ingested       — scheduled data refresh completed

Configure via .env:
  WEBHOOK_URL     = https://your-endpoint.example.com/mirofish-events
  WEBHOOK_SECRET  = optional HMAC-SHA256 signing secret
"""

import hashlib
import hmac
import json
import threading
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.webhook')


def _sign_payload(payload: str, secret: str) -> str:
    """Return HMAC-SHA256 hex digest for Payload integrity verification."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _fire(event: str, data: Dict[str, Any]) -> None:
    """Send a single webhook POST (called in a daemon thread)."""
    url = Config.WEBHOOK_URL
    if not url:
        return

    body = {
        'event': event,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'source': 'mirofish',
        'data': data,
    }
    payload_str = json.dumps(body, ensure_ascii=False)
    headers = {'Content-Type': 'application/json'}

    secret = Config.WEBHOOK_SECRET
    if secret:
        headers['X-MiroFish-Signature'] = _sign_payload(payload_str, secret)

    try:
        resp = requests.post(url, data=payload_str.encode('utf-8'),
                             headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f'Webhook fired: {event} → {resp.status_code}')
    except Exception as exc:
        logger.warning(f'Webhook delivery failed ({event}): {exc}')


class WebhookService:
    """Non-blocking webhook dispatcher. All calls fire in background threads."""

    @staticmethod
    def _dispatch(event: str, data: Dict[str, Any]) -> None:
        if not Config.WEBHOOK_URL:
            return
        threading.Thread(target=_fire, args=(event, data), daemon=True).start()

    # ------------------------------------------------------------------
    # Event senders
    # ------------------------------------------------------------------

    @classmethod
    def report_completed(
        cls,
        report_id: str,
        simulation_id: str,
        project_id: str,
        project_name: Optional[str] = None,
    ) -> None:
        cls._dispatch('report.completed', {
            'report_id': report_id,
            'simulation_id': simulation_id,
            'project_id': project_id,
            'project_name': project_name,
        })

    @classmethod
    def simulation_completed(
        cls,
        simulation_id: str,
        project_id: str,
        total_rounds: int,
        total_actions: int,
    ) -> None:
        cls._dispatch('simulation.completed', {
            'simulation_id': simulation_id,
            'project_id': project_id,
            'total_rounds': total_rounds,
            'total_actions': total_actions,
        })

    @classmethod
    def simulation_failed(
        cls,
        simulation_id: str,
        project_id: str,
        error: str,
    ) -> None:
        cls._dispatch('simulation.failed', {
            'simulation_id': simulation_id,
            'project_id': project_id,
            'error': error,
        })

    @classmethod
    def graph_built(
        cls,
        project_id: str,
        graph_id: str,
        node_count: Optional[int] = None,
    ) -> None:
        cls._dispatch('graph.built', {
            'project_id': project_id,
            'graph_id': graph_id,
            'node_count': node_count,
        })

    @classmethod
    def scrape_ingested(
        cls,
        project_id: str,
        source_name: str,
        pages_scraped: int,
        words_added: int,
    ) -> None:
        cls._dispatch('scrape.ingested', {
            'project_id': project_id,
            'source_name': source_name,
            'pages_scraped': pages_scraped,
            'words_added': words_added,
        })

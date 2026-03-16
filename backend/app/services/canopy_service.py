"""
Canopy Integration Service
Connects MiroFish to a Canopy workspace for encrypted team collaboration.

Canopy is a local-first, P2P encrypted workspace (Slack alternative).
This service posts prediction reports, simulation signals, and handles
@mention commands from team members via Canopy's REST API.

API base: http://<canopy_host>:<canopy_port>/api/v1
Auth:     X-API-Key header with a scoped agent key
"""

import json
import textwrap
from datetime import datetime
from typing import Optional

import requests

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.canopy')


class CanopyService:
    """Client for Canopy's REST API."""

    def __init__(self):
        self.base_url = Config.CANOPY_BASE_URL.rstrip('/')
        self.api_key = Config.CANOPY_API_KEY
        self.channel_id = Config.CANOPY_CHANNEL_ID
        self.enabled = bool(self.base_url and self.api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
        }

    def _post(self, path: str, payload: dict) -> Optional[dict]:
        if not self.enabled:
            logger.debug('Canopy integration disabled — skipping post')
            return None
        try:
            url = f'{self.base_url}/api/v1{path}'
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f'Canopy POST {path} failed: {exc}')
            return None

    def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        if not self.enabled:
            return None
        try:
            url = f'{self.base_url}/api/v1{path}'
            resp = requests.get(url, params=params, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f'Canopy GET {path} failed: {exc}')
            return None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        return self.enabled

    def test_connection(self) -> dict:
        """Ping the Canopy instance and return status info."""
        if not self.enabled:
            return {'ok': False, 'reason': 'Canopy not configured'}
        try:
            url = f'{self.base_url}/api/v1/info'
            resp = requests.get(url, headers=self._headers(), timeout=5)
            resp.raise_for_status()
            return {'ok': True, 'info': resp.json()}
        except Exception as exc:
            return {'ok': False, 'reason': str(exc)}

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def post_message(self, content: str, channel_id: Optional[str] = None) -> Optional[dict]:
        """Post a plain text message to a Canopy channel."""
        cid = channel_id or self.channel_id
        if not cid:
            logger.warning('Canopy: no channel_id configured')
            return None
        return self._post(f'/channels/{cid}/messages', {'content': content})

    def reply_to_mention(self, mention_id: str, content: str) -> Optional[dict]:
        """Reply to an agent inbox mention."""
        return self._post(f'/agents/me/inbox/{mention_id}/reply', {'content': content})

    def claim_mention(self, mention_id: str) -> Optional[dict]:
        """Claim a mention so other agents don't pile on."""
        return self._post(f'/agents/me/inbox/{mention_id}/claim', {})

    # ------------------------------------------------------------------
    # Inbox
    # ------------------------------------------------------------------

    def get_inbox(self) -> list:
        """Return pending inbox items for this agent."""
        data = self._get('/agents/me/inbox')
        if data and isinstance(data, list):
            return data
        if data and 'items' in data:
            return data['items']
        return []

    def heartbeat(self) -> Optional[dict]:
        """Poll workload hints from Canopy."""
        return self._get('/agents/me/heartbeat')

    # ------------------------------------------------------------------
    # MiroFish-specific posts
    # ------------------------------------------------------------------

    def post_simulation_signal(
        self,
        project_name: str,
        simulation_id: str,
        status: str,
        progress: int,
        round_num: Optional[int] = None,
        channel_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Post a [signal] block when simulation status changes."""
        round_info = f' · round {round_num}' if round_num is not None else ''
        ts = datetime.utcnow().strftime('%H:%M UTC')
        content = textwrap.dedent(f"""\
            [signal] **MiroFish Simulation Update** — {ts}
            Project: **{project_name}**
            Simulation ID: `{simulation_id}`
            Status: `{status}`{round_info}
            Progress: {progress}%
        """)
        return self.post_message(content, channel_id=channel_id)

    def post_report(
        self,
        project_name: str,
        report_id: str,
        simulation_id: str,
        summary: str,
        channel_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Post a completed prediction report as a Canopy message with a [task] block."""
        ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        # Truncate summary to keep the message readable in Canopy
        short_summary = summary[:1200].rstrip() + ('…' if len(summary) > 1200 else '')
        content = textwrap.dedent(f"""\
            [task] **MiroFish Prediction Report Ready** — {ts}
            Project: **{project_name}**
            Report ID: `{report_id}`
            Simulation ID: `{simulation_id}`

            ---
            {short_summary}
            ---

            Review the full report in MiroFish → Step 4.
        """)
        result = self.post_message(content, channel_id=channel_id)
        if result:
            logger.info(f'Canopy: posted report {report_id} to channel')
        return result

    def post_graph_built(
        self,
        project_name: str,
        project_id: str,
        graph_id: str,
        node_count: Optional[int] = None,
        channel_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Notify Canopy when a knowledge graph has been built."""
        node_info = f' ({node_count} nodes)' if node_count else ''
        ts = datetime.utcnow().strftime('%H:%M UTC')
        content = textwrap.dedent(f"""\
            [signal] **MiroFish Knowledge Graph Built** — {ts}
            Project: **{project_name}**  (`{project_id}`)
            Graph ID: `{graph_id}`{node_info}
            Ready to configure simulation in Step 3.
        """)
        return self.post_message(content, channel_id=channel_id)

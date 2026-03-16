"""
Canopy Agent Inbox Listener
Background daemon thread that polls the Canopy agent inbox and routes
@mention commands to MiroFish actions.

Supported mention commands (case-insensitive):
  @mirofish status              — list recent simulations
  @mirofish report <sim_id>     — fetch report summary for a simulation
  @mirofish help                — show available commands
"""

import re
import threading
import time

from ..config import Config
from ..utils.logger import get_logger
from .canopy_service import CanopyService

logger = get_logger('mirofish.canopy_agent')

_agent_thread: threading.Thread | None = None
_stop_event = threading.Event()


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _handle_status(canopy: CanopyService, mention_id: str) -> str:
    try:
        from ..services.simulation_manager import SimulationManager
        manager = SimulationManager()
        sims = manager.list_simulations(limit=5)
        if not sims:
            return 'No simulations found yet. Start one in MiroFish Step 3.'
        lines = ['**Recent simulations:**']
        for s in sims:
            lines.append(f'• `{s.simulation_id}` — {s.status} ({s.project_id})')
        return '\n'.join(lines)
    except Exception as exc:
        logger.error(f'Canopy agent status error: {exc}')
        return f'Could not retrieve simulations: {exc}'


def _handle_report(canopy: CanopyService, mention_id: str, sim_id: str) -> str:
    try:
        from ..services.report_agent import ReportManager, ReportStatus
        report = ReportManager.get_report_by_simulation(sim_id)
        if not report:
            return f'No report found for simulation `{sim_id}`.'
        if report.status != ReportStatus.COMPLETED:
            return f'Report for `{sim_id}` is still **{report.status.value}**.'
        summary = (report.markdown_content or '')[:800].rstrip()
        if len(report.markdown_content or '') > 800:
            summary += '…'
        return f'**Report `{report.report_id}`** for simulation `{sim_id}`:\n\n{summary}'
    except Exception as exc:
        logger.error(f'Canopy agent report error: {exc}')
        return f'Could not retrieve report: {exc}'


def _handle_help() -> str:
    return (
        '**MiroFish Agent — available commands:**\n'
        '• `@mirofish status` — list recent simulations\n'
        '• `@mirofish report <simulation_id>` — get report summary\n'
        '• `@mirofish help` — show this message'
    )


# ---------------------------------------------------------------------------
# Inbox loop
# ---------------------------------------------------------------------------

def _process_inbox(canopy: CanopyService) -> None:
    items = canopy.get_inbox()
    for item in items:
        mention_id = item.get('id') or item.get('mention_id')
        if not mention_id:
            continue

        text = (item.get('content') or item.get('message') or '').strip().lower()

        # Claim the mention to prevent double-handling
        canopy.claim_mention(mention_id)

        if 'help' in text:
            reply = _handle_help()
        elif 'status' in text:
            reply = _handle_status(canopy, mention_id)
        elif 'report' in text:
            m = re.search(r'report\s+(sim_\w+)', text)
            sim_id = m.group(1) if m else ''
            if sim_id:
                reply = _handle_report(canopy, mention_id, sim_id)
            else:
                reply = 'Usage: `@mirofish report <simulation_id>`'
        else:
            reply = _handle_help()

        canopy.reply_to_mention(mention_id, reply)
        logger.info(f'Canopy: handled mention {mention_id}')


def _inbox_loop(poll_interval: int) -> None:
    canopy = CanopyService()
    logger.info(f'Canopy agent inbox listener started (poll every {poll_interval}s)')
    while not _stop_event.is_set():
        try:
            _process_inbox(canopy)
        except Exception as exc:
            logger.warning(f'Canopy inbox poll error: {exc}')
        _stop_event.wait(poll_interval)
    logger.info('Canopy agent inbox listener stopped')


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def start_canopy_agent() -> None:
    """Start the background inbox listener if Canopy is configured."""
    global _agent_thread

    if not Config.CANOPY_API_KEY or not Config.CANOPY_BASE_URL:
        logger.debug('Canopy not configured — inbox listener not started')
        return

    if _agent_thread and _agent_thread.is_alive():
        return

    _stop_event.clear()
    poll_interval = Config.CANOPY_POLL_INTERVAL
    _agent_thread = threading.Thread(
        target=_inbox_loop,
        args=(poll_interval,),
        daemon=True,
        name='canopy-inbox-listener',
    )
    _agent_thread.start()


def stop_canopy_agent() -> None:
    """Signal the inbox listener to stop."""
    _stop_event.set()

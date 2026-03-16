"""
Scheduler API — manage automated scrape-ingest sources.

POST   /api/scheduler/sources           create a scheduled source
GET    /api/scheduler/sources           list all (optionally filter by project)
GET    /api/scheduler/sources/:id       get one source
PATCH  /api/scheduler/sources/:id       enable/disable
DELETE /api/scheduler/sources/:id       remove
POST   /api/scheduler/sources/:id/run   trigger immediately
"""

import traceback
from flask import request, jsonify

from . import scheduler_bp
from ..services.scheduler_service import SchedulerService
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.scheduler')
_svc = SchedulerService()


@scheduler_bp.route('/sources', methods=['POST'])
def create_source():
    """
    Create a scheduled scrape source.

    Request (JSON):
        {
            "project_id":         "proj_xxxx",
            "name":               "Reuters Energy Desk",
            "urls":               ["https://reuters.com/...", "..."],
            "mode":               "auto",
            "interval_minutes":   60,
            "auto_rebuild_graph": false
        }
    """
    try:
        d = request.get_json() or {}
        for required in ('project_id', 'name', 'urls'):
            if not d.get(required):
                return jsonify({'success': False, 'error': f'{required} required'}), 400

        src = _svc.add_source(
            project_id=d['project_id'],
            name=d['name'],
            urls=d['urls'],
            mode=d.get('mode', 'auto'),
            interval_minutes=int(d.get('interval_minutes', 60)),
            auto_rebuild_graph=bool(d.get('auto_rebuild_graph', False)),
        )
        return jsonify({'success': True, 'data': src.to_dict()}), 201
    except Exception as exc:
        logger.error(f'Create source failed: {exc}')
        return jsonify({'success': False, 'error': str(exc),
                        'traceback': traceback.format_exc()}), 500


@scheduler_bp.route('/sources', methods=['GET'])
def list_sources():
    try:
        project_id = request.args.get('project_id')
        sources = _svc.list_sources(project_id=project_id)
        return jsonify({'success': True, 'data': [s.to_dict() for s in sources],
                        'count': len(sources)})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@scheduler_bp.route('/sources/<source_id>', methods=['GET'])
def get_source(source_id):
    try:
        src = _svc.get_source(source_id)
        if not src:
            return jsonify({'success': False, 'error': f'Source not found: {source_id}'}), 404
        return jsonify({'success': True, 'data': src.to_dict()})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@scheduler_bp.route('/sources/<source_id>', methods=['PATCH'])
def toggle_source(source_id):
    """Enable or disable a scheduled source. Body: { "enabled": true }"""
    try:
        d = request.get_json() or {}
        enabled = d.get('enabled')
        if enabled is None:
            return jsonify({'success': False, 'error': 'enabled field required'}), 400
        src = _svc.toggle_source(source_id, bool(enabled))
        if not src:
            return jsonify({'success': False, 'error': f'Source not found: {source_id}'}), 404
        return jsonify({'success': True, 'data': src.to_dict()})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@scheduler_bp.route('/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id):
    try:
        ok = _svc.remove_source(source_id)
        if not ok:
            return jsonify({'success': False, 'error': f'Source not found: {source_id}'}), 404
        return jsonify({'success': True, 'message': f'Source removed: {source_id}'})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@scheduler_bp.route('/sources/<source_id>/run', methods=['POST'])
def run_now(source_id):
    """Trigger a source immediately (non-blocking)."""
    try:
        ok = _svc.run_now(source_id)
        if not ok:
            return jsonify({'success': False, 'error': f'Source not found: {source_id}'}), 404
        return jsonify({'success': True, 'message': 'Source triggered in background'})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500

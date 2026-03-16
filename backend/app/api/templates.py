"""
Use-case Templates API
Pre-built simulation configurations for each enterprise scenario.

GET  /api/templates          list all templates
GET  /api/templates/:id      get one template
POST /api/templates/:id/apply apply template to a project
"""

import json
import os
import traceback
from flask import request, jsonify

from . import templates_bp
from ..models.project import ProjectManager
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.templates')

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '../data/templates')


def _load_all() -> list:
    templates = []
    if not os.path.isdir(_TEMPLATES_DIR):
        return templates
    for fname in sorted(os.listdir(_TEMPLATES_DIR)):
        if fname.endswith('.json'):
            try:
                with open(os.path.join(_TEMPLATES_DIR, fname), 'r', encoding='utf-8') as f:
                    templates.append(json.load(f))
            except Exception as exc:
                logger.warning(f'Could not load template {fname}: {exc}')
    return templates


def _load_one(template_id: str) -> dict | None:
    path = os.path.join(_TEMPLATES_DIR, f'{template_id}.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


@templates_bp.route('', methods=['GET'])
def list_templates():
    """Return all available use-case templates (metadata only)."""
    templates = _load_all()
    # Strip heavy fields for list view
    summary_keys = ['id', 'name', 'icon', 'description', 'use_case', 'key_metrics']
    summaries = [{k: t[k] for k in summary_keys if k in t} for t in templates]
    return jsonify({'success': True, 'data': summaries, 'count': len(summaries)})


@templates_bp.route('/<template_id>', methods=['GET'])
def get_template(template_id: str):
    """Return full template detail."""
    tmpl = _load_one(template_id)
    if not tmpl:
        return jsonify({'success': False, 'error': f'Template not found: {template_id}'}), 404
    return jsonify({'success': True, 'data': tmpl})


@templates_bp.route('/<template_id>/apply', methods=['POST'])
def apply_template(template_id: str):
    """
    Apply a template to an existing project.

    Sets simulation_requirement on the project and optionally creates
    a scheduled scraping source for the template's suggested URLs.

    Request (JSON):
        {
            "project_id":      "proj_xxxx",          // required
            "create_schedule": true,                 // optional
            "interval_minutes": 60                   // optional
        }
    """
    try:
        tmpl = _load_one(template_id)
        if not tmpl:
            return jsonify({'success': False, 'error': f'Template not found: {template_id}'}), 404

        data = request.get_json() or {}
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({'success': False, 'error': 'project_id required'}), 400

        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': f'Project not found: {project_id}'}), 404

        # Apply simulation_requirement
        project.simulation_requirement = tmpl['simulation_requirement']
        ProjectManager.save_project(project)

        schedule_info = None
        if data.get('create_schedule') and tmpl.get('suggested_urls'):
            from ..services.scheduler_service import SchedulerService
            svc = SchedulerService()
            src = svc.add_source(
                project_id=project_id,
                name=f"{tmpl['name']} — auto feed",
                urls=tmpl['suggested_urls'],
                mode=tmpl.get('scrape_mode', 'auto'),
                interval_minutes=int(
                    data.get('interval_minutes', tmpl.get('scrape_interval_minutes', 60))
                ),
            )
            schedule_info = src.to_dict()

        return jsonify({
            'success': True,
            'data': {
                'project_id': project_id,
                'template_id': template_id,
                'simulation_requirement': tmpl['simulation_requirement'],
                'scheduled_source': schedule_info,
                'suggested_agent_count': tmpl.get('suggested_agent_count'),
                'suggested_rounds': tmpl.get('suggested_rounds'),
                'suggested_platform': tmpl.get('suggested_platform'),
            }
        })

    except Exception as exc:
        logger.error(f'Apply template failed: {exc}')
        return jsonify({'success': False, 'error': str(exc),
                        'traceback': traceback.format_exc()}), 500

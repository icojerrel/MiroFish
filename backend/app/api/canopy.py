"""
Canopy Integration API
Exposes Canopy connection status and manual push endpoints.
"""

import traceback
from flask import request, jsonify

from . import canopy_bp
from ..config import Config
from ..services.canopy_service import CanopyService
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.canopy')


@canopy_bp.route('/status', methods=['GET'])
def canopy_status():
    """
    Return Canopy integration status.

    Response:
        {
            "success": true,
            "data": {
                "enabled": true,
                "base_url": "http://localhost:7770",
                "channel_id": "...",
                "connected": true,
                "info": { ... }
            }
        }
    """
    try:
        canopy = CanopyService()
        result = canopy.test_connection()
        return jsonify({
            "success": True,
            "data": {
                "enabled": canopy.is_enabled(),
                "base_url": Config.CANOPY_BASE_URL,
                "channel_id": Config.CANOPY_CHANNEL_ID,
                "connected": result.get('ok', False),
                "info": result.get('info'),
                "error": result.get('reason'),
            }
        })
    except Exception as exc:
        logger.error(f'Canopy status check failed: {exc}')
        return jsonify({"success": False, "error": str(exc)}), 500


@canopy_bp.route('/test', methods=['POST'])
def canopy_test():
    """
    Post a test message to Canopy.

    Request (JSON):
        { "message": "optional custom text" }
    """
    try:
        data = request.get_json() or {}
        message = data.get('message', '✅ MiroFish → Canopy integration test successful!')
        canopy = CanopyService()
        if not canopy.is_enabled():
            return jsonify({"success": False, "error": "Canopy not configured"}), 400
        result = canopy.post_message(message)
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        logger.error(f'Canopy test failed: {exc}')
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


@canopy_bp.route('/push-report', methods=['POST'])
def canopy_push_report():
    """
    Manually push an existing report to Canopy.

    Request (JSON):
        { "report_id": "report_xxxx" }
    """
    try:
        data = request.get_json() or {}
        report_id = data.get('report_id')
        if not report_id:
            return jsonify({"success": False, "error": "report_id required"}), 400

        from ..services.report_agent import ReportManager, ReportStatus
        from ..services.simulation_manager import SimulationManager
        from ..models.project import ProjectManager

        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404
        if report.status != ReportStatus.COMPLETED:
            return jsonify({"success": False, "error": "Report not yet completed"}), 400

        sim_state = SimulationManager().get_simulation(report.simulation_id)
        project = ProjectManager.get_project(sim_state.project_id) if sim_state else None
        project_name = (project.name if project and hasattr(project, 'name') else
                        (sim_state.project_id if sim_state else report_id))

        canopy = CanopyService()
        if not canopy.is_enabled():
            return jsonify({"success": False, "error": "Canopy not configured"}), 400

        result = canopy.post_report(
            project_name=project_name,
            report_id=report.report_id,
            simulation_id=report.simulation_id,
            summary=report.markdown_content or '',
        )
        return jsonify({"success": True, "data": result})
    except Exception as exc:
        logger.error(f'Canopy push-report failed: {exc}')
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500

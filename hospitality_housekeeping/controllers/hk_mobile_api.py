# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import json

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request, Response


class HospitalityHkMobileApi(http.Controller):
    """Phase-1 REST stub for Phase-4's hospitality_staff_mobile PWA.

    Plain JSON in/out over auth='user' session auth (no JSON-RPC
    envelope) so a future PWA, or any REST client, can call these
    directly. All authorization is delegated to the existing
    hk_task_record_rule_* record rules: an attendant only ever sees
    or actions their own tasks (attendant_user_id = request user),
    a supervisor sees/actions tasks for their assigned properties.
    """

    def _json_response(self, data, status=200):
        """Return a JSON HTTP response with the specified payload and status
        code."""
        return Response(
            json.dumps(data), status=status, content_type='application/json')

    def _get_own_task(self, task_id):
        """Browse a task under the requesting user's own access
        rights (no sudo). Nothing here checks access directly: the
        first field access below (task.state, inside the action_*
        method itself) is what triggers the ORM's normal read
        check, so an attendant trying to act on someone else's task
        hits the hk_task_rule_attendant record rule and raises
        AccessError, exactly as it would from the form/kanban."""
        return request.env['hospitality.housekeeping.task'].browse(task_id)

    @http.route('/hospitality/hk/mobile/tasks', type='http', auth='user',
                methods=['GET'], csrf=False)
    def hk_mobile_tasks(self, **kwargs):
        """GET my pending + in_progress tasks for the current
        business date (the resolved current property's business_date,
        same convention as the HK Board)."""
        Task = request.env['hospitality.housekeeping.task']
        property_id = Task._get_current_property_id()
        domain = [
            ('attendant_user_id', '=', request.env.uid),
            ('state', 'in', ['pending', 'in_progress']),
        ]
        if property_id:
            business_date = request.env['hospitality.property'].browse(
                property_id).business_date
            domain.append(('business_date', '=', business_date))
        tasks = Task.search(domain)
        return self._json_response({
            'tasks': [self._task_to_dict(t) for t in tasks],
        })

    @http.route('/hospitality/hk/mobile/task/<int:task_id>/start',
                type='http', auth='user', methods=['POST'], csrf=False)
    def hk_mobile_task_start(self, task_id, **kwargs):
        """POST: assign the task to the calling user and move it to
        in_progress (action_assign)."""
        return self._do_action(task_id, lambda task: task.action_assign(
            attendant_user_id=request.env.uid))

    @http.route('/hospitality/hk/mobile/task/<int:task_id>/finish',
                type='http', auth='user', methods=['POST'], csrf=False)
    def hk_mobile_task_finish(self, task_id, **kwargs):
        """POST: mark the task done (action_finish)."""
        return self._do_action(task_id, lambda task: task.action_finish())

    @http.route('/hospitality/hk/mobile/task/<int:task_id>/dnd',
                type='http', auth='user', methods=['POST'], csrf=False)
    def hk_mobile_task_dnd(self, task_id, **kwargs):
        """POST: set the task to Do Not Disturb (action_set_dnd)."""
        return self._do_action(task_id, lambda task: task.action_set_dnd())

    def _do_action(self, task_id, action_fn):
        """Execute a task action and return a JSON response.

        Converts access and validation errors into appropriate HTTP responses.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          
        """
        try:
            task = self._get_own_task(task_id)
            action_fn(task)
        except AccessError:
            return self._json_response(
                {'error': 'access_denied'}, status=403)
        except UserError as exc:
            return self._json_response(
                {'error': str(exc)}, status=400)
        return self._json_response(self._task_to_dict(task))

    def _task_to_dict(self, task):
        """Serialize a housekeeping task into a JSON-compatible
        dictionary."""
        return {
            'id': task.id,
            'name': task.name,
            'space': task.space_id.display_name,
            'task_type': task.task_type,
            'state': task.state,
            'priority': task.priority,
            'business_date': str(task.business_date) if task.business_date
            else False,
        }
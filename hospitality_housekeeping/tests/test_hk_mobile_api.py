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

from odoo.fields import Date
from odoo.tests.common import HttpCase, tagged

# Requires --workers 0, per this project's convention for HttpCase tests.


@tagged('post_install', '-at_install')
class TestHkMobileApi(HttpCase):
    """HK-04: covers the Phase-1 mobile API stub -- own-tasks
    scoping on the GET endpoint, and that every route refuses an
    unauthenticated caller.

    NOTE: property/space fixtures use only a minimal field set. If
    hospitality.property or hospitality.space carry other required
    fields in this database, adjust setUpClass to match.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Mobile Test Property',
                'code': 'HKMOBILE',
            })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Mobile Test Type',
            })

        cls.space_mine = cls.env['hospitality.space'].create({
            'name': 'HK Mobile Test Space Mine',
            'code': 'HKMOBMINE',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space_other = cls.env['hospitality.space'].create({
            'name': 'HK Mobile Test Space Other',
            'code': 'HKMOBOTHER',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.attendant = cls.env['res.users'].create({
            'name': 'HK Mobile Attendant',
            'login': 'hk_mobile_attendant',
            'password': 'hk_mobile_attendant',
            'group_ids': [(4, cls.group_attendant.id)],
        })
        cls.other_attendant = cls.env['res.users'].create({
            'name': 'HK Mobile Other Attendant',
            'login': 'hk_mobile_other_attendant',
            'password': 'hk_mobile_other_attendant',
            'group_ids': [(4, cls.group_attendant.id)],
        })

        cls.my_task = cls.HkTask.create({
            'property_id': cls.property.id,
            'space_id': cls.space_mine.id,
            'business_date': Date.today(),
            'task_type': 'stayover',
        })
        cls.my_task.action_assign(attendant_user_id=cls.attendant.id)

        cls.other_task = cls.HkTask.create({
            'property_id': cls.property.id,
            'space_id': cls.space_other.id,
            'business_date': Date.today(),
            'task_type': 'stayover',
        })
        cls.other_task.action_assign(
            attendant_user_id=cls.other_attendant.id)

    def test_mobile_api_tasks_returns_only_mine(self):
        """GET /hospitality/hk/mobile/tasks, logged in as one
        attendant, returns that attendant's task and not the other
        attendant's task."""
        self.authenticate('hk_mobile_attendant', 'hk_mobile_attendant')
        response = self.url_open('/hospitality/hk/mobile/tasks')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        task_ids = [t['id'] for t in data['tasks']]

        self.assertIn(self.my_task.id, task_ids)
        self.assertNotIn(self.other_task.id, task_ids)

    def test_mobile_api_actions_require_auth(self):
        """Every mobile-API route rejects an unauthenticated caller
        rather than acting on the task. auth='user' redirects an
        anonymous request to the login page (a 30x), so redirects
        are disabled here to check that directly rather than
        following the chain down to the login page's own 200.

        NOTE: if this Odoo version's HttpCase.url_open() doesn't
        accept allow_redirects, drop that kwarg and instead assert
        on response.url containing 'login' after the default
        redirect-following request."""
        # Each test method starts with a fresh, already-unauthenticated
        # session, so there's nothing to log out of yet in this
        # method specifically -- only call logout() if a prior
        # authenticate() in this test actually created a session.
        if getattr(self, 'session', None) is not None:
            self.logout()

        tasks_response = self.url_open(
            '/hospitality/hk/mobile/tasks', allow_redirects=False)
        self.assertIn(tasks_response.status_code, (303, 302, 401, 403))

        start_response = self.url_open(
            '/hospitality/hk/mobile/task/%d/start' % self.my_task.id,
            data={'_': '1'}, allow_redirects=False)
        self.assertIn(start_response.status_code, (303, 302, 401, 403))

        # The task must be unaffected by the rejected call.
        self.assertEqual(self.my_task.state, 'in_progress')
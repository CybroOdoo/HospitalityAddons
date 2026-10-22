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
from datetime import timedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged

from ..models.hospitality_housekeeping_task import RESERVATION_MODEL


@tagged('post_install', '-at_install')
class TestHkIntegrationFullCycle(TransactionCase):
    """HK-06: a genuine cross-module integration test spanning
    hospitality.reservation (arrival, checkout) and
    hospitality.housekeeping.task (the full clean/inspect state
    machine), exercising both the stayover cron path and the HK-05
    real-time departure event hook in one continuous story:

    1. Reservation goes confirmed -> checked_in (arrival).
    2. The stayover cron (as it would run the next morning) creates
       a task for the now-occupied room.
    3. That task is assigned, finished, and inspected -- the space
       ends up occupied_clean.
    4. The reservation is checked out.
    5. Without calling any cron, a departure task already exists
       (the write() event hook on hospitality.reservation fired
       immediately -- see hospitality_reservation_hk_hook.py).
    6. That task is assigned, finished, and inspected -- the space
       ends up vacant_clean.
    7. Running the safety-net cron afterwards doesn't create a
       duplicate departure task.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']
        cls.Reservation = cls.env[RESERVATION_MODEL]

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Integration Test Property',
                'code': 'HKINTEG',
            })

        cls.partner = cls.env['res.partner'].create({
            'name': 'HK Integration Test Guest',
        })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Integration Test Type',
            })

        cls.rate_code = cls.env['hospitality.rate.code'].search(
            [('property_id', '=', cls.property.id)], limit=1)
        if not cls.rate_code:
            cls.rate_code = cls.env['hospitality.rate.code'].create({
                'name': 'HK Integration Test Rate',
                'code': 'HKINTEGRATE',
                'property_id': cls.property.id,
            })

        cls.space = cls.env['hospitality.space'].create({
            'name': 'HK Integration Test Space',
            'code': 'HKINT1',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.attendant_user = cls.env['res.users'].create({
            'name': 'HK Integration Test Attendant',
            'login': 'hk_integration_attendant_test',
            'group_ids': [(4, cls.group_attendant.id)],
        })

    def test_integration_arrival_to_clean_to_inspect_full_cycle(self):
        # --- 1. Arrival: confirmed -> checked_in ---
        reservation = self.Reservation.create({
            'property_id': self.property.id,
            'partner_id': self.partner.id,
            'space_type_id': self.space_type.id,
            'space_id': self.space.id,
            'rate_code_id': self.rate_code.id,
            'arrival': Date.today(),
            'departure': Date.today() + timedelta(days=2),
        })
        reservation.action_confirm()
        self.assertEqual(reservation.state, 'confirmed')
        reservation.action_check_in()
        self.assertEqual(reservation.state, 'checked_in')

        # --- 2. Stayover cron creates a task for the occupied room ---
        self.HkTask._cron_create_stayover_tasks()
        stayover_task = self.HkTask.search([
            ('space_id', '=', self.space.id),
            ('task_type', '=', 'stayover'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(len(stayover_task), 1)
        self.assertEqual(stayover_task.state, 'pending')

        # --- 3. Clean and inspect the stayover task ---
        stayover_task.action_assign(attendant_user_id=self.attendant_user.id)
        self.assertEqual(stayover_task.state, 'in_progress')
        stayover_task.action_finish()
        self.assertEqual(stayover_task.state, 'done')
        stayover_task.action_inspect()
        self.assertEqual(stayover_task.state, 'inspected')
        self.assertEqual(self.space.status, 'occupied_clean')

        # --- 4. Checkout ---
        reservation.action_check_out()
        self.assertEqual(reservation.state, 'checked_out')

        # --- 5. Departure task already exists via the write() event
        # hook -- no cron was called for this. ---
        departure_task = self.HkTask.search([
            ('space_id', '=', self.space.id),
            ('task_type', '=', 'departure'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(
            len(departure_task), 1,
            'departure task should already exist from the '
            'write() event hook, before any cron runs')
        self.assertEqual(departure_task.state, 'pending')

        # --- 6. Clean and inspect the departure task ---
        departure_task.action_assign(
            attendant_user_id=self.attendant_user.id)
        departure_task.action_finish()
        departure_task.action_inspect()
        self.assertEqual(departure_task.state, 'inspected')
        self.assertEqual(self.space.status, 'vacant_clean')

        # --- 7. Safety-net cron afterwards must not duplicate it ---
        self.HkTask._cron_create_departure_tasks()
        departure_tasks_after = self.HkTask.search([
            ('space_id', '=', self.space.id),
            ('task_type', '=', 'departure'),
        ])
        self.assertEqual(len(departure_tasks_after), 1)
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

from ..models.hospitality_housekeeping_task import (
    RESERVATION_MODEL, RESERVATION_CHECKED_IN_STATE,
    RESERVATION_CHECKED_OUT_STATE)


@tagged('post_install', '-at_install')
class TestHkCrons(TransactionCase):
    """HK-05: the three housekeeping crons.

    Reservation fixtures now use the confirmed hospitality_reservation
    schema: property_id, partner_id, arrival, departure,
    space_type_id and rate_code_id are all required=True there, and
    a @api.constrains('space_id', 'space_type_id') check requires
    the reservation's space_type_id to match space_id.space_type_id
    exactly -- hence every test space below is created with the
    same space_type_id used on its reservation.

    REMAINING ASSUMPTION: hospitality.space.type's own required
    fields aren't known (hospitality_property wasn't in hand for
    this). The search-then-create fallback below tries an existing
    type first; if none exists and creating one with just 'name'
    fails, add whatever field it's complaining about.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']
        cls.Reservation = cls.env[RESERVATION_MODEL]

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Cron Test Property',
                'code': 'HKCRON',
            })

        cls.partner = cls.env['res.partner'].create({
            'name': 'HK Cron Test Guest',
        })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Cron Test Type',
            })

        cls.rate_code = cls.env['hospitality.rate.code'].search(
            [('property_id', '=', cls.property.id)], limit=1)
        if not cls.rate_code:
            cls.rate_code = cls.env['hospitality.rate.code'].create({
                'name': 'HK Cron Test Rate',
                'code': 'HKCRONRATE',
                'property_id': cls.property.id,
            })

        cls.space_a = cls.env['hospitality.space'].create({
            'name': 'HK Cron Test Space A',
            'code': 'HKCRONA',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space_b = cls.env['hospitality.space'].create({
            'name': 'HK Cron Test Space B',
            'code': 'HKCRONB',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

    def _create_reservation(self, space, state):
        return self.Reservation.create({
            'property_id': self.property.id,
            'partner_id': self.partner.id,
            'space_type_id': space.space_type_id.id,
            'space_id': space.id,
            'rate_code_id': self.rate_code.id,
            'arrival': Date.today(),
            'departure': Date.today() + timedelta(days=1),
            'state': state,
        })

    def test_cron_creates_stayover_tasks(self):
        """A checked-in reservation with a space assigned gets a
        stayover task for the property's current business date, and
        running the cron again doesn't create a duplicate."""
        self._create_reservation(
            self.space_a, RESERVATION_CHECKED_IN_STATE)

        self.HkTask._cron_create_stayover_tasks()

        tasks = self.HkTask.search([
            ('space_id', '=', self.space_a.id),
            ('task_type', '=', 'stayover'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(len(tasks), 1)

        # Running it again must not create a second one (the unique
        # constraint on (space_id, business_date, task_type) backs
        # this up, but the cron's own pre-check should avoid ever
        # hitting it).
        self.HkTask._cron_create_stayover_tasks()
        tasks_after = self.HkTask.search([
            ('space_id', '=', self.space_a.id),
            ('task_type', '=', 'stayover'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(len(tasks_after), 1)

    def test_cron_does_not_create_stayover_for_checked_out_space(self):
        """A space with no in-house (checked-in) reservation gets no
        stayover task."""
        self._create_reservation(
            self.space_b, RESERVATION_CHECKED_OUT_STATE)

        self.HkTask._cron_create_stayover_tasks()

        tasks = self.HkTask.search([
            ('space_id', '=', self.space_b.id),
            ('task_type', '=', 'stayover'),
        ])
        self.assertFalse(tasks)

    def test_cron_creates_departure_task_on_checkout(self):
        """A reservation in the checked-out state gets its space a
        departure task for the property's current business date."""
        self._create_reservation(
            self.space_a, RESERVATION_CHECKED_OUT_STATE)

        self.HkTask._cron_create_departure_tasks()

        tasks = self.HkTask.search([
            ('space_id', '=', self.space_a.id),
            ('task_type', '=', 'departure'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(len(tasks), 1)

        # Idempotent: running it again doesn't duplicate the task.
        self.HkTask._cron_create_departure_tasks()
        tasks_after = self.HkTask.search([
            ('space_id', '=', self.space_a.id),
            ('task_type', '=', 'departure'),
        ])
        self.assertEqual(len(tasks_after), 1)

    def test_departure_task_created_immediately_on_check_out_event(self):
        """The real event path: calling action_check_out() on a
        checked-in reservation creates the departure task right
        away, without needing _cron_create_departure_tasks() to run
        at all -- confirms the write() hook on
        hospitality.reservation fires, not just the safety-net
        poll."""
        space_c = self.env['hospitality.space'].create({
            'name': 'HK Cron Test Space C',
            'code': 'HKCRONC',
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
        })
        reservation = self._create_reservation(
            space_c, RESERVATION_CHECKED_IN_STATE)

        reservation.action_check_out()

        tasks = self.HkTask.search([
            ('space_id', '=', space_c.id),
            ('task_type', '=', 'departure'),
            ('business_date', '=', self.property.business_date),
        ])
        self.assertEqual(
            len(tasks), 1,
            'departure task should exist immediately after '
            'action_check_out(), before the cron ever runs')

        # Running the safety-net cron afterwards must not duplicate
        # the task the event hook already created.
        self.HkTask._cron_create_departure_tasks()
        tasks_after = self.HkTask.search([
            ('space_id', '=', space_c.id),
            ('task_type', '=', 'departure'),
        ])
        self.assertEqual(len(tasks_after), 1)
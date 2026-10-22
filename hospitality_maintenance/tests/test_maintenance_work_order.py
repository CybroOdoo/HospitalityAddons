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

from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHospitalityWorkOrder(TransactionCase):
    """MAINT-02: work order state machine + OOO auto-block."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'MAINT-02 Test Property',
            'code': 'MT02',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'MAINT-02 Test Room Type',
            'code': 'MT02STD',
            'property_id': cls.property.id,
        })
        cls.space = cls.env['hospitality.space'].create({
            'name': 'MAINT-02 Test Room 101',
            'code': 'MT101',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'MAINT-02 Test Spare Part',
        })

    def _create_order(self, **extra):
        vals = {
            'property_id': self.property.id,
            'space_id': self.space.id,
            'category': 'plumbing',
            'source': 'staff',
            'description': 'Leaking tap in bathroom',
        }
        vals.update(extra)
        return self.env['hospitality.work.order'].create(vals)

    def test_state_machine_transitions(self):
        """Happy path draft -> open -> in_progress -> done, plus a
        hold/resume detour and an invalid-transition guard."""
        order = self._create_order()
        self.assertEqual(order.state, 'draft')

        order.action_open()
        self.assertEqual(order.state, 'open')

        order.action_start()
        self.assertEqual(order.state, 'in_progress')

        order.action_hold(reason='Waiting on plumber availability')
        self.assertEqual(order.state, 'on_hold')

        order.action_resume()
        self.assertEqual(order.state, 'in_progress')

        order.action_await_part(reason='Ordering replacement valve')
        self.assertEqual(order.state, 'awaiting_part')

        order.action_resume()
        self.assertEqual(order.state, 'in_progress')

        order.action_done()
        self.assertEqual(order.state, 'done')

        # Invalid: cannot re-open a done order.
        with self.assertRaises(UserError):
            order.action_open()

        # Invalid: cannot cancel a done order.
        with self.assertRaises(UserError):
            order.action_cancel()

    def test_set_ooo_blocks_space_on_start(self):
        """Starting a work order with set_ooo=True must auto-block the
        linked space out of inventory."""
        ooo_from = Date.today() + timedelta(days=1)
        ooo_to = ooo_from + timedelta(days=2)
        order = self._create_order(
            set_ooo=True, ooo_from=ooo_from, ooo_to=ooo_to)
        order.action_open()

        order.action_start()

        self.assertEqual(order.state, 'in_progress')
        self.assertEqual(self.space.status, 'ooo')
        self.assertEqual(self.space.ooo_reason, order.description)
        self.assertEqual(self.space.ooo_from, ooo_from)
        self.assertEqual(self.space.ooo_to, ooo_to)

    def test_set_ooo_requires_dates_on_start(self):
        """Starting a set_ooo work order without OOO From/To must raise,
        since hospitality.space itself requires both when status='ooo'."""
        order = self._create_order(set_ooo=True)
        order.action_open()
        with self.assertRaises(UserError):
            order.action_start()

    def test_release_ooo_on_done(self):
        """Completing a work order that had auto-blocked its space must
        release the space back to vacant_dirty."""
        ooo_from = Date.today() + timedelta(days=1)
        ooo_to = ooo_from + timedelta(days=2)
        order = self._create_order(
            set_ooo=True, ooo_from=ooo_from, ooo_to=ooo_to)
        order.action_open()

        order.action_start()
        self.assertEqual(self.space.status, 'ooo')

        order.action_done()
        self.assertEqual(order.state, 'done')
        self.assertEqual(self.space.status, 'vacant_dirty')

    def test_cost_total_computed_from_parts(self):
        """cost_total must equal the sum of qty * cost across all lines
        in parts_used_ids, and stay in sync as lines are added/removed."""
        order = self._create_order()
        self.assertEqual(order.cost_total, 0.0)

        self.env['hospitality.work.order.part'].create({
            'work_order_id': order.id,
            'product_id': self.product.id,
            'qty': 2,
            'cost': 15.5,
        })
        self.env['hospitality.work.order.part'].create({
            'work_order_id': order.id,
            'product_id': self.product.id,
            'qty': 1,
            'cost': 40.0,
        })
        self.assertEqual(order.cost_total, 2 * 15.5 + 1 * 40.0)

        order.parts_used_ids[0].unlink()
        self.assertEqual(order.cost_total, 40.0)
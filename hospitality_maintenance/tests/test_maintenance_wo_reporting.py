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

from lxml import etree

from odoo.fields import Datetime
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestHospitalityWorkOrderReporting(TransactionCase):
    """MAINT-04: WO Aging pivot + form view state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'MAINT-04 Test Property',
            'code': 'MT04',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'MAINT-04 Test Room Type',
            'code': 'MT04STD',
            'property_id': cls.property.id,
        })
        cls.space = cls.env['hospitality.space'].create({
            'name': 'MAINT-04 Test Room 201',
            'code': 'MT201',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

    def _create_order(self, **extra):
        vals = {
            'property_id': self.property.id,
            'space_id': self.space.id,
            'category': 'plumbing',
            'source': 'staff',
            'description': 'MAINT-04 test work order',
        }
        vals.update(extra)
        return self.env['hospitality.work.order'].create(vals)

    def test_aging_buckets_classify_correctly(self):
        """age_bucket must classify reported_at into the right day-range
        bucket, and go blank once the order reaches a terminal state."""
        now = Datetime.now()
        cases = [
            (now - timedelta(hours=2), '1_lt_1d'),
            (now - timedelta(days=2), '2_1_3d'),
            (now - timedelta(days=5), '3_3_7d'),
            (now - timedelta(days=10), '4_7_14d'),
            (now - timedelta(days=20), '5_gt_14d'),
        ]
        for reported_at, expected_bucket in cases:
            order = self._create_order(reported_at=reported_at)
            self.assertEqual(
                order.age_bucket, expected_bucket,
                "reported_at=%s should classify as %s" % (
                    reported_at, expected_bucket))

        # A boundary case just past a threshold still lands correctly.
        boundary_order = self._create_order(
            reported_at=now - timedelta(days=1, seconds=1))
        self.assertEqual(boundary_order.age_bucket, '2_1_3d')

        # Terminal states are excluded from aging entirely.
        closed_order = self._create_order(
            reported_at=now - timedelta(days=30))
        closed_order.action_open()
        closed_order.action_start()
        closed_order.action_done()
        self.assertFalse(closed_order.age_bucket)

        cancelled_order = self._create_order(
            reported_at=now - timedelta(days=30))
        cancelled_order.action_cancel()
        self.assertFalse(cancelled_order.age_bucket)

    def test_wo_form_buttons_visible_per_state(self):
        """Each header button's `invisible` modifier must show it only
        for the state(s) that button is meant to act from, matching
        hospitality.work.order's own _ALLOWED_FROM transition table.

        This checks the view's logic directly (evaluating each button's
        invisible expression against every possible state) rather than
        driving a real browser, since the underlying state-machine
        contract is what actually needs regression protection here."""
        view = self.env['hospitality.work.order'].get_view(
            self.env.ref(
                'hospitality_maintenance.view_hospitality_work_order_form'
            ).id,
            'form',
        )
        arch = etree.fromstring(view['arch'])
        buttons = {
            button.get('name'): button.get('invisible', 'False')
            for button in arch.xpath('//header/button[@name]')
        }

        all_states = [
            'draft', 'open', 'in_progress', 'on_hold', 'awaiting_part',
            'done', 'cancelled',
        ]
        # Mirrors hospitality.work.order's own _ALLOWED_FROM, plus
        # action_cancel which is allowed from every non-terminal state.
        expected_visible_states = {
            'action_open': {'draft'},
            'action_start': {'open'},
            'action_hold': {'in_progress'},
            'action_await_part': {'in_progress'},
            'action_resume': {'on_hold', 'awaiting_part'},
            'action_done': {'in_progress'},
            'action_cancel': {
                'draft', 'open', 'in_progress', 'on_hold', 'awaiting_part',
            },
        }

        self.assertEqual(set(buttons), set(expected_visible_states),
                          "Header button set changed — update this test's "
                          "expectations alongside the form view.")

        for button_name, invisible_expr in buttons.items():
            expected_states = expected_visible_states[button_name]
            for state in all_states:
                is_invisible = bool(
                    safe_eval(invisible_expr, {'state': state}))
                should_be_visible = state in expected_states
                self.assertEqual(
                    not is_invisible, should_be_visible,
                    "Button '%s' (invisible=%r) is %s for state=%s, "
                    "expected %s." % (
                        button_name, invisible_expr,
                        'hidden' if is_invisible else 'visible',
                        state,
                        'visible' if should_be_visible else 'hidden'))
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

from datetime import datetime, timedelta
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'hospitality')
class TestBase05Policies(TransactionCase):
    """BASE-05 — Cancellation & deposit policies + activity trace."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def _seq(name):
            return cls.env['ir.sequence'].create({
                'name': name,
                'code': name.lower().replace(' ', '_'),
                'prefix': name[:3].upper() + '/%(year)s/',
                'padding': 5,
            })

        cls.prop = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TEST01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': cls.env.company.currency_id.id,
            'sequence_reservation_id': _seq('Res Test').id,
            'sequence_folio_id': _seq('Folio Test').id,
        })

        # Cancellation policy with two rules: free >24h, 100% ≤24h
        cls.cancel_policy = cls.env[
            'hospitality.cancellation.policy'].create({
            'name': 'Test Flex',
            'code': 'TFLEX',
        })
        cls.env['hospitality.cancellation.policy.rule'].create([
            {
                'policy_id': cls.cancel_policy.id,
                'sequence': 10,
                'hours_before_arrival': 24,
                'days_before_arrival': 0,
                'charge_type': 'percent',
                'charge_value': 0,
            },
            {
                'policy_id': cls.cancel_policy.id,
                'sequence': 20,
                'hours_before_arrival': 1,
                'days_before_arrival': 0,
                'charge_type': 'percent',
                'charge_value': 100,
            },
        ])

        # Deposit policy: 50% of total at booking
        cls.deposit_policy = cls.env['hospitality.deposit.policy'].create({
            'name': 'Test 50%',
            'code': 'T50',
            'due_at': 'booking',
            'amount_type': 'percent_total',
            'amount_value': 50,
        })

    # ------------------------------------------------------------------
    # Test 1 — Cancellation free outside window
    # ------------------------------------------------------------------
    def test_01_cancellation_free_outside_window(self):
        """No charge when cancelled more than 24h before arrival."""
        arrival = datetime(2026, 9, 1, 14, 0)
        cancel = datetime(2026, 8, 30, 10, 0)   # ~52h before
        charge = self.cancel_policy.rule_ids.compute_charge(
            500.0, arrival, cancel
        )
        self.assertEqual(charge, 0.0,
                         "Should be 0 when cancelled >24h before arrival.")

    # ------------------------------------------------------------------
    # Test 2 — Cancellation 100% within window
    # ------------------------------------------------------------------
    def test_02_cancellation_full_charge_within_window(self):
        """100% charge when cancelled within 24h of arrival."""
        arrival = datetime(2026, 9, 1, 14, 0)
        cancel = datetime(2026, 9, 1, 10, 0)    # 4h before
        charge = self.cancel_policy.rule_ids.compute_charge(
            500.0, arrival, cancel
        )
        self.assertEqual(charge, 500.0,
                         "Should be 100% of total within 24h window.")

    # ------------------------------------------------------------------
    # Test 3 — Cancellation rule constraint: both hours and days > 0
    # ------------------------------------------------------------------
    def test_03_rule_constraint_both_nonzero(self):
        """Both hours_before_arrival and days_before_arrival > 0 raises."""
        with self.assertRaises(ValidationError):
            self.env['hospitality.cancellation.policy.rule'].create({
                'policy_id': self.cancel_policy.id,
                'hours_before_arrival': 12,
                'days_before_arrival': 2,
                'charge_type': 'percent',
                'charge_value': 50,
            })

    # ------------------------------------------------------------------
    # Test 4 — Deposit compute_deposit (percent)
    # ------------------------------------------------------------------
    def test_04_deposit_percent(self):
        """50% deposit policy returns half the total amount."""
        deposit = self.deposit_policy.compute_deposit(
            total_amount=800.0, first_night_amount=200.0
        )
        self.assertAlmostEqual(deposit, 400.0,
                               msg="50% of 800 should be 400.")

    # ------------------------------------------------------------------
    # Test 5 — Deposit compute_deposit (first_night)
    # ------------------------------------------------------------------
    def test_05_deposit_first_night(self):
        """First-night deposit policy returns the first night amount."""
        fn_policy = self.env['hospitality.deposit.policy'].create({
            'name': 'Test FN',
            'code': 'TFN',
            'due_at': 'booking',
            'amount_type': 'first_night',
            'amount_value': 0,
        })
        deposit = fn_policy.compute_deposit(
            total_amount=800.0, first_night_amount=200.0
        )
        self.assertAlmostEqual(deposit, 200.0,
                               msg="First night deposit should be 200.")

    # ------------------------------------------------------------------
    # Test 6 — Activity trace lifecycle: create → resolve
    # ------------------------------------------------------------------
    def test_06_activity_trace_resolve(self):
        """Trace starts unresolved; action_resolve marks it resolved."""
        trace = self.env['hospitality.activity.trace'].create({
            'type': 'arrival',
            'text': 'VIP guest arriving — prepare welcome amenities.',
            'property_id': self.prop.id,
        })
        self.assertFalse(trace.resolved, "New trace should be unresolved.")
        self.assertFalse(trace.resolved_by,
                         "resolved_by should be empty before resolve.")

        trace.action_resolve()

        self.assertTrue(trace.resolved, "Trace should be resolved after action.")
        self.assertEqual(trace.resolved_by, self.env.user,
                         "resolved_by should be the current user.")
        self.assertTrue(trace.resolved_at,
                        "resolved_at should be set after resolve.")
        # Name should include the type label
        self.assertIn('Arrival', trace.name,
                      "Computed name should include type label.")
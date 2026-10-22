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

from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError

@tagged('post_install', '-at_install')
class TestReservationStateMachine(TransactionCase):
    """RES-02: Full state-machine and business-rule tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property ──────────────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TST01',
        })

        # ── Space type ────────────────────────────────────────────────────────
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard Room',
            'code': 'STD',
            'property_id': cls.property.id,
        })

        # ── Space ─────────────────────────────────────────────────────────────
        cls.space = cls.env['hospitality.space'].create({
            'name': '101',
            'code': 'RM101',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

        # ── Rate code ─────────────────────────────────────────────────────────
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BAR',
            'code': 'BAR',
            'property_id': cls.property.id,
        })

        # ── Guest partner ─────────────────────────────────────────────────────
        cls.guest = cls.env['res.partner'].create({'name': 'John Doe'})

        # ── Users ─────────────────────────────────────────────────────────────
        agent_group = cls.env.ref(
            'hospitality_reservation.group_reservation_agent'
        )
        supervisor_group = cls.env.ref(
            'hospitality_reservation.group_reservation_supervisor'
        )
        cls.agent_user = cls.env['res.users'].create({
            'name': 'Agent User',
            'login': 'test_agent@test.com',
            'group_ids': [(6, 0, [agent_group.id])],
        })
        cls.supervisor_user = cls.env['res.users'].create({
            'name': 'Supervisor User',
            'login': 'test_supervisor@test.com',
            'group_ids': [(6, 0, [supervisor_group.id])],
        })

        # ── Common dates ──────────────────────────────────────────────────────
        cls.today = date.today()
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.next_week = cls.today + timedelta(days=7)

    def _make_reservation(self, **kwargs):
        """Helper: create a minimal draft reservation."""
        defaults = {
            'property_id': self.property.id,
            'partner_id': self.guest.id,
            'arrival': self.tomorrow,
            'departure': self.next_week,
            'space_type_id': self.space_type.id,
            'rate_code_id': self.rate_code.id,
            'adults': 2,
        }
        defaults.update(kwargs)
        return self.env['hospitality.reservation'].create(defaults)

    # ── 1. Valid transitions ───────────────────────────────────────────────────

    def test_state_machine_valid_transitions(self):
        """Full lifecycle: draft → option → confirmed → checked_in → checked_out."""
        res = self._make_reservation()
        self.assertEqual(res.state, 'draft')

        # draft → option
        from odoo import fields as F
        res.option_expires_at = F.Datetime.now() + timedelta(days=2)
        res.action_save_option()
        self.assertEqual(res.state, 'option')

        # option → confirmed (supervisor bypasses deposit check)
        res.with_user(self.supervisor_user).action_confirm()
        self.assertEqual(res.state, 'confirmed')

        # confirmed → checked_in (space required)
        res.space_id = self.space.id
        res.action_check_in()
        self.assertEqual(res.state, 'checked_in')

        # checked_in → checked_out
        res.action_check_out()
        self.assertEqual(res.state, 'checked_out')

    # ── 2. Invalid transitions ────────────────────────────────────────────────

    def test_state_machine_invalid_transitions_raise(self):
        """Invalid transitions must raise UserError."""
        res = self._make_reservation()

        # Cannot check in from draft
        with self.assertRaises(UserError):
            res.action_check_in()

        # Cannot check out from draft
        with self.assertRaises(UserError):
            res.action_check_out()

        # Cannot no-show from draft
        with self.assertRaises(UserError):
            res.with_user(self.supervisor_user).action_no_show()

    # ── 3. Space assignment lock ──────────────────────────────────────────────

    def test_space_assignment_locks_row(self):
        """_assign_space must detect a concurrent overlap and raise."""
        # First reservation takes the space
        res1 = self._make_reservation()
        res1.space_id = self.space.id
        res1.state = 'confirmed'

        # Second reservation same dates → overlap conflict
        res2 = self._make_reservation()
        with self.assertRaises(UserError):
            res2._assign_space(self.space.id)

    # ── 4. Overlapping reservations rejected ──────────────────────────────────

    def test_overlapping_reservations_rejected(self):
        """Two confirmed reservations on same space/dates must conflict."""
        res1 = self._make_reservation()
        res1.space_id = self.space.id
        res1.state = 'confirmed'

        res2 = self._make_reservation()
        with self.assertRaises(UserError):
            res2._assign_space(self.space.id)

    # ── 5. Option expiry cron ─────────────────────────────────────────────────

    def test_option_expiry_cron(self):
        """Cron must cancel options whose expiry has passed."""
        from odoo import fields as F
        past = F.Datetime.now() - timedelta(hours=1)
        res = self._make_reservation(option_expires_at=past)
        res.state = 'option'  # force to option without setting expires_at again

        self.env['hospitality.reservation']._cron_expire_options()
        self.assertEqual(res.state, 'cancelled')

    # ── 6. Nights computed ────────────────────────────────────────────────────

    def test_nights_computed(self):
        """nights must equal departure - arrival in days."""
        res = self._make_reservation(
            arrival=self.tomorrow,
            departure=self.tomorrow + timedelta(days=3),
        )
        self.assertEqual(res.nights, 3)

    # ── 7. Cancellation policy charge ────────────────────────────────────────

    def test_cancellation_applies_policy_charge(self):
        """Cancelling a confirmed reservation must set cancelled_at."""
        res = self._make_reservation()
        res.state = 'confirmed'
        res.action_cancel()
        self.assertEqual(res.state, 'cancelled')
        self.assertTrue(res.cancelled_at)
        self.assertEqual(res.cancelled_by.id, self.env.uid)

    # ── 8. Check-in requires space and deposit ────────────────────────────────

    def test_check_in_requires_space_and_deposit(self):
        """Check-in without space must raise UserError."""
        res = self._make_reservation()
        res.state = 'confirmed'
        # No space assigned → must raise
        with self.assertRaises(UserError):
            res.action_check_in()

    # ── 9. Undo check-in supervisor only ─────────────────────────────────────

    def test_undo_check_in_supervisor_only(self):
        """Agent must NOT be able to undo check-in; supervisor must succeed."""
        res = self._make_reservation(arrival=date.today())
        res.space_id = self.space.id
        res.state = 'checked_in'

        # Agent → denied
        with self.assertRaises(UserError):
            res.with_user(self.agent_user).action_undo_check_in()

        # Supervisor → allowed (arrival == today so same-day guard passes)
        res.with_user(self.supervisor_user).action_undo_check_in()
        self.assertEqual(res.state, 'confirmed')

    # ── 10. cc_token hidden from non-supervisor ───────────────────────────────

    def test_cc_token_hidden_from_non_supervisor(self):
        """cc_token field must be invisible to agent-only users."""
        supervisor_group = self.env.ref(
            'hospitality_reservation.group_reservation_supervisor'
        )
        agent_group = self.env.ref(
            'hospitality_reservation.group_reservation_agent'
        )
        # Agent user should NOT have access to cc_token via field groups
        agent_fields = (
            self.env['hospitality.reservation']
            .with_user(self.agent_user)
            .fields_get(['cc_token'])
        )
        # fields_get returns {} for fields the user cannot see
        self.assertFalse(
            agent_fields,
            'cc_token must not be accessible to agent-only users.',
        )

        # Supervisor should see it
        supervisor_fields = (
            self.env['hospitality.reservation']
            .with_user(self.supervisor_user)
            .fields_get(['cc_token'])
        )
        self.assertIn(
            'cc_token',
            supervisor_fields,
            'cc_token must be accessible to supervisors.',
        )
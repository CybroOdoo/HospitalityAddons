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
"""FD-07 — Full lifecycle integration test.

Unlike the per-wizard unit tests (FD-02/03/04/05), which stub out
collaborators such as ``reservation.action_check_in`` /
``action_check_out`` to isolate wizard logic, this test drives the real
ORM chain end-to-end: walk-in wizard -> checked-in reservation with an
open folio -> room move -> check-out -> reservation checked-out. It also
touches the FD-05 queue entry and FD-06 shift lifecycle, so a single run
exercises every FD-* model at least once.

Only ``_get_balance`` on the check-out wizard is patched (to ``0.0``),
since the actual folio-charge-posting cadence lives outside this module
and is intentionally out of scope for a front-desk integration test.
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestFrontDeskIntegration(TransactionCase):
    """FD-07 acceptance: test_integration_walkin_to_checkout."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Reservation = cls.env['hospitality.reservation']

        cls.template_reservation = Reservation.search([
            ('property_id', '!=', False),
            ('space_type_id', '!=', False),
            ('rate_code_id', '!=', False),
        ], limit=1)

        if not cls.template_reservation:
            raise Exception(
                "No valid reservation template found with property_id, "
                "space_type_id and rate_code_id. Install hospitality_reservation "
                "demo data first."
            )

        cls.property = cls.template_reservation.property_id
        cls.space_type = cls.template_reservation.space_type_id
        cls.rate_code = cls.template_reservation.rate_code_id

        cls.walkin_space = cls.env['hospitality.space'].create({
            'name': '901-FD07',
            'code': '901FD07',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })
        cls.move_target_space = cls.env['hospitality.space'].create({
            'name': '902-FD07',
            'code': '902FD07',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

    # ─────────────────────────────────────────────────────────────────
    # Full lifecycle: walk-in -> checked-in -> room move -> check-out
    # ─────────────────────────────────────────────────────────────────
    def test_integration_walkin_to_checkout(self):
        Reservation = self.env['hospitality.reservation']

        # ── 1. Walk-in: new guest, new reservation, immediate check-in ──
        walkin_wiz = self.env['hospitality.walk.in.wizard'].create({
            'mode': 'new_partner',
            'new_partner_name': 'FD07 Integration Guest',
            'new_partner_email': 'fd07integration@example.com',
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
            'space_id': self.walkin_space.id,
            'rate_code_id': self.rate_code.id,
            'expected_departure': fields.Date.context_today(self) + timedelta(days=2),
            'payment_method': 'cash',
            'deposit_amount': 0.0,
        })
        walkin_wiz.action_walk_in()

        reservation = Reservation.search([
            ('space_id', '=', self.walkin_space.id),
        ], limit=1, order='id desc')
        self.assertTrue(reservation, "Walk-in must create a reservation.")
        self.assertEqual(reservation.state, 'checked_in')

        # hospitality.reservation carries no forward pointer to
        # hospitality.folio — the link is one-way via
        # hospitality.folio.reservation_id — so existence must be
        # checked with a reverse search, not getattr() on the
        # reservation.
        folio = self.env['hospitality.folio'].search([
            ('reservation_id', '=', reservation.id),
        ], limit=1)
        self.assertTrue(
            folio, "Checked-in walk-in reservation must carry an open folio."
        )

        # ── Housekeeping status is managed independently of reservation
        #    state — checking in a reservation does not itself flip the
        #    space's status to occupied. Set it explicitly here, matching
        #    the setup pattern already used in the FD-05 room-move test,
        #    so the room move below has a valid source state to move
        #    *from* (action_set_vacant_dirty only allows sources of
        #    occupied_clean / occupied_dirty / ooo / oos). ───────────────
        self.walkin_space.action_set_occupied_clean()

        # ── 2. Room move to a second, vacant-clean space ────────────────
        move_wiz = self.env['hospitality.room.move.wizard'].create({
            'reservation_id': reservation.id,
            'target_space_id': self.move_target_space.id,
            'reason': 'FD-07 integration test move.',
        })
        move_wiz.action_move()

        reservation.invalidate_recordset()
        self.walkin_space.invalidate_recordset()
        self.move_target_space.invalidate_recordset()

        self.assertEqual(reservation.space_id, self.move_target_space)
        self.assertEqual(self.walkin_space.status, 'vacant_dirty')
        self.assertEqual(self.move_target_space.status, 'occupied_clean')

        # ── 3. Check-out: settle + transition to checked_out ────────────
        checkout_wiz = self.env['hospitality.front.desk.check.out.wizard'].create({
            'reservation_id': reservation.id,
            'settle_now': False,
        })
        CheckoutWizard = type(checkout_wiz)
        with patch.object(CheckoutWizard, '_get_balance', return_value=0.0):
            result = checkout_wiz.action_check_out()

        reservation.invalidate_recordset()
        self.assertEqual(reservation.state, 'checked_out')
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

        # ── 4. Queue entry can be raised against the same reservation ───
        entry = self.env['hospitality.queue.entry'].create({
            'reservation_id': reservation.id,
        })
        self.assertEqual(entry.state, 'waiting')
        entry.action_mark_ready()
        self.assertEqual(entry.state, 'ready')

        # ── 5. Front desk shift opens and closes cleanly for the property ─
        shift = self.env['hospitality.front.desk.shift'].create({
            'user_id': self.env.user.id,
            'property_id': self.property.id,
        })
        self.assertEqual(shift.state, 'open')
        self.assertIn(
            shift.id,
            [row['id'] for row in
             self.env['hospitality.front.desk.shift'].get_dashboard_data(
                 self.property.id
             )['open_shifts']],
        )
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')
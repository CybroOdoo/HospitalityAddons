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
from odoo.tests.common import TransactionCase


class TestFrontDeskRoomMoveWizard(TransactionCase):
    """FD-05 acceptance tests for the room move wizard and queue entry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Reservation = cls.env['hospitality.reservation']

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Guest FD05', 'email': 'fd05guest@example.com'
        })

        cls.template_reservation = Reservation.search([
            ('property_id', '!=', False),
            ('space_type_id', '!=', False),
            ('rate_code_id', '!=', False),
        ], limit=1)
        if not cls.template_reservation:
            raise Exception(
                'No valid reservation template found with property_id, '
                'space_type_id and rate_code_id. Install hospitality_reservation '
                'demo data first.'
            )

        cls.property = cls.template_reservation.property_id
        cls.space_type = cls.template_reservation.space_type_id
        cls.rate_code = cls.template_reservation.rate_code_id

        # ── Spaces: current (occupied) and target (vacant clean) ────────
        cls.current_space = cls.env['hospitality.space'].create({
            'name': '301-FD05', 'code': '301FD05',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })
        cls.target_space = cls.env['hospitality.space'].create({
            'name': '302-FD05', 'code': '302FD05',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

        # Put the current space into occupied_clean (as if guest checked in)
        cls.current_space.action_set_occupied_clean()

        cls.reservation = cls.template_reservation.copy({
            'partner_id': cls.partner.id,
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'rate_code_id': cls.rate_code.id,
            'space_id': cls.current_space.id,
            'state': 'draft',
        })
        cls.env.cr.execute(
            "UPDATE hospitality_reservation SET state = 'checked_in' WHERE id = %s",
            (cls.reservation.id,)
        )
        cls.reservation.invalidate_recordset()

    def _make_wizard(self, **kwargs):
        vals = {
            'reservation_id': self.reservation.id,
            'target_space_id': self.target_space.id,
            'reason': 'Guest requested a quieter room.',
        }
        vals.update(kwargs)
        return self.env['hospitality.room.move.wizard'].create(vals)

    # ─────────────────────────────────────────────────────────────────
    # 1. Room move persists the new space on the reservation
    # ─────────────────────────────────────────────────────────────────
    def test_room_move_persists_new_space(self):
        wiz = self._make_wizard()
        wiz.action_move()
        self.reservation.invalidate_recordset()
        self.assertEqual(self.reservation.space_id, self.target_space)

    # ─────────────────────────────────────────────────────────────────
    # 2. Room move updates housekeeping status on both spaces
    # ─────────────────────────────────────────────────────────────────
    def test_room_move_updates_status_on_both_spaces(self):
        wiz = self._make_wizard()
        wiz.action_move()
        self.current_space.invalidate_recordset()
        self.target_space.invalidate_recordset()
        self.assertEqual(self.current_space.status, 'vacant_dirty')
        self.assertEqual(self.target_space.status, 'occupied_clean')

    # ─────────────────────────────────────────────────────────────────
    # 3. Queue entry lifecycle: waiting -> ready -> served / cancelled
    # ─────────────────────────────────────────────────────────────────
    def test_queue_entry_lifecycle(self):
        entry = self.env['hospitality.queue.entry'].create({
            'reservation_id': self.reservation.id,
        })
        self.assertEqual(entry.state, 'waiting')
        self.assertFalse(entry.ready_at)

        entry.action_mark_ready()
        self.assertEqual(entry.state, 'ready')
        self.assertTrue(entry.ready_at)
        self.assertEqual(entry.called_by, self.env.user)

        entry.action_mark_served()
        self.assertEqual(entry.state, 'served')

        # A cancelled/served entry cannot be force-readied again.
        entry.action_mark_ready()
        self.assertEqual(entry.state, 'served')

        other_entry = self.env['hospitality.queue.entry'].create({
            'reservation_id': self.reservation.id,
        })
        other_entry.action_cancel()
        self.assertEqual(other_entry.state, 'cancelled')
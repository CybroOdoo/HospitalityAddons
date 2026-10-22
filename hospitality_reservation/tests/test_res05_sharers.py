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

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSharersAndCron(TransactionCase):
    """RES-05 — Sharers, multi-room group_id_stub, and option-expiry cron."""

    # ── Fixtures ──────────────────────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'RES-05 Test Hotel',
            'code': 'R05H',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard',
            'code': 'STD',
            'property_id': cls.property.id,
        })
        cls.space_type_b = cls.env['hospitality.space.type'].create({
            'name': 'Suite',
            'code': 'STE',
            'property_id': cls.property.id,
        })
        cls.space = cls.env['hospitality.space'].create({
            'name': '101',
            'code': 'RM101',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space_b = cls.env['hospitality.space'].create({
            'name': '201',
            'code': 'RM201',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BAR', 'code': 'BAR',
            'property_id': cls.property.id,
        })
        cls.guest_a = cls.env['res.partner'].create({'name': 'Guest Alpha'})
        cls.guest_b = cls.env['res.partner'].create({'name': 'Guest Beta'})
        cls.today = date.today()

    def _make_res(self, arrival_offset=1, departure_offset=3,
                  space=None, partner=None, state='confirmed'):
        """Helper: create a confirmed reservation."""
        res = self.env['hospitality.reservation'].create({
            'property_id': self.property.id,
            'partner_id': (partner or self.guest_a).id,
            'arrival': self.today + timedelta(days=arrival_offset),
            'departure': self.today + timedelta(days=departure_offset),
            'space_type_id': self.space_type.id,
            'space_id': (space or self.space).id,
            'rate_code_id': self.rate_code.id,
            'adults': 1,
        })
        if state == 'confirmed':
            res.action_confirm()
        return res

    # ── test_share_create_new_inherits_dates_and_space ────────────────────────

    def test_share_create_new_inherits_dates_and_space(self):
        """Wizard create_new copies arrival/departure and space from source."""
        source = self._make_res()

        wizard = self.env['hospitality.reservation.share.wizard'].create({
            'source_reservation_id': source.id,
            'mode': 'create_new',
            'partner_id': self.guest_b.id,
        })
        wizard.action_apply()

        # Source should now have one sharer
        self.assertEqual(len(source.share_with_ids), 1,
                         'Source should have 1 sharer after create_new.')

        sharer = source.share_with_ids
        self.assertEqual(sharer.arrival, source.arrival,
                         'Sharer arrival must match source.')
        self.assertEqual(sharer.departure, source.departure,
                         'Sharer departure must match source.')
        self.assertEqual(sharer.space_id, source.space_id,
                         'Sharer space must match source.')
        self.assertEqual(sharer.partner_id, self.guest_b,
                         'Sharer partner must be the one chosen in the wizard.')

        # Both ends must be linked
        self.assertIn(source, sharer.share_with_ids,
                      'Sharer must back-link to source.')

    # ── test_share_attach_existing_links_both_ends ────────────────────────────

    def test_share_attach_existing_links_both_ends(self):
        """Wizard attach_existing links both share_with_ids ends correctly."""
        source = self._make_res(arrival_offset=1, departure_offset=4)
        target = self._make_res(arrival_offset=2, departure_offset=5,
                                partner=self.guest_b)

        wizard = self.env['hospitality.reservation.share.wizard'].create({
            'source_reservation_id': source.id,
            'mode': 'attach_existing',
            'target_reservation_id': target.id,
        })
        wizard.action_apply()

        self.assertIn(target, source.share_with_ids,
                      'Target must appear in source.share_with_ids.')
        self.assertIn(source, target.share_with_ids,
                      'Source must appear in target.share_with_ids (back-link).')

    # ── test_share_rejects_mismatched_space ───────────────────────────────────

    def test_share_rejects_mismatched_space(self):
        """Attaching a sharer with a different space must raise UserError."""
        source = self._make_res(space=self.space)
        target = self._make_res(space=self.space_b, partner=self.guest_b)

        wizard = self.env['hospitality.reservation.share.wizard'].create({
            'source_reservation_id': source.id,
            'mode': 'attach_existing',
            'target_reservation_id': target.id,
        })
        with self.assertRaises(UserError,
                               msg='Mismatched space must raise UserError.'):
            wizard.action_apply()

    # ── test_multi_room_uses_group_id_stub ────────────────────────────────────

    def test_multi_room_uses_group_id_stub(self):
        """action_add_another_room creates a sister with the same group_id_stub."""
        source = self._make_res()
        self.assertFalse(source.group_id_stub,
                         'group_id_stub should be empty before the action.')

        source.action_add_another_room()

        self.assertTrue(source.group_id_stub,
                        'group_id_stub must be set after action_add_another_room.')

        # Search for sister rooms sharing the same group_id_stub
        sisters = self.env['hospitality.reservation'].search([
            ('group_id_stub', '=', source.group_id_stub),
            ('id', '!=', source.id),
        ])
        self.assertEqual(len(sisters), 1,
                         'Source must have exactly 1 sister reservation.')

        sister = sisters
        self.assertEqual(sister.group_id_stub, source.group_id_stub,
                         'Sister must share the same group_id_stub.')

        # Calling again must reuse the same stub (not generate a new one)
        old_stub = source.group_id_stub
        source.action_add_another_room()
        self.assertEqual(source.group_id_stub, old_stub,
                         'group_id_stub must not change on repeated calls.')

    # ── test_cron_expires_options ─────────────────────────────────────────────

    def test_cron_expires_options(self):
        """_cron_expire_options cancels all option reservations past expiry."""
        from odoo import fields as ofields
        import datetime

        # Create one expired option and one still-valid option
        expired_res = self.env['hospitality.reservation'].create({
            'property_id': self.property.id,
            'partner_id': self.guest_a.id,
            'arrival': self.today + timedelta(days=5),
            'departure': self.today + timedelta(days=7),
            'space_type_id': self.space_type.id,
            'space_id': self.space.id,
            'rate_code_id': self.rate_code.id,
            'adults': 1,
            'option_expires_at': ofields.Datetime.now() - datetime.timedelta(hours=1),
        })
        expired_res.action_save_option()

        valid_res = self.env['hospitality.reservation'].create({
            'property_id': self.property.id,
            'partner_id': self.guest_b.id,
            'arrival': self.today + timedelta(days=5),
            'departure': self.today + timedelta(days=7),
            'space_type_id': self.space_type_b.id,
            'rate_code_id': self.rate_code.id,
            'adults': 1,
            'option_expires_at': ofields.Datetime.now() + datetime.timedelta(hours=24),
        })
        valid_res.action_save_option()

        self.assertEqual(expired_res.state, 'option')
        self.assertEqual(valid_res.state, 'option')

        # Run the cron
        self.env['hospitality.reservation']._cron_expire_options()

        self.assertEqual(expired_res.state, 'cancelled',
                         'Expired option must be cancelled by cron.')
        self.assertEqual(valid_res.state, 'option',
                         'Non-expired option must remain in option state.')
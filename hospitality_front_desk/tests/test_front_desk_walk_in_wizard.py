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


class TestFrontDeskWalkInWizard(TransactionCase):
    """FD-04 acceptance tests for the walk-in wizard."""

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

        cls.existing_partner = cls.env['res.partner'].create({
            'name': 'FD04 Existing Guest',
            'email': 'fd04existing@example.com',
        })

    def _make_space(self, suffix):
        return self.env['hospitality.space'].create({
            'name': '%s-FD04' % suffix,
            'code': '%sFD04' % suffix,
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
            'status': 'vacant_clean',
        })

    def _wizard_vals(self, space, **kwargs):
        vals = {
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
            'space_id': space.id,
            'rate_code_id': self.rate_code.id,
            'expected_departure': fields_date_add(self.env, days=1),
            'payment_method': 'cash',
            'deposit_amount': 0.0,
        }
        vals.update(kwargs)
        return vals

    # ─────────────────────────────────────────────────────────────────
    # 1. New partner mode creates a partner
    # ─────────────────────────────────────────────────────────────────
    def test_walkin_new_partner_creates_partner(self):
        space = self._make_space('301')
        Partner = self.env['res.partner']
        before_count = Partner.search_count([
            ('name', '=', 'FD04 Walk-In Guest'),
        ])

        wiz = self.env['hospitality.walk.in.wizard'].create(
            self._wizard_vals(
                space,
                mode='new_partner',
                new_partner_name='FD04 Walk-In Guest',
                new_partner_email='fd04walkin@example.com',
            )
        )
        wiz.action_walk_in()

        after_count = Partner.search_count([
            ('name', '=', 'FD04 Walk-In Guest'),
        ])
        self.assertEqual(after_count, before_count + 1)

    # ─────────────────────────────────────────────────────────────────
    # 2. Existing partner mode reuses the partner, does not duplicate
    # ─────────────────────────────────────────────────────────────────
    def test_walkin_existing_partner_reuses(self):
        space = self._make_space('302')
        Partner = self.env['res.partner']
        before_count = Partner.search_count([
            ('id', '=', self.existing_partner.id),
        ])

        wiz = self.env['hospitality.walk.in.wizard'].create(
            self._wizard_vals(
                space,
                mode='existing_partner',
                partner_id=self.existing_partner.id,
            )
        )
        wiz.action_walk_in()

        after_count = Partner.search_count([
            ('id', '=', self.existing_partner.id),
        ])
        self.assertEqual(after_count, before_count)

        Reservation = self.env['hospitality.reservation']
        reservation = Reservation.search([
            ('partner_id', '=', self.existing_partner.id),
            ('space_id', '=', space.id),
        ], limit=1, order='id desc')
        self.assertTrue(reservation)
        self.assertEqual(reservation.partner_id, self.existing_partner)

    # ─────────────────────────────────────────────────────────────────
    # 3. Full flow results in a checked-in reservation
    # ─────────────────────────────────────────────────────────────────
    def test_walkin_full_flow_results_in_checked_in_state(self):
        space = self._make_space('303')

        wiz = self.env['hospitality.walk.in.wizard'].create(
            self._wizard_vals(
                space,
                mode='new_partner',
                new_partner_name='FD04 Full Flow Guest',
            )
        )
        wiz.action_walk_in()

        Reservation = self.env['hospitality.reservation']
        reservation = Reservation.search([
            ('space_id', '=', space.id),
        ], limit=1, order='id desc')

        self.assertTrue(reservation)
        self.assertEqual(reservation.state, 'checked_in')

        if 'is_walkin' in Reservation._fields:
            self.assertTrue(reservation.is_walkin)

        # hospitality.reservation carries no forward pointer to
        # hospitality.folio — the link is one-way via
        # hospitality.folio.reservation_id — so existence must be
        # checked with a reverse search, not getattr() on the
        # reservation.
        folio = self.env['hospitality.folio'].search([
            ('reservation_id', '=', reservation.id),
        ], limit=1)
        self.assertTrue(folio, "Checked-in walk-in reservation must have an open folio.")


def fields_date_add(env, days=1):
    """Return today's date + days, as a date object, without importing
    odoo.fields at module load time (kept local for test isolation)."""
    from datetime import timedelta
    from odoo import fields as odoo_fields
    return odoo_fields.Date.context_today(env.user) + timedelta(days=days)
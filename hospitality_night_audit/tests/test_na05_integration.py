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
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNightAuditIntegration(TransactionCase):
    """NA-05: full end-to-end audit against a real property with 3
    checked-in reservations.

    hospitality.rate.code._get_rate() is patched rather than exercised
    for real. Building a working hospitality.rate.plan (weekday_mask,
    date_from/date_to, _price_for_night pricing) is hospitality_rate's
    own concern and its exact fields weren't available while writing
    this test; patching keeps this test scoped to night-audit
    orchestration — which is what NA-05 is actually meant to prove —
    instead of silently depending on hospitality_rate's internal
    schema staying exactly as guessed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # _step_advance_business_date requires the Hospitality Admin
        # group to write property_id.business_date directly (mirrors
        # the same grant already used in test_na04_wizard.py).
        admin_group = cls.env.ref(
            'hospitality_base.group_hospitality_admin', raise_if_not_found=False,
        )
        if admin_group:
            cls.env.user.write({'group_ids': [(4, admin_group.id)]})

        cls.today = fields.Date.today()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'NA-05 Integration Property',
            'code': 'NA05IT',
        })
        cls.property.business_date = cls.today

        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'NA-05 Standard King',
            'code': 'NA05STDK',
            'property_id': cls.property.id,
            'category': 'room',
            'default_occupancy': 2,
            'max_occupancy': 2,
        })

        cls.room_txn_code = cls.env['hospitality.transaction.code'].search(
            [('code', '=', 'ROOM')], limit=1
        )
        if not cls.room_txn_code:
            cls.room_txn_code = cls.env['hospitality.transaction.code'].create({
                'code': 'ROOM',
                'name': 'Room Charge',
                'transaction_type': 'charge',
            })

        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'NA-05 Best Available Rate',
            'code': 'NA05BAR',
            'property_id': cls.property.id,
        })
        cls.rate_code.action_activate()

        cls.reservations = cls.env['hospitality.reservation']
        cls.folios = cls.env['hospitality.folio']
        for i in range(1, 4):
            space = cls.env['hospitality.space'].create({
                'name': 'NA-05 Room 10%d' % i,
                'code': 'NA05R10%d' % i,
                'space_type_id': cls.space_type.id,
                'property_id': cls.property.id,
            })
            partner = cls.env['res.partner'].create({
                'name': 'NA-05 Guest %d' % i,
            })
            reservation = cls.env['hospitality.reservation'].create({
                'property_id': cls.property.id,
                'partner_id': partner.id,
                'arrival': cls.today,
                'departure': fields.Date.add(cls.today, days=2),
                'adults': 2,
                'space_type_id': cls.space_type.id,
                'space_id': space.id,
                'rate_code_id': cls.rate_code.id,
                'guarantee_type': 'none',
            })
            reservation.action_confirm()
            reservation.action_check_in()
            space.write({'status': 'occupied_clean'})

            # hospitality.reservation.action_check_in() attempts to open
            # a folio via `self.env['hospitality.folio'].open(rec)`, but
            # no such classmethod exists on hospitality.folio (only the
            # instance method action_open_folio()) — the call is wrapped
            # in a bare try/except so it fails silently. Opening the
            # folio explicitly here reproduces what check-in is meant to
            # do, so this test exercises the real posting path instead
            # of masking that gap.
            folio = cls.env['hospitality.folio'].create({
                'reservation_id': reservation.id,
                'property_id': cls.property.id,
                'partner_id': partner.id,
                'currency_id': cls.property.currency_id.id,
            })
            folio.action_open_folio()

            cls.reservations |= reservation
            cls.folios |= folio

    def test_integration_full_audit_on_demo_property(self):
        Run = self.env['hospitality.night.audit.run']
        RateCode = self.env.registry['hospitality.rate.code']

        business_date = self.property.business_date
        nightly_price = 150.0

        def _fake_get_rate(rate, property_id, space_type_id, rate_code_id,
                            arrival, departure, occupancy):
            return {
                'nightly': [(arrival, nightly_price)],
                'inclusions': [],
                'restrictions': [],
                'currency_id': self.property.currency_id.id,
            }

        with patch.object(RateCode, '_get_rate', autospec=True,
                           side_effect=_fake_get_rate):
            run = Run.run_audit(self.property.id, business_date)

        self.assertIn(
            run.state, ('posted', 'closed'),
            'Audit did not complete cleanly: %s' % (run.log_text or ''),
        )
        for step in run.step_ids:
            self.assertNotEqual(
                step.status, 'failed',
                '%s failed: %s' % (step.name, step.message),
            )

        # business_date advanced by exactly one day
        self.assertEqual(
            self.property.business_date, business_date + timedelta(days=1)
        )

        # a ROOM charge line was posted to every one of the 3 folios
        room_lines = self.env['hospitality.folio.line'].search([
            ('folio_id', 'in', self.folios.ids),
            ('transaction_code_id', '=', self.room_txn_code.id),
            ('business_date', '=', business_date),
            ('is_void', '=', False),
        ])
        self.assertEqual(len(room_lines), 3)
        self.assertEqual(run.rooms_posted, 3)
        for line in room_lines:
            self.assertEqual(line.unit_price, nightly_price)
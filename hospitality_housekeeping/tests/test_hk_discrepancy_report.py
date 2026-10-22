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
    RESERVATION_MODEL, RESERVATION_CHECKED_IN_STATE)


@tagged('post_install', '-at_install')
class TestHkDiscrepancyReport(TransactionCase):
    """HK-05: HK Discrepancy report.

    Reservation fixtures use the confirmed hospitality_reservation
    schema (see the fixture note in test_hk_crons.py for the full
    required-field list and the space_type_id match constraint)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Discrepancy = cls.env['hospitality.hk.discrepancy']
        cls.Reservation = cls.env[RESERVATION_MODEL]

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Discrepancy Test Property',
                'code': 'HKDISC',
            })

        cls.partner = cls.env['res.partner'].create({
            'name': 'HK Discrepancy Test Guest',
        })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Discrepancy Test Type',
            })

        cls.rate_code = cls.env['hospitality.rate.code'].search(
            [('property_id', '=', cls.property.id)], limit=1)
        if not cls.rate_code:
            cls.rate_code = cls.env['hospitality.rate.code'].create({
                'name': 'HK Discrepancy Test Rate',
                'code': 'HKDISCRATE',
                'property_id': cls.property.id,
            })

        # Mismatch: PMS has a checked-in reservation, but the space
        # is still marked vacant_clean on the HK side.
        cls.space_mismatch = cls.env['hospitality.space'].create({
            'name': 'HK Discrepancy Mismatch Space',
            'code': 'HKDISCM',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })
        cls.Reservation.create({
            'property_id': cls.property.id,
            'partner_id': cls.partner.id,
            'space_type_id': cls.space_type.id,
            'space_id': cls.space_mismatch.id,
            'rate_code_id': cls.rate_code.id,
            'arrival': Date.today(),
            'departure': Date.today() + timedelta(days=1),
            'state': RESERVATION_CHECKED_IN_STATE,
        })

        # No mismatch: PMS has no reservation, and the space is
        # correctly marked vacant.
        cls.space_ok = cls.env['hospitality.space'].create({
            'name': 'HK Discrepancy OK Space',
            'code': 'HKDISCOK',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

    def test_hk_discrepancy_report_finds_mismatch(self):
        """The mismatched space shows up as an 'occupied' PMS state
        against a 'vacant' housekeeping status; the correctly-vacant
        space doesn't appear at all."""
        records = self.Discrepancy._compute_discrepancies(
            self.property.id)

        space_ids = records.mapped('space_id.id')
        self.assertIn(self.space_mismatch.id, space_ids)
        self.assertNotIn(self.space_ok.id, space_ids)

        mismatch_row = records.filtered(
            lambda r: r.space_id == self.space_mismatch)
        self.assertEqual(mismatch_row.pms_state, 'occupied')
        self.assertTrue(mismatch_row.note)
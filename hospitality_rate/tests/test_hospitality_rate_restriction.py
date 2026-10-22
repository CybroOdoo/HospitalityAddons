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
"""
RATE-04 — Tests for hospitality.rate.restriction

Tests:
  1. test_closed_short_circuits
  2. test_cta_blocks_arrival
  3. test_ctd_blocks_departure
  4. test_min_stay
  5. test_max_stay
  6. test_no_restriction_returns_empty
"""

from datetime import date

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestHospitalityRateRestriction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property ─────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TH004',
        })

        # ── Space Type (property_id is NOT NULL) ─────────────────────
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard Room',
            'code': 'STD4',
            'property_id': cls.property.id,
        })

        # ── Rate Code ────────────────────────────────────────────────
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'Rack Rate',
            'code': 'RACK4',
            'property_id': cls.property.id,
            'type': 'public',
        })

        # ── Restriction model alias ─────────────────────────────────
        cls.Restriction = cls.env['hospitality.rate.restriction']

    # ══════════════════════════════════════════════════════════════════════
    # TEST 1: Closed short-circuits
    # ══════════════════════════════════════════════════════════════════════

    def test_closed_short_circuits(self):
        """When a restriction is closed, _evaluate returns ['closed']
        immediately without checking other flags."""
        self.Restriction.create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 7, 1),
            'date_to': date(2026, 7, 31),
            'closed': True,
            'cta': True,
            'ctd': True,
            'min_stay': 5,
            'max_stay': 10,
        })

        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 7, 10),
            departure=date(2026, 7, 12),
        )

        # Only 'closed', nothing else despite cta/ctd/min/max being set
        self.assertEqual(violations, ['closed'])

    # ══════════════════════════════════════════════════════════════════════
    # TEST 2: CTA blocks arrival
    # ══════════════════════════════════════════════════════════════════════

    def test_cta_blocks_arrival(self):
        """When CTA is set, arriving within the restriction range
        produces a 'cta' violation."""
        self.Restriction.create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 8, 1),
            'date_to': date(2026, 8, 15),
            'cta': True,
        })

        # Arrival on Aug 5 (within range) -> cta violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 8, 5),
            departure=date(2026, 8, 10),
        )
        self.assertIn('cta', violations)

        # Arrival on Aug 20 (outside range, no overlap) -> no violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 8, 20),
            departure=date(2026, 8, 25),
        )
        self.assertNotIn('cta', violations)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 3: CTD blocks departure
    # ══════════════════════════════════════════════════════════════════════

    def test_ctd_blocks_departure(self):
        """When CTD is set, departing within the restriction range
        produces a 'ctd' violation."""
        self.Restriction.create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 9, 1),
            'date_to': date(2026, 9, 15),
            'ctd': True,
        })

        # Departure on Sep 10 (within range) -> ctd violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 9, 5),
            departure=date(2026, 9, 10),
        )
        self.assertIn('ctd', violations)

        # Departure on Sep 20 (outside range) -> no ctd
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 9, 5),
            departure=date(2026, 9, 20),
        )
        self.assertNotIn('ctd', violations)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 4: Minimum stay
    # ══════════════════════════════════════════════════════════════════════

    def test_min_stay(self):
        """When min_stay is set, a stay shorter than min_stay
        produces a 'min_stay' violation."""
        self.Restriction.create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 10, 1),
            'date_to': date(2026, 10, 31),
            'min_stay': 3,
        })

        # 2-night stay -> min_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 10, 10),
            departure=date(2026, 10, 12),
        )
        self.assertIn('min_stay', violations)

        # 3-night stay -> no min_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 10, 10),
            departure=date(2026, 10, 13),
        )
        self.assertNotIn('min_stay', violations)

        # 5-night stay -> no min_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 10, 10),
            departure=date(2026, 10, 15),
        )
        self.assertNotIn('min_stay', violations)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 5: Maximum stay
    # ══════════════════════════════════════════════════════════════════════

    def test_max_stay(self):
        """When max_stay is set (>0), a stay longer than max_stay
        produces a 'max_stay' violation."""
        self.Restriction.create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 11, 1),
            'date_to': date(2026, 11, 30),
            'max_stay': 5,
        })

        # 7-night stay -> max_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 11, 10),
            departure=date(2026, 11, 17),
        )
        self.assertIn('max_stay', violations)

        # 5-night stay -> no max_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 11, 10),
            departure=date(2026, 11, 15),
        )
        self.assertNotIn('max_stay', violations)

        # 3-night stay -> no max_stay violation
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 11, 10),
            departure=date(2026, 11, 13),
        )
        self.assertNotIn('max_stay', violations)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 6: No restriction returns empty list
    # ══════════════════════════════════════════════════════════════════════

    def test_no_restriction_returns_empty(self):
        """When no restrictions exist for the given parameters,
        _evaluate returns an empty list."""
        violations = self.Restriction._evaluate(
            rate_code_id=self.rate_code.id,
            space_type_id=self.space_type.id,
            arrival=date(2026, 12, 10),
            departure=date(2026, 12, 15),
        )
        self.assertEqual(violations, [])
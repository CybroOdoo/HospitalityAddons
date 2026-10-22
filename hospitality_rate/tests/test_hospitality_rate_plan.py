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
RATE-03 — Tests for hospitality.rate.plan

Tests:
  1. test_overlap_rejected
  2. test_price_flat
  3. test_price_per_pax_with_extras
  4. test_price_occupancy_grid
  5. test_weekday_mask_excludes_saturday
  6. test_grid_required_when_mode_is_grid
"""

from datetime import date

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestHospitalityRatePlan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property (required by space.type and rate.code) ──────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TH002',
        })

        # ── Space Types (property_id is NOT NULL) ────────────────────
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Standard Room',
            'code': 'STD',
            'property_id': cls.property.id,
        })

        cls.space_type_2 = cls.env['hospitality.space.type'].create({
            'name': 'Deluxe Room',
            'code': 'DLX',
            'property_id': cls.property.id,
        })

        # ── Rate Code ────────────────────────────────────────────────
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'Best Available Rate',
            'code': 'BAR',
            'property_id': cls.property.id,
            'type': 'public',
        })

    # ══════════════════════════════════════════════════════════════════════
    # TEST 1: Overlapping date ranges are rejected
    # ══════════════════════════════════════════════════════════════════════

    def test_overlap_rejected(self):
        """Two plans for the same (rate_code_id, space_type_id) cannot
        have overlapping date ranges."""
        self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'occupancy_pricing': 'flat',
            'price_double': 100.0,
        })

        # Overlapping range -> rejected
        with self.assertRaises(ValidationError):
            self.env['hospitality.rate.plan'].create({
                'rate_code_id': self.rate_code.id,
                'space_type_id': self.space_type.id,
                'date_from': date(2026, 1, 15),
                'date_to': date(2026, 2, 15),
                'occupancy_pricing': 'flat',
                'price_double': 120.0,
            })

        # Non-overlapping range -> allowed
        self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 2, 1),
            'date_to': date(2026, 2, 28),
            'occupancy_pricing': 'flat',
            'price_double': 130.0,
        })

        # Same dates but different space_type_id -> allowed
        self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type_2.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 1, 31),
            'occupancy_pricing': 'flat',
            'price_double': 150.0,
        })

    # ══════════════════════════════════════════════════════════════════════
    # TEST 2: Flat pricing
    # ══════════════════════════════════════════════════════════════════════

    def test_price_flat(self):
        """occupancy_pricing='flat' always returns price_double."""
        plan = self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
            'occupancy_pricing': 'flat',
            'price_single': 80.0,
            'price_double': 100.0,
        })

        # 2026-03-02 is a Monday (weekday bit 0, included in default mask 127)
        result = plan._price_for_night(date(2026, 3, 2), adults=1, children=0)
        self.assertEqual(result, 100.0)

        result = plan._price_for_night(date(2026, 3, 2), adults=2, children=1)
        self.assertEqual(result, 100.0)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 3: Per-pax pricing with extras
    # ══════════════════════════════════════════════════════════════════════

    def test_price_per_pax_with_extras(self):
        """occupancy_pricing='per_pax':
        - adults == 1 -> price_single
        - adults != 1 -> price_double + extras
        - extras = max(0, adults-2) * price_extra_adult
                   + children * price_extra_child
        """
        plan = self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'occupancy_pricing': 'per_pax',
            'price_single': 80.0,
            'price_double': 100.0,
            'price_extra_adult': 20.0,
            'price_extra_child': 10.0,
        })

        # 2026-04-06 is a Monday
        single_price = plan._price_for_night(
            date(2026, 4, 6), adults=1, children=0)
        self.assertEqual(single_price, 80.0)

        double_price = plan._price_for_night(
            date(2026, 4, 6), adults=2, children=0)
        self.assertEqual(double_price, 100.0)

        # 3 adults, 1 child:
        # base = price_double (100) since adults != 1
        # extras = max(0, 3-2) * 20 + 1 * 10 = 20 + 10 = 30
        # total = 130
        extra_price = plan._price_for_night(
            date(2026, 4, 6), adults=3, children=1)
        self.assertEqual(extra_price, 130.0)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 4: Occupancy grid pricing
    # ══════════════════════════════════════════════════════════════════════

    def test_price_occupancy_grid(self):
        """occupancy_pricing='occupancy_grid': returns the price from the
        matching occupancy_grid_ids row, and raises if no row matches."""
        plan = self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'occupancy_pricing': 'occupancy_grid',
            'occupancy_grid_ids': [
                (0, 0, {'adults': 1, 'children': 0, 'price': 90.0}),
                (0, 0, {'adults': 2, 'children': 0, 'price': 110.0}),
                (0, 0, {'adults': 2, 'children': 1, 'price': 130.0}),
            ],
        })

        # 2026-05-04 is a Monday
        result = plan._price_for_night(date(2026, 5, 4), adults=2, children=1)
        self.assertEqual(result, 130.0)

        result = plan._price_for_night(date(2026, 5, 4), adults=1, children=0)
        self.assertEqual(result, 90.0)

        # No matching row for 3 adults, 2 children -> raises
        with self.assertRaises(ValidationError):
            plan._price_for_night(date(2026, 5, 4), adults=3, children=2)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 5: Weekday mask excludes Saturday
    # ══════════════════════════════════════════════════════════════════════

    def test_weekday_mask_excludes_saturday(self):
        """When the Saturday bit (bit 5) is cleared in weekday_mask,
        _price_for_night returns None for a Saturday date."""
        # 127 (1111111) with bit 5 (Saturday) cleared = 95 (1011111)
        mask_without_saturday = 127 & ~(1 << 5)

        plan = self.env['hospitality.rate.plan'].create({
            'rate_code_id': self.rate_code.id,
            'space_type_id': self.space_type.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'occupancy_pricing': 'flat',
            'price_double': 100.0,
            'weekday_mask': mask_without_saturday,
        })

        # 2026-06-06 is a Saturday -> not active
        saturday = date(2026, 6, 6)
        self.assertEqual(saturday.weekday(), 5)
        result = plan._price_for_night(saturday, adults=2, children=0)
        self.assertIsNone(result)

        # 2026-06-05 is a Friday -> active
        friday = date(2026, 6, 5)
        self.assertEqual(friday.weekday(), 4)
        result = plan._price_for_night(friday, adults=2, children=0)
        self.assertEqual(result, 100.0)

    # ══════════════════════════════════════════════════════════════════════
    # TEST 6: Occupancy grid required when mode is 'occupancy_grid'
    # ══════════════════════════════════════════════════════════════════════

    def test_grid_required_when_mode_is_grid(self):
        """occupancy_pricing='occupancy_grid' with no occupancy_grid_ids
        rows raises a ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['hospitality.rate.plan'].create({
                'rate_code_id': self.rate_code.id,
                'space_type_id': self.space_type.id,
                'date_from': date(2026, 7, 1),
                'date_to': date(2026, 7, 31),
                'occupancy_pricing': 'occupancy_grid',
            })
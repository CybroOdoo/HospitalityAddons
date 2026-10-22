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
RATE-06 — Canonical pricing API tests.

Tests:
  test_flat_pricing_7_nights
  test_per_pax_with_2_extras
  test_occupancy_grid_lookup
  test_derived_percent_minus_10
  test_derived_fixed_off
  test_derived_fixed_on
  test_weekday_mask_excludes_day
  test_package_expansion_per_pax_per_night
  test_restrictions_returned_but_pricing_still_computed
  test_perf_p95_under_50ms
"""

import statistics
import time
from datetime import date, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestHospitalityRateAPI(TransactionCase):
    """End-to-end tests for HospitalityRateCode._get_rate (RATE-06)."""

    # ─────────────────────────────────────────────────────────────────────
    # CLASS-LEVEL SETUP — shared fixtures
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property ──────────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'TH01',
        })

        # ── Space Type ────────────────────────────────────────────────────
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Deluxe Room',
            'code': 'DLX',
            'property_id': cls.property.id,
        })

        # ── Transaction Code (for package inclusions) ─────────────────────
        cls.txn_code = cls.env['hospitality.transaction.code'].create({
            'name': 'Breakfast',
            'code': 'BRK',
            'category': 'fnb',
            'sign': 'debit',
        })

        # ── Base (master) rate code ───────────────────────────────────────
        cls.base_rate = cls.env['hospitality.rate.code'].create({
            'name': 'BAR',
            'code': 'BAR',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'none',
            'state': 'active',
        })

        # ── Flat rate plan — all 7 weekdays, rate_double = 100 ───────────
        cls.plan_flat = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.base_rate.id,
            'space_type_id': cls.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'occupancy_pricing': 'flat',
            'price_double': 100.0,
            'weekday_mask': 127,  # all days
        })

        # ── Per-pax rate plan — single=80, double=100,
        #    extra_adult=30, extra_child=15 ─────────────────────────────
        cls.rate_perpax = cls.env['hospitality.rate.code'].create({
            'name': 'PERPAX',
            'code': 'PERPAX',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'none',
            'state': 'active',
        })
        cls.plan_perpax = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_perpax.id,
            'space_type_id': cls.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'occupancy_pricing': 'per_pax',
            'price_single': 80.0,
            'price_double': 100.0,
            'price_extra_adult': 30.0,
            'price_extra_child': 15.0,
            'weekday_mask': 127,
        })

        # ── Occupancy-grid rate plan ───────────────────────────────────────
        cls.rate_grid = cls.env['hospitality.rate.code'].create({
            'name': 'GRID',
            'code': 'GRID',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'none',
            'state': 'active',
        })
        cls.plan_grid = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_grid.id,
            'space_type_id': cls.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'occupancy_pricing': 'occupancy_grid',
            'weekday_mask': 127,
            'occupancy_grid_ids': [
                (0, 0, {'adults': 2, 'children': 0, 'price': 120.0}),
                (0, 0, {'adults': 2, 'children': 1, 'price': 140.0}),
            ],
        })

        # ── Derived rate codes ────────────────────────────────────────────
        cls.rate_pct = cls.env['hospitality.rate.code'].create({
            'name': 'PCT-10',
            'code': 'PCT10',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'percent',
            'derive_value': -10.0,
            'base_rate_code_id': cls.base_rate.id,
            'state': 'active',
        })
        cls.rate_fixed_off = cls.env['hospitality.rate.code'].create({
            'name': 'FOFF',
            'code': 'FOFF',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'fixed_off',
            'derive_value': 20.0,
            'base_rate_code_id': cls.base_rate.id,
            'state': 'active',
        })
        cls.rate_fixed_on = cls.env['hospitality.rate.code'].create({
            'name': 'FON',
            'code': 'FON',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'fixed_on',
            'derive_value': 15.0,
            'base_rate_code_id': cls.base_rate.id,
            'state': 'active',
        })

        # ── Weekday-mask rate: only Mon–Fri (bits 0-4 = 0b0011111 = 31) ──
        cls.rate_weekday = cls.env['hospitality.rate.code'].create({
            'name': 'WKDAY',
            'code': 'WKDAY',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'none',
            'state': 'active',
        })
        cls.plan_weekday = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_weekday.id,
            'space_type_id': cls.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'occupancy_pricing': 'flat',
            'price_double': 90.0,
            'weekday_mask': 0b0011111,  # Mon=0 … Fri=4
        })

        # ── Package rate with per_pax_per_night inclusion ──────────────────
        cls.package = cls.env['hospitality.package'].create({
            'name': 'BB Package',
            'code': 'BB',
            'property_id': cls.property.id,
            'inclusion_ids': [
                (0, 0, {
                    'transaction_code_id': cls.txn_code.id,
                    'qty': 1.0,
                    'value': 12.0,
                    'posting_rhythm': 'per_pax_per_night',
                }),
            ],
        })
        cls.rate_pkg = cls.env['hospitality.rate.code'].create({
            'name': 'BBRATE',
            'code': 'BBRATE',
            'property_id': cls.property.id,
            'type': 'package',
            'derive_method': 'none',
            'package_id': cls.package.id,
            'state': 'active',
        })
        cls.plan_pkg = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_pkg.id,
            'space_type_id': cls.space_type.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 12, 31),
            'occupancy_pricing': 'flat',
            'price_double': 100.0,
            'weekday_mask': 127,
        })

        # ── Restriction: min-stay 3 nights over a specific window ─────────
        cls.restriction = cls.env['hospitality.rate.restriction'].create({
            'rate_code_id': cls.base_rate.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'min_stay': 3,
        })

        # ── Common dates ──────────────────────────────────────────────────
        # Mon 2026-03-02 → Mon 2026-03-09 (7 nights, all weekdays)
        cls.arr7 = date(2026, 3, 2)
        cls.dep7 = date(2026, 3, 9)
        cls.occ2 = {'adults': 2, 'children': 0}

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────

    def _call(self, rate, arrival, departure, occ=None):
        """Convenience wrapper around _get_rate."""
        if occ is None:
            occ = self.occ2
        return rate._get_rate(
            self.property.id,
            self.space_type.id,
            rate.id,
            arrival,
            departure,
            occ,
        )

    # ─────────────────────────────────────────────────────────────────────
    # TESTS
    # ─────────────────────────────────────────────────────────────────────

    def test_flat_pricing_7_nights(self):
        """7 nights flat rate → 7 tuples each with amount 100.0."""
        result = self._call(self.base_rate, self.arr7, self.dep7)

        self.assertEqual(len(result['nightly']), 7)
        for night_date, amount in result['nightly']:
            self.assertEqual(
                amount, 100.0,
                f"Expected 100.0 on {night_date}, got {amount}",
            )
        self.assertEqual(result['restrictions'], [])
        self.assertEqual(result['inclusions'], [])

    def test_per_pax_with_2_extras(self):
        """2 adults + 2 children: double(100) + 0 extra_adult + 2*15 child = 130."""
        occ = {'adults': 2, 'children': 2}
        result = self._call(self.rate_perpax, self.arr7, self.dep7, occ=occ)

        # double=100, extra_adult=0 (no adults beyond 2), child=2*15=30
        expected = 100.0 + 2 * 15.0
        for night_date, amount in result['nightly']:
            self.assertAlmostEqual(
                amount, expected, places=2,
                msg=f"Per-pax price wrong on {night_date}",
            )

    def test_occupancy_grid_lookup(self):
        """Occupancy grid: 2 adults, 1 child → 140."""
        occ = {'adults': 2, 'children': 1}
        result = self._call(self.rate_grid, self.arr7, self.dep7, occ=occ)

        for night_date, amount in result['nightly']:
            self.assertAlmostEqual(
                amount, 140.0, places=2,
                msg=f"Grid price wrong on {night_date}",
            )

    def test_derived_percent_minus_10(self):
        """Derived rate at -10% of base 100 → 90 per night."""
        result = self._call(self.rate_pct, self.arr7, self.dep7)

        for night_date, amount in result['nightly']:
            self.assertAlmostEqual(
                amount, 90.0, places=2,
                msg=f"Percent-derived price wrong on {night_date}",
            )

    def test_derived_fixed_off(self):
        """Derived rate fixed_off 20 from base 100 → 80 per night."""
        result = self._call(self.rate_fixed_off, self.arr7, self.dep7)

        for night_date, amount in result['nightly']:
            self.assertAlmostEqual(
                amount, 80.0, places=2,
                msg=f"Fixed-off price wrong on {night_date}",
            )

    def test_derived_fixed_on(self):
        """Derived rate fixed_on 15 from base 100 → 115 per night."""
        result = self._call(self.rate_fixed_on, self.arr7, self.dep7)

        for night_date, amount in result['nightly']:
            self.assertAlmostEqual(
                amount, 115.0, places=2,
                msg=f"Fixed-on price wrong on {night_date}",
            )

    def test_weekday_mask_excludes_day(self):
        """Plan with Mon-Fri mask: Saturday and Sunday nights → None."""
        # 2026-03-06 is Friday, 2026-03-07 is Saturday, 2026-03-08 is Sunday
        arr = date(2026, 3, 6)   # Fri
        dep = date(2026, 3, 9)   # Mon (exclusive)
        result = self._call(self.rate_weekday, arr, dep)

        # Fri=4 (bit 4) is in mask 0b0011111, Sat=5 and Sun=6 are not
        prices = {d: amt for d, amt in result['nightly']}
        self.assertAlmostEqual(prices[date(2026, 3, 6)], 90.0, places=2,
                               msg="Friday should be priced")
        self.assertIsNone(prices[date(2026, 3, 7)],
                          "Saturday should return None (masked out)")
        self.assertIsNone(prices[date(2026, 3, 8)],
                          "Sunday should return None (masked out)")

    def test_package_expansion_per_pax_per_night(self):
        """Package per_pax_per_night with 2 adults → 2 rows per night × 3 nights."""
        arr = date(2026, 4, 1)
        dep = date(2026, 4, 4)   # 3 nights
        occ = {'adults': 2, 'children': 0}
        result = self._call(self.rate_pkg, arr, dep, occ=occ)

        self.assertEqual(len(result['nightly']), 3)
        # 3 nights × 2 pax = 6 inclusion rows
        self.assertEqual(len(result['inclusions']), 6)
        for row in result['inclusions']:
            self.assertEqual(row['transaction_code_id'], self.txn_code.id)
            self.assertAlmostEqual(row['value'], 12.0, places=2)
            self.assertNotEqual(row['when'], 'on_arrival')

    def test_restrictions_returned_but_pricing_still_computed(self):
        """
        Restrictions are returned in the result but pricing is still
        computed — a single-night stay during the min_stay=3 window.
        """
        # min_stay=3 restriction is on base_rate for June 2026
        arr = date(2026, 6, 10)
        dep = date(2026, 6, 11)  # 1 night < min_stay=3
        result = self._call(self.base_rate, arr, dep)

        self.assertIn('min_stay', result['restrictions'],
                      "min_stay violation should be reported")
        # pricing still computed (not blocked)
        self.assertEqual(len(result['nightly']), 1)
        _, amount = result['nightly'][0]
        self.assertIsNotNone(amount, "Price must still be returned despite restriction")

    def test_perf_p95_under_50ms(self):
        """
        p95 of 20 consecutive 7-night calls must be < 50 ms.

        After the first call (cold ORM cache) we run 20 timed iterations
        and compute the 95th percentile.
        """
        arr = date(2026, 3, 2)
        dep = date(2026, 3, 9)

        # Warm up
        self._call(self.base_rate, arr, dep)

        samples = []
        for _ in range(20):
            t0 = time.perf_counter()
            self._call(self.base_rate, arr, dep)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            samples.append(elapsed_ms)

        p95 = statistics.quantiles(samples, n=100)[94]  # index 94 = 95th pct
        self.assertLess(
            p95, 50.0,
            f"p95 latency {p95:.1f} ms exceeds 50 ms target. "
            f"Samples: {[f'{s:.1f}' for s in samples]}",
        )
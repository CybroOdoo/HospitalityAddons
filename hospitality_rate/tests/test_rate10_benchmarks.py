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
RATE-10 — Demo data + tests + pricing API benchmarks.

Tests:
  test_perf_get_rate_p95_under_50ms_7_nights
      p95 of 30 consecutive _get_rate calls for a 7-night stay must be < 50 ms.

  test_perf_calendar_query_p95_under_100ms_90_days
      p95 of 20 consecutive hospitality.rate.plan ORM searches covering a
      90-day window (all space types) must be < 100 ms.

  test_integration_derived_rate_resolves_via_get_rate
      A CORP-ACME rate (−10 % of BAR) must return prices exactly 10 % below
      the corresponding BAR per-pax prices when called through _get_rate.
"""

import statistics
import time
from datetime import date, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestRate10Benchmarks(TransactionCase):
    """RATE-10 perf benchmarks and derived-rate integration test."""

    # ─────────────────────────────────────────────────────────────────────
    # CLASS-LEVEL SETUP
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Property ──────────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].create({
            'name': 'NYC Test Hotel',
            'code': 'NYC01T',
        })

        # ── 5 Space Types (mirrors PROP-07 demo space types) ─────────────
        space_type_defs = [
            ('Standard Room',   'STD'),
            ('Deluxe Room',     'DLX'),
            ('Junior Suite',    'JRS'),
            ('Executive Suite', 'EXS'),
            ('Penthouse',       'PNT'),
        ]
        cls.space_types = []
        for name, code in space_type_defs:
            st = cls.env['hospitality.space.type'].create({
                'name': name,
                'code': code,
                'property_id': cls.property.id,
            })
            cls.space_types.append(st)

        cls.space_type = cls.space_types[0]  # primary type for single-type tests

        # ── BAR — master rate code, per_pax ──────────────────────────────
        cls.rate_bar = cls.env['hospitality.rate.code'].create({
            'name': 'Best Available Rate',
            'code': 'BAR',
            'property_id': cls.property.id,
            'type': 'public',
            'derive_method': 'none',
            'state': 'active',
        })

        # Rate plans: BAR × each space type × today → today + 90 days
        today = date.today()
        end_90 = today + timedelta(days=90)
        bar_prices = [
            (120.0, 150.0, 35.0, 18.0),  # STD
            (160.0, 200.0, 40.0, 20.0),  # DLX
            (220.0, 270.0, 50.0, 25.0),  # JRS
            (300.0, 360.0, 60.0, 30.0),  # EXS
            (500.0, 600.0, 80.0, 40.0),  # PNT
        ]
        cls.bar_plans = []
        for st, (ps, pd, pea, pec) in zip(cls.space_types, bar_prices):
            plan = cls.env['hospitality.rate.plan'].create({
                'rate_code_id': cls.rate_bar.id,
                'space_type_id': st.id,
                'date_from': today,
                'date_to': end_90,
                'occupancy_pricing': 'per_pax',
                'price_single': ps,
                'price_double': pd,
                'price_extra_adult': pea,
                'price_extra_child': pec,
                'weekday_mask': 127,
            })
            cls.bar_plans.append(plan)

        # ── CORP-ACME — derived corporate rate: BAR − 10 % ───────────────
        cls.rate_corp_acme = cls.env['hospitality.rate.code'].create({
            'name': 'Acme Corporation Rate',
            'code': 'CORP-ACME',
            'property_id': cls.property.id,
            'type': 'corporate',
            'derive_method': 'percent',
            'derive_value': -10.0,
            'base_rate_code_id': cls.rate_bar.id,
            'state': 'active',
        })

        # ── Restrictions on BAR ───────────────────────────────────────────
        # MLOS=2 on Fri (bit 4) + Sat (bit 5) = 0b0110000 = 48
        cls.env['hospitality.rate.restriction'].create({
            'rate_code_id': cls.rate_bar.id,
            'date_from': today,
            'date_to': end_90,
            'min_stay': 2,
            'weekday_mask': 48,
        })

        # Closed on Christmas Eve
        cls.env['hospitality.rate.restriction'].create({
            'rate_code_id': cls.rate_bar.id,
            'date_from': date(2026, 12, 24),
            'date_to': date(2026, 12, 24),
            'closed': True,
        })

        # ── Common test fixtures ──────────────────────────────────────────
        cls.today = today
        cls.end_90 = end_90
        # 7-night window within the 90-day plan range
        cls.arr7 = today + timedelta(days=5)   # Mon-ish, safely inside range
        cls.dep7 = cls.arr7 + timedelta(days=7)
        cls.occ2 = {'adults': 2, 'children': 0}

    # ─────────────────────────────────────────────────────────────────────
    # HELPER
    # ─────────────────────────────────────────────────────────────────────

    def _get_rate(self, rate_code, space_type=None, arrival=None,
                  departure=None, occupancy=None):
        """Thin wrapper around the canonical pricing API."""
        st = space_type or self.space_type
        arr = arrival or self.arr7
        dep = departure or self.dep7
        occ = occupancy or self.occ2
        return rate_code._get_rate(
            self.property.id,
            st.id,
            rate_code.id,
            arr,
            dep,
            occ,
        )

    # ─────────────────────────────────────────────────────────────────────
    # TEST 1 — p95 get_rate latency < 50 ms over 7 nights
    # ─────────────────────────────────────────────────────────────────────

    def test_perf_get_rate_p95_under_50ms_7_nights(self):
        """
        p95 of 30 consecutive _get_rate calls (7-night BAR stay) < 50 ms.

        One warm-up call is made first to populate ORM caches so we measure
        steady-state latency, not cold-start ORM initialisation cost.
        """
        # Warm up
        self._get_rate(self.rate_bar)

        samples = []
        for _ in range(30):
            t0 = time.perf_counter()
            self._get_rate(self.rate_bar)
            samples.append((time.perf_counter() - t0) * 1000)

        p95 = statistics.quantiles(samples, n=100)[94]
        self.assertLess(
            p95, 50.0,
            f"p95 latency {p95:.2f} ms exceeds 50 ms target. "
            f"Samples (ms): {[f'{s:.2f}' for s in samples]}",
        )

    # ─────────────────────────────────────────────────────────────────────
    # TEST 2 — p95 calendar ORM query latency < 100 ms over 90 days
    # ─────────────────────────────────────────────────────────────────────

    def test_perf_calendar_query_p95_under_100ms_90_days(self):
        """
        p95 of 20 consecutive hospitality.rate.plan ORM searches covering the
        full 90-day window (all space types for BAR) must be < 100 ms.

        This mirrors the query issued by the rate-calendar widget (_loadPlans).
        """
        Plan = self.env['hospitality.rate.plan']
        date_from_str = self.today.strftime('%Y-%m-%d')
        date_to_str = self.end_90.strftime('%Y-%m-%d')

        domain = [
            ('rate_code_id', '=', self.rate_bar.id),
            ('date_from', '<=', date_to_str),
            ('date_to', '>=', date_from_str),
        ]
        fields_list = [
            'space_type_id', 'date_from', 'date_to',
            'price_double', 'weekday_mask',
        ]

        # Warm up
        Plan.search_read(domain, fields_list, limit=5000)

        samples = []
        for _ in range(20):
            t0 = time.perf_counter()
            Plan.search_read(domain, fields_list, limit=5000)
            samples.append((time.perf_counter() - t0) * 1000)

        p95 = statistics.quantiles(samples, n=100)[94]
        self.assertLess(
            p95, 100.0,
            f"Calendar query p95 latency {p95:.2f} ms exceeds 100 ms target. "
            f"Samples (ms): {[f'{s:.2f}' for s in samples]}",
        )

    # ─────────────────────────────────────────────────────────────────────
    # TEST 3 — Derived rate CORP-ACME resolves correctly via _get_rate
    # ─────────────────────────────────────────────────────────────────────

    def test_integration_derived_rate_resolves_via_get_rate(self):
        """
        CORP-ACME (percent derive_method, derive_value=-10, base=BAR) must
        return per-night amounts exactly 10 % below the equivalent BAR prices
        when queried through _get_rate for a 7-night, 2-adult stay.

        This validates the full derivation chain:
          _get_rate → _apply_derive → percent adjustment
        """
        occ = {'adults': 2, 'children': 0}

        bar_result = self._get_rate(
            self.rate_bar,
            space_type=self.space_type,
            arrival=self.arr7,
            departure=self.dep7,
            occupancy=occ,
        )
        corp_result = self._get_rate(
            self.rate_corp_acme,
            space_type=self.space_type,
            arrival=self.arr7,
            departure=self.dep7,
            occupancy=occ,
        )

        self.assertEqual(
            len(bar_result['nightly']), 7,
            "BAR should return 7 nightly prices.",
        )
        self.assertEqual(
            len(corp_result['nightly']), 7,
            "CORP-ACME should return 7 nightly prices.",
        )

        for (bar_date, bar_price), (corp_date, corp_price) in zip(
            bar_result['nightly'], corp_result['nightly']
        ):
            self.assertEqual(
                bar_date, corp_date,
                f"Date mismatch: BAR={bar_date}, CORP-ACME={corp_date}",
            )

            if bar_price is None:
                self.assertIsNone(
                    corp_price,
                    f"On {bar_date}: BAR is None so CORP-ACME should also be None.",
                )
            else:
                expected = round(bar_price * 0.90, 10)
                self.assertAlmostEqual(
                    corp_price, expected, places=2,
                    msg=(
                        f"On {bar_date}: CORP-ACME price {corp_price:.4f} "
                        f"is not 90 % of BAR price {bar_price:.4f} "
                        f"(expected {expected:.4f})."
                    ),
                )

        # CORP-ACME is a derived rate with no package → no inclusions
        self.assertEqual(
            corp_result['inclusions'], [],
            "Derived rate should carry no package inclusions.",
        )
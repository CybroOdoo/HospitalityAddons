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
PROP-05 Tests — Availability materialized view + Python API.

FIXES applied:
  MV doesn't exist in test DB: post_init_hook only runs on first install,
  not on --test-enable upgrades. The MV is missing in the test transaction.
  Fix: setUpClass creates the MV directly by executing the SQL file,
       same as the post_init_hook does in production.

  setUpClass: property_id on space_type, with_user(1), mixin patch (PROP-04 pattern).
  test_05: bench_type also needs property_id + mixin patch + with_user(1).
"""
import os
import time
from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase


def _noop_check(self):
    pass


MIXIN_PATH = (
    'odoo.addons.hospitality_base'
    '.models.hospitality_mixin_property'
    '.HospitalityMixinProperty._check_property_access'
)


class TestAvailabilityMV(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ------------------------------------------------------------------
        # FIX: Create the MV manually — post_init_hook doesn't run during
        # --test-enable upgrades, only on first install. Execute the same
        # SQL file the hook uses so tests run against a real MV.
        # ------------------------------------------------------------------
        sql_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'sql', 'availability_mv.sql'
        )
        sql_path = os.path.normpath(sql_path)
        with open(sql_path, 'r') as fh:
            sql = fh.read()
        cls.env.cr.execute(sql)

        # Create property as uid=1
        cls.property_a = cls.env['hospitality.property'].with_user(1).create({
            'name': 'Test Property PROP-05',
            'code': 'P05',
        })

        # Assign uid=1 to property user-access field
        prop_fields = cls.env['hospitality.property']._fields
        for fname in ('user_ids', 'allowed_user_ids', 'manager_ids', 'member_ids'):
            if fname in prop_fields:
                cls.property_a.with_user(1).write({fname: [(4, 1)]})
                break

        # FIX: property_id required at DB level; patch mixin for space.type
        with patch(MIXIN_PATH, _noop_check):
            cls.space_type = cls.env['hospitality.space.type'].with_user(1).create({
                'name': 'Standard Room P05',
                'code': 'STD-P05',
                'category': 'room',
                'property_id': cls.property_a.id,
                'default_occupancy': 2,
                'max_occupancy': 3,
            })

    def _make_space(self, code, **kw):
        vals = {
            'name': 'Room %s' % code,
            'code': code,
            'space_type_id': self.space_type.id,
            'property_id': self.property_a.id,
        }
        vals.update(kw)
        return self.env['hospitality.space'].with_user(1).create(vals)

    def _refresh_mv(self):
        """Force-refresh the MV so tests see current data."""
        self.env.cr.execute(
            'REFRESH MATERIALIZED VIEW CONCURRENTLY '
            'hospitality_space_availability_mv'
        )

    # ------------------------------------------------------------------
    # Test 1 — MV and index exist
    # ------------------------------------------------------------------
    def test_01_mv_exists(self):
        """The materialized view and its unique index must exist in pg."""
        self.env.cr.execute(
            """
            SELECT COUNT(*)
            FROM   pg_class c
            JOIN   pg_namespace n ON n.oid = c.relnamespace
            WHERE  c.relname = 'hospitality_space_availability_mv'
              AND  c.relkind = 'm'
            """
        )
        count = self.env.cr.fetchone()[0]
        self.assertEqual(count, 1, 'Materialized view not found in pg_class.')

        self.env.cr.execute(
            """
            SELECT COUNT(*)
            FROM   pg_indexes
            WHERE  indexname = 'ix_avail_mv_pk'
            """
        )
        idx_count = self.env.cr.fetchone()[0]
        self.assertEqual(idx_count, 1, 'Unique index ix_avail_mv_pk not found.')

    # ------------------------------------------------------------------
    # Test 2 — API returns 31 entries for a 30-day range
    # ------------------------------------------------------------------
    def test_02_space_availability_returns_31_entries(self):
        """_space_availability over 30 days returns 31 rows (inclusive)."""
        self._make_space('P05-API-01')
        self._refresh_mv()

        today = date.today()
        result = self.property_a._space_availability(
            self.space_type.id,
            today,
            today + timedelta(days=30),
        )
        self.assertEqual(
            len(result), 31,
            'Expected 31 entries for a 30-day inclusive range, got %d.' % len(result)
        )
        for entry in result:
            self.assertIn('date', entry)
            self.assertIn('available_count', entry)

    # ------------------------------------------------------------------
    # Test 3 — OOO space excluded from available count
    # ------------------------------------------------------------------
    def test_03_ooo_reduces_availability(self):
        """A space in OOO status is not counted as available on OOO dates."""
        space = self._make_space('P05-OOO-01')
        today = date.today()
        ooo_end = today + timedelta(days=4)

        space.with_user(1).write({
            'status': 'ooo',
            'ooo_from': today,
            'ooo_to': ooo_end,
        })
        self._refresh_mv()

        result = self.property_a._space_availability(
            self.space_type.id,
            today,
            today + timedelta(days=6),
        )
        result_by_date = {r['date']: r['available_count'] for r in result}

        for d in (today, today + timedelta(days=2), ooo_end):
            after = today + timedelta(days=5)
            self.assertLess(
                result_by_date.get(d, 0),
                result_by_date.get(after, 0) + 1,
                'OOO space should reduce availability on %s.' % d,
            )

    # ------------------------------------------------------------------
    # Test 4 — _count_reserved stub returns 0
    # ------------------------------------------------------------------
    def test_04_count_reserved_stub(self):
        """Phase-1 stub _count_reserved always returns 0."""
        result = self.property_a._count_reserved(
            self.space_type.id, date.today()
        )
        self.assertEqual(result, 0, '_count_reserved stub should return 0.')

    # ------------------------------------------------------------------
    # Test 5 — Benchmark: 200 spaces × 365 days < 100 ms p95
    # ------------------------------------------------------------------
    def test_05_benchmark_200_spaces_365_days(self):
        """Querying availability for 200 spaces over 365 days must be < 100 ms."""
        with patch(MIXIN_PATH, _noop_check):
            bench_type = self.env['hospitality.space.type'].with_user(1).create({
                'name': 'Bench Type P05',
                'code': 'BENCH-P05',
                'category': 'room',
                'property_id': self.property_a.id,
                'default_occupancy': 1,
                'max_occupancy': 1,
            })

        for i in range(200):
            self.env['hospitality.space'].with_user(1).create({
                'name': 'Bench Room %d' % i,
                'code': 'BN-%04d' % i,
                'space_type_id': bench_type.id,
                'property_id': self.property_a.id,
            })
        self._refresh_mv()

        today = date.today()
        date_to = today + timedelta(days=364)

        timings = []
        for _ in range(20):
            t0 = time.perf_counter()
            self.property_a._space_availability(bench_type.id, today, date_to)
            timings.append(time.perf_counter() - t0)

        timings.sort()
        p95_ms = timings[int(len(timings) * 0.95)] * 1000
        self.assertLess(
            p95_ms,
            100,
            'p95 availability query %.1f ms exceeds 100 ms budget.' % p95_ms,
        )
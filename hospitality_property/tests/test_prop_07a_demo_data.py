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
PROP-07 Tests (Part A) — Demo data integrity.

Verifies that the hospitality_property_demo.xml records installed correctly:
  1. Building, 4 floors, 2 sections present under NYC01.
  2. All 5 space types created with correct occupancy values.
  3. Exactly 20 spaces created for NYC01.
  4. Status distribution across demo spaces is mixed (≥ 5 distinct statuses).
  5. Room 105 is OOO with correct reason and date window.
  6. Room 205 is OOS with correct reason and date window.

NOTE: These tests ONLY run when the module is installed with --load-demo
(i.e. 'demo' install mode).  If demo data is not loaded the tests are
skipped gracefully.
"""
from datetime import date, timedelta

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestProp07DemoData(TransactionCase):

    def _nyc01(self):
        """Return the NYC01 demo property, or None if not installed."""
        prop = self.env.ref(
            'hospitality_base.demo_property_nyc01', raise_if_not_found=False
        )
        return prop

    def setUp(self):
        super().setUp()
        self.nyc01 = self._nyc01()
        if not self.nyc01:
            self.skipTest('NYC01 demo property not found — demo data not loaded.')

    def test_01_demo_scaffold_created(self):
        """MAIN building, 4 floors and 2 sections must exist under NYC01."""
        buildings = self.env['hospitality.building'].search([
            ('property_id', '=', self.nyc01.id),
            ('code', '=', 'MAIN'),
        ])
        self.assertEqual(len(buildings), 1, 'MAIN building not found under NYC01.')

        main = buildings[0]
        self.assertEqual(len(main.floor_ids), 4,
                         'Expected 4 floors on MAIN building, found %d.' % len(main.floor_ids))
        floor_codes = sorted(main.floor_ids.mapped('code'))
        self.assertEqual(floor_codes, ['F1', 'F2', 'F3', 'F4'])

        self.assertEqual(len(main.section_ids), 2,
                         'Expected 2 sections on MAIN building.')
        section_codes = sorted(main.section_ids.mapped('code'))
        self.assertEqual(section_codes, ['EW', 'PS'])

    def test_02_demo_space_types(self):
        """All 5 demo space types must exist with correct occupancy."""
        expected = {
            'STD-K':    (2, 2),
            'STD-T':    (2, 2),
            'DLX-K':    (2, 3),
            'JR-SUITE': (2, 4),
            'ACC':      (2, 2),
        }
        for code, (default_occ, max_occ) in expected.items():
            stype = self.env['hospitality.space.type'].search([
                ('property_id', '=', self.nyc01.id),
                ('code', '=', code),
            ])
            self.assertEqual(len(stype), 1,
                             'Space type %s not found for NYC01.' % code)
            self.assertEqual(stype.default_occupancy, default_occ,
                             '%s default_occupancy should be %d.' % (code, default_occ))
            self.assertEqual(stype.max_occupancy, max_occ,
                             '%s max_occupancy should be %d.' % (code, max_occ))

    def test_03_twenty_spaces(self):
        """Exactly 20 spaces must be created for NYC01."""
        spaces = self.env['hospitality.space'].search([
            ('property_id', '=', self.nyc01.id),
            ('code', 'in', [
                '101', '102', '103', '104', '105',
                '201', '202', '203', '204', '205',
                '301', '302', '303', '304', '305',
                '401', '402', '403', '404', '405',
            ]),
        ])
        self.assertEqual(len(spaces), 20,
                         'Expected 20 demo spaces, found %d.' % len(spaces))

    def test_04_mixed_status_distribution(self):
        """Demo spaces must have at least 5 distinct statuses."""
        spaces = self.env['hospitality.space'].search([
            ('property_id', '=', self.nyc01.id),
        ])
        statuses = set(spaces.mapped('status'))
        self.assertGreaterEqual(
            len(statuses), 5,
            'Expected ≥5 distinct statuses in demo data, found: %s' % statuses,
        )

    def test_05_room_105_ooo(self):
        """Room 105 must be OOO with reason 'Carpet replacement' and a 5-day window.

        NOTE: ooo_from is stamped with datetime.now() at the moment the demo
        XML is loaded (module install), not at test-run time. If the module
        was installed on an earlier day and the test DB was later reused
        (e.g. `-u` upgrade instead of `-i` reinstall), ooo_from will legitimately
        predate `date.today()`. We therefore assert on the *span* (the real
        business invariant) rather than absolute equality with "today", and
        only sanity-check that ooo_from isn't in the future or absurdly stale.
        """
        space = self.env['hospitality.space'].search([
            ('property_id', '=', self.nyc01.id),
            ('code', '=', '105'),
        ])
        self.assertEqual(len(space), 1, 'Room 105 not found.')
        self.assertEqual(space.status, 'ooo', 'Room 105 should be OOO.')
        self.assertEqual(space.ooo_reason, 'Carpet replacement')

        today = date.today()
        self.assertLessEqual(space.ooo_from, today,
                             'ooo_from should not be in the future.')
        self.assertGreaterEqual(space.ooo_from, today - timedelta(days=30),
                                'ooo_from looks stale (>30 days old) — '
                                'demo data may need a reinstall (`-i`).')
        self.assertEqual(space.ooo_to - space.ooo_from, timedelta(days=5),
                         'OOO window should span exactly 5 days.')

    def test_06_room_205_oos(self):
        """Room 205 must be OOS with reason 'Renovation block' and a 30-day window.

        See note on test_05_room_105_ooo re: why we check the span rather than
        asserting oos_from == date.today().
        """
        space = self.env['hospitality.space'].search([
            ('property_id', '=', self.nyc01.id),
            ('code', '=', '205'),
        ])
        self.assertEqual(len(space), 1, 'Room 205 not found.')
        self.assertEqual(space.status, 'oos', 'Room 205 should be OOS.')
        self.assertEqual(space.oos_reason, 'Renovation block')

        today = date.today()
        self.assertLessEqual(space.oos_from, today,
                             'oos_from should not be in the future.')
        self.assertGreaterEqual(space.oos_from, today - timedelta(days=30),
                                'oos_from looks stale (>30 days old) — '
                                'demo data may need a reinstall (`-i`).')
        self.assertEqual(space.oos_to - space.oos_from, timedelta(days=30),
                         'OOS window should span exactly 30 days.')
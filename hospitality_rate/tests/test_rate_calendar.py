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
RATE-07 — Tour tests for the Rate Calendar custom OWL client action.

IMPORTANT — must be run with --workers 0
----------------------------------------
HttpCase tour tests spin up a headless browser that needs to reach the
same Python process holding the test data. In prefork (workers > 0)
mode, the test framework cannot determine the HTTP port and crashes
in setUpClass with:

    AttributeError: 'PreforkServer' object has no attribute 'httpd'

To avoid an opaque crash, this test class auto-skips itself when it
detects prefork mode and prints clear instructions.

Run with:
  ./odoo-bin -c odoo.conf -d <db> -u hospitality_rate \\
             --test-enable --workers 0 --stop-after-init \\
             --test-tags /hospitality_rate:TestRateCalendarTours
"""

import logging
import unittest
import uuid
from datetime import date, timedelta

import odoo
from odoo.tests import HttpCase, tagged

_logger = logging.getLogger(__name__)


def _http_test_supported():
    """Return True iff this process can host HttpCase tour tests.

    HttpCase requires single-threaded mode so the headless browser can
    reach the test data inside the same Python process.
    """
    server = getattr(odoo.service.server, 'server', None)
    return server is not None and hasattr(server, 'httpd')


@tagged('post_install', '-at_install')
class TestRateCalendarTours(HttpCase):
    """Browser-driven tour tests for the RATE-07 Rate Calendar."""

    # The Rate Calendar is exposed as an ir.actions.client.
    ACTION_URL = "/odoo/action-hospitality_rate.action_rate_calendar"

    @classmethod
    def setUpClass(cls):
        # ── Skip cleanly when the server can't host HttpCase ───────────────
        if not _http_test_supported():
            _logger.warning(
                "TestRateCalendarTours: skipped because Odoo is running "
                "in prefork/workers mode. To run these tours, restart "
                "with --workers 0."
            )
            raise unittest.SkipTest(
                "RATE-07 tour tests require --workers 0. "
                "Restart Odoo with: --workers 0 --test-enable "
                "--test-tags /hospitality_rate:TestRateCalendarTours"
            )

        super().setUpClass()

        # ── Property ───────────────────────────────────────────────────────
        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'RATE-07 Test Property',
            })

        # ── Space type ─────────────────────────────────────────────────────
        cls.space_type = cls.env['hospitality.space.type'].search(
            [('property_id', '=', cls.property.id)], limit=1,
        )
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'RATE-07 Deluxe',
                'property_id': cls.property.id,
            })

        # ── Rate code (unique code per run to avoid duplicate-key errors) ──
        unique_suffix = uuid.uuid4().hex[:6].upper()
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'code': f'R7{unique_suffix}',
            'name': 'Rate Calendar Test',
            'property_id': cls.property.id,
            'type': 'public',
            'state': 'active',
        })

        # ── Seed a 30-day rate plan so the grid is not empty ──────────────
        cls.today = date.today()
        cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_code.id,
            'space_type_id': cls.space_type.id,
            'date_from': cls.today,
            'date_to': cls.today + timedelta(days=30),
            'occupancy_pricing': 'flat',
            'price_single': 100.0,
            'price_double': 150.0,
        })

    # ═══════════════════════════════════════════════════════════════════════
    # Tour 1 — calendar loads
    # ═══════════════════════════════════════════════════════════════════════

    def test_rate_calendar_loads(self):
        """The Rate Calendar OWL client action mounts and renders the grid."""
        self.start_tour(
            self.ACTION_URL,
            "hospitality_rate.rate_calendar_loads",
            login="admin",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Tour 2 — inline edit persists
    # ═══════════════════════════════════════════════════════════════════════

    def test_inline_edit_persists(self):
        """Cell-edit on blur calls action_upsert_cell and persists the price."""
        self.start_tour(
            self.ACTION_URL,
            "hospitality_rate.rate_calendar_inline_edit",
            login="admin",
        )

        # The tour sets one cell to 222.50. Verify that a 1-day plan now
        # exists with that price for the seeded rate code / space type.
        plan = self.env['hospitality.rate.plan'].search([
            ('rate_code_id', '=', self.rate_code.id),
            ('space_type_id', '=', self.space_type.id),
            ('price_double', '=', 222.50),
        ], limit=1)
        self.assertTrue(
            plan,
            "Inline-edited price should persist as a 1-day plan",
        )
        self.assertEqual(
            plan.date_from, plan.date_to,
            "Edited cell should be stored as a 1-day plan "
            "(split out of the multi-day seed plan).",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Tour 3 — copy range replicates prices
    # ═══════════════════════════════════════════════════════════════════════

    def test_copy_range_replicates_prices(self):
        """Copy dialog calls action_copy_range; destination mirrors source."""
        # Seed a known source price on day-0 so we can assert on day-7.
        self.env['hospitality.rate.plan']._upsert_cell(
            self.rate_code.id, self.space_type.id, self.today, 333.33,
        )

        self.start_tour(
            self.ACTION_URL,
            "hospitality_rate.rate_calendar_copy_range",
            login="admin",
        )

        # The default copy dialog copies day-0..day-6 → day-7..day-13.
        # Day-7 must therefore carry day-0's price (333.33).
        target_date = self.today + timedelta(days=7)
        plan = self.env['hospitality.rate.plan'].search([
            ('rate_code_id', '=', self.rate_code.id),
            ('space_type_id', '=', self.space_type.id),
            ('date_from', '<=', target_date),
            ('date_to', '>=', target_date),
        ], limit=1)
        self.assertTrue(
            plan,
            "A plan should cover the destination day after copy.",
        )
        self.assertEqual(
            plan.price_double, 333.33,
            "Copied destination cell must match source price.",
        )
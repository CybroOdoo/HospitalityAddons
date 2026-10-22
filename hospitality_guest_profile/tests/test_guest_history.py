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
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC License
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
"""
test_guest_history.py  (GUEST-05)
==================================
Acceptance tests for the stay-history line model and computed KPIs.

Test matrix
-----------
1. test_nights_computed
   Creating a history line with check_in / check_out calculates nights correctly.

2. test_kpis_three_demo_rows
   Adding 3 history rows to a guest yields correct total_stays, total_nights,
   total_revenue, and last_stay_date (acceptance criterion from spec).

3. test_kpis_reset_on_line_delete
   Deleting a history line recalculates KPIs.

4. test_merge_preserves_history_and_broadcasts
   Merging two guests preserves all history lines on the kept partner
   and emits the bus message on 'hospitality.guest.merged'.
"""

import json
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestGuestHistory(TransactionCase):
    """Tests for hospitality.guest.history.line and partner KPIs (GUEST-05)."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _create_guest(self, name='Test Guest', **kwargs):
        vals = {'name': name, 'is_guest': True}
        vals.update(kwargs)
        return self.env['res.partner'].create(vals)

    def _add_history(self, partner, check_in, check_out, revenue=0.0, **kwargs):
        vals = {
            'partner_id': partner.id,
            'check_in': check_in,
            'check_out': check_out,
            'revenue': revenue,
        }
        vals.update(kwargs)
        return self.env['hospitality.guest.history.line'].create(vals)

    # ==================================================================
    # Test 1 — nights computed correctly
    # ==================================================================
    def test_nights_computed(self):
        """nights = (check_out - check_in).days, stored on the record."""
        guest = self._create_guest('Alice')
        line = self._add_history(
            guest,
            check_in=date(2025, 3, 10),
            check_out=date(2025, 3, 14),
        )
        self.assertEqual(line.nights, 4, 'nights should be 4 for a 4-night stay')

    def test_nights_zero_when_no_dates(self):
        """nights defaults to 0 when check_in or check_out is missing."""
        guest = self._create_guest('Bob')
        line = self.env['hospitality.guest.history.line'].create({
            'partner_id': guest.id,
        })
        self.assertEqual(line.nights, 0)

    # ==================================================================
    # Test 2 — 3 demo rows → correct KPIs (acceptance criterion)
    # ==================================================================
    def test_kpis_three_demo_rows(self):
        """Adding 3 demo history rows must yield correct lifetime KPIs."""
        guest = self._create_guest('Carol')

        self._add_history(guest, date(2024, 1,  5), date(2024, 1,  8), revenue=300.0)
        self._add_history(guest, date(2024, 6, 20), date(2024, 6, 23), revenue=450.0)
        self._add_history(guest, date(2025, 2,  1), date(2025, 2,  5), revenue=520.0)

        # Force recompute in case of cache
        guest.invalidate_recordset()

        self.assertEqual(guest.total_stays, 3, 'total_stays should be 3')
        self.assertEqual(
            guest.total_nights,
            3 + 3 + 4,   # 3, 3, 4 nights
            'total_nights should be 10',
        )
        self.assertAlmostEqual(
            guest.total_revenue, 1270.0, places=2,
            msg='total_revenue should be 1270.0',
        )
        self.assertEqual(
            guest.last_stay_date,
            date(2025, 2, 5),
            'last_stay_date should be the latest check_out',
        )

    # ==================================================================
    # Test 3 — KPIs recalculate when a line is deleted
    # ==================================================================
    def test_kpis_reset_on_line_delete(self):
        """Removing a history line triggers KPI recomputation."""
        guest = self._create_guest('Dave')
        line1 = self._add_history(guest, date(2024, 3, 1), date(2024, 3, 4), revenue=200.0)
        line2 = self._add_history(guest, date(2024, 9, 1), date(2024, 9, 3), revenue=150.0)

        guest.invalidate_recordset()
        self.assertEqual(guest.total_stays, 2)

        line2.unlink()
        guest.invalidate_recordset()

        self.assertEqual(guest.total_stays, 1, 'total_stays should drop to 1')
        self.assertEqual(guest.total_nights, 3)
        self.assertAlmostEqual(guest.total_revenue, 200.0, places=2)
        self.assertEqual(guest.last_stay_date, date(2024, 3, 4))

    # ==================================================================
    # Test 4 — merge preserves history and broadcasts bus message
    # ==================================================================
    def test_merge_preserves_history_and_broadcasts(self):
        """
        Merging two guests must:
        1. Keep all history lines on the surviving (dst) partner.
        2. Broadcast a bus notification on 'hospitality.guest.merged'
           with {kept_id, merged_ids}.
        """
        guest_a = self._create_guest('Eve A')
        guest_b = self._create_guest('Eve B (duplicate)')

        self._add_history(guest_a, date(2024, 1, 1), date(2024, 1, 3), revenue=100.0)
        self._add_history(guest_b, date(2024, 5, 1), date(2024, 5, 4), revenue=180.0)

        merged_b_id = guest_b.id

        bus_messages = []

        def fake_sendone(channel, notification_type, message):
            if channel == 'hospitality.guest.merged':
                bus_messages.append(json.loads(message))

        wizard = self.env['base.partner.merge.automatic.wizard'].create({
            'state': 'selection',
            'dst_partner_id': guest_a.id,
            'partner_ids': [(6, 0, [guest_a.id, guest_b.id])],
        })

        with patch.object(
            type(self.env['bus.bus']),
            '_sendone',
            side_effect=fake_sendone,
        ):
            wizard._merge(
                [guest_a.id, guest_b.id],
                dst_partner=guest_a,
            )

        # History lines must have been reassigned to guest_a
        guest_a.invalidate_recordset()
        self.assertEqual(
            guest_a.total_stays, 2,
            'After merge, kept partner should have 2 stay history lines',
        )

        # Bus broadcast must have fired
        self.assertTrue(
            bus_messages,
            'A bus message should have been sent on hospitality.guest.merged',
        )
        msg = bus_messages[0]
        self.assertEqual(msg['kept_id'], guest_a.id)
        self.assertIn(merged_b_id, msg['merged_ids'])
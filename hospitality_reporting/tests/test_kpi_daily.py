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

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestKpiDaily(TransactionCase):
    """REP-02: hospitality.kpi.daily materialization.

    Fixture: 1 property, 3 physical spaces (2 sellable + 1 OOO), 1
    checked-in reservation occupying one sellable space, and 3 folio
    charge lines (room/fnb/telephone) dated to business_date — giving
    deterministic, hand-checkable expected KPI values:

        rooms_available = 3, rooms_ooo = 1, rooms_sold = 1
        occupancy_pct   = 1 / (3 - 1) = 0.5
        room_revenue = 150.0, fnb_revenue = 40.0, other_revenue = 10.0
        total_revenue = 200.0
        adr     = 150.0 / 1 = 150.0
        rev_par = 150.0 / 3 = 50.0
    """

    @classmethod
    def _safe_vals(cls, model_name, vals):
        """Filter vals down to fields that actually exist on
        model_name, so guessed-at fields on models we don't have the
        source for (space type, rate code) don't raise 'invalid
        field' if the real model doesn't have them."""
        existing_fields = cls.env[model_name]._fields
        return {k: v for k, v in vals.items() if k in existing_fields}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KpiDaily = cls.env['hospitality.kpi.daily']
        cls.business_date = fields.Date.today()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'REP-02 Test Property',
            'code': 'REP02',
            'company_id': cls.env.company.id,
        })

        cls.space_type = cls.env['hospitality.space.type'].create(
            cls._safe_vals('hospitality.space.type', {
                'name': 'Standard Room',
                'code': 'STD',
                'property_id': cls.property.id,
            })
        )

        cls.rate_code = cls.env['hospitality.rate.code'].create(
            cls._safe_vals('hospitality.rate.code', {
                'name': 'Best Available Rate',
                'code': 'BAR',
                'property_id': cls.property.id,
            })
        )

        # 2 sellable spaces + 1 OOO space (all physical, non-virtual).
        cls.space_sold = cls.env['hospitality.space'].create({
            'name': 'Room 101',
            'code': '101',
            'space_type_id': cls.space_type.id,
            'property_id': cls.property.id,
            'status': 'occupied_clean',
        })
        cls.space_vacant = cls.env['hospitality.space'].create({
            'name': 'Room 102',
            'code': '102',
            'space_type_id': cls.space_type.id,
            'property_id': cls.property.id,
            'status': 'vacant_clean',
        })
        cls.space_ooo = cls.env['hospitality.space'].create({
            'name': 'Room 103',
            'code': '103',
            'space_type_id': cls.space_type.id,
            'property_id': cls.property.id,
            'status': 'ooo',
            'ooo_from': fields.Date.today(),
            'ooo_to': fields.Date.today() + timedelta(days=1),
            'ooo_reason': 'REP-02 test fixture',
        })

        cls.guest = cls.env['res.partner'].create({
            'name': 'REP-02 Test Guest',
            'company_type': 'person',
        })

        cls.reservation = cls.env['hospitality.reservation'].create({
            'property_id': cls.property.id,
            'partner_id': cls.guest.id,
            'arrival': cls.business_date,
            'departure': cls.business_date + timedelta(days=2),
            'space_type_id': cls.space_type.id,
            'space_id': cls.space_sold.id,
            'rate_code_id': cls.rate_code.id,
            'state': 'checked_in',
        })

        cls.folio = cls.env['hospitality.folio'].create({
            'reservation_id': cls.reservation.id,
            'property_id': cls.property.id,
            'partner_id': cls.guest.id,
        })

        cls.txn_room = cls.env['hospitality.transaction.code'].create({
            'code': 'ROOM-REP02',
            'name': 'Room Charge',
            'transaction_type': 'charge',
            'category_filter': 'room',
        })
        cls.txn_fnb = cls.env['hospitality.transaction.code'].create({
            'code': 'FNB-REP02',
            'name': 'Restaurant Charge',
            'transaction_type': 'charge',
            'category_filter': 'fnb',
        })
        cls.txn_other = cls.env['hospitality.transaction.code'].create({
            'code': 'TEL-REP02',
            'name': 'Telephone Charge',
            'transaction_type': 'charge',
            'category_filter': 'telephone',
        })

        cls.env['hospitality.folio.line'].create({
            'folio_id': cls.folio.id,
            'transaction_code_id': cls.txn_room.id,
            'business_date': cls.business_date,
            'qty': 1,
            'unit_price': 150.0,
        })
        cls.env['hospitality.folio.line'].create({
            'folio_id': cls.folio.id,
            'transaction_code_id': cls.txn_fnb.id,
            'business_date': cls.business_date,
            'qty': 1,
            'unit_price': 40.0,
        })
        cls.env['hospitality.folio.line'].create({
            'folio_id': cls.folio.id,
            'transaction_code_id': cls.txn_other.id,
            'business_date': cls.business_date,
            'qty': 1,
            'unit_price': 10.0,
        })

    def test_materialize_computes_all_fields(self):
        kpi = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)

        self.assertEqual(kpi.property_id, self.property)
        self.assertEqual(kpi.business_date, self.business_date)

        self.assertEqual(kpi.rooms_available, 3)
        self.assertEqual(kpi.rooms_ooo, 1)
        self.assertEqual(kpi.rooms_sold, 1)
        self.assertEqual(kpi.rooms_complimentary, 0)

        self.assertEqual(kpi.room_revenue, 150.0)
        self.assertEqual(kpi.fnb_revenue, 40.0)
        self.assertEqual(kpi.other_revenue, 10.0)
        self.assertEqual(kpi.total_revenue, 200.0)

        self.assertAlmostEqual(kpi.occupancy_pct, 0.5, places=4)
        self.assertAlmostEqual(kpi.adr, 150.0, places=2)
        self.assertAlmostEqual(kpi.rev_par, 50.0, places=2)

        self.assertEqual(kpi.arrivals, 1)
        self.assertEqual(kpi.departures, 0)
        self.assertEqual(kpi.no_shows, 0)
        self.assertEqual(kpi.walkins, 0)
        self.assertEqual(kpi.cancellations, 0)

        self.assertIsInstance(kpi.segment_breakdown, dict)
        self.assertIsInstance(kpi.source_breakdown, dict)
        # No market_segment_id/source_code_id set on the fixture
        # reservation, so both breakdowns should bucket it as
        # "Unspecified" with count 1.
        self.assertEqual(sum(kpi.segment_breakdown.values()), 1)
        self.assertEqual(sum(kpi.source_breakdown.values()), 1)

    def test_occupancy_pct_excludes_ooo(self):
        kpi = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)

        # Naive occupancy (sold / total available, ignoring OOO) would
        # be 1/3 ≈ 0.333 — occupancy_pct must NOT equal that; it must
        # exclude the OOO room from the denominator: 1/(3-1) = 0.5.
        naive_occupancy = kpi.rooms_sold / kpi.rooms_available
        self.assertNotAlmostEqual(kpi.occupancy_pct, naive_occupancy, places=3)
        self.assertAlmostEqual(kpi.occupancy_pct, 0.5, places=4)

    def test_unique_per_property_per_date(self):
        kpi_first = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)
        first_id = kpi_first.id

        # Add another room charge, then re-materialize for the SAME
        # property/date — this must update the existing row in place
        # (upsert), not create a second one.
        self.env['hospitality.folio.line'].create({
            'folio_id': self.folio.id,
            'transaction_code_id': self.txn_room.id,
            'business_date': self.business_date,
            'qty': 1,
            'unit_price': 75.0,
        })
        kpi_second = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)

        self.assertEqual(
            kpi_second.id, first_id,
            "Re-materializing the same property/date must update the "
            "existing row, not create a new one.")

        rows = self.KpiDaily.search([
            ('property_id', '=', self.property.id),
            ('business_date', '=', self.business_date),
        ])
        self.assertEqual(
            len(rows), 1,
            "Exactly one hospitality.kpi.daily row must exist per "
            "(property_id, business_date).")

        # Confirm the upsert actually picked up the new data.
        self.assertEqual(kpi_second.room_revenue, 225.0)
        self.assertEqual(kpi_second.total_revenue, 275.0)

        # DB-level constraint should also refuse a manual duplicate
        # create() bypassing _materialize_for_date entirely.
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.KpiDaily.create({
                    'property_id': self.property.id,
                    'business_date': self.business_date,
                })

    def test_name_uses_property_and_date(self):
        kpi = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)

        self.assertIn(self.property.name, kpi.name)
        self.assertIn(self.property.name, kpi.display_name)

    def test_breakdown_display_renders_html_not_raw_json(self):
        kpi = self.KpiDaily._materialize_for_date(
            self.property.id, self.business_date)

        # Raw Json fields still hold plain dicts (materialization
        # output is unchanged)...
        self.assertIsInstance(kpi.segment_breakdown, dict)
        self.assertIsInstance(kpi.source_breakdown, dict)

        # ...but the _display companion fields render as an HTML
        # table, not the raw '{"Unspecified": 4}' text.
        self.assertIn('<table', kpi.segment_breakdown_display)
        self.assertIn('Unspecified', kpi.segment_breakdown_display)
        self.assertNotIn('{"Unspecified"', kpi.segment_breakdown_display)
        self.assertIn('<table', kpi.source_breakdown_display)
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
class TestManagerFlash(TransactionCase):
    """REP-03: hospitality.kpi.daily.get_manager_flash_data(), the
    single RPC backing the Manager Flash OWL dashboard.

    Fixture: 1 property, 1 checked-in reservation (arrival = today),
    with a folio charge of 100.0 room revenue dated yesterday and
    150.0 dated today — two materialized snapshots give a
    hand-checkable day-over-day delta of +50.0 on room_revenue.
    """

    @classmethod
    def _safe_vals(cls, model_name, vals):
        """Filter vals down to fields that actually exist on
        model_name, so guessed-at fields on models we don't have the
        source for don't raise 'invalid field'."""
        existing_fields = cls.env[model_name]._fields
        return {k: v for k, v in vals.items() if k in existing_fields}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KpiDaily = cls.env['hospitality.kpi.daily']
        cls.today = fields.Date.today()
        cls.yesterday = cls.today - timedelta(days=1)

        cls.property = cls.env['hospitality.property'].create({
            'name': 'REP-03 Test Property',
            'code': 'REP03',
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
        cls.space = cls.env['hospitality.space'].create({
            'name': 'Room 201',
            'code': '201',
            'space_type_id': cls.space_type.id,
            'property_id': cls.property.id,
            'status': 'occupied_clean',
        })

        cls.guest = cls.env['res.partner'].create({
            'name': 'REP-03 Test Guest',
            'company_type': 'person',
        })

        cls.reservation = cls.env['hospitality.reservation'].create({
            'property_id': cls.property.id,
            'partner_id': cls.guest.id,
            'arrival': cls.today,
            'departure': cls.today + timedelta(days=2),
            'space_type_id': cls.space_type.id,
            'space_id': cls.space.id,
            'rate_code_id': cls.rate_code.id,
            'state': 'checked_in',
        })

        cls.folio = cls.env['hospitality.folio'].create({
            'reservation_id': cls.reservation.id,
            'property_id': cls.property.id,
            'partner_id': cls.guest.id,
        })

        cls.txn_room = cls.env['hospitality.transaction.code'].create({
            'code': 'ROOM-REP03',
            'name': 'Room Charge',
            'transaction_type': 'charge',
            'category_filter': 'room',
        })

        # Yesterday: 100 room revenue. Today: 150 room revenue.
        cls.env['hospitality.folio.line'].create({
            'folio_id': cls.folio.id,
            'transaction_code_id': cls.txn_room.id,
            'business_date': cls.yesterday,
            'qty': 1,
            'unit_price': 100.0,
        })
        cls.env['hospitality.folio.line'].create({
            'folio_id': cls.folio.id,
            'transaction_code_id': cls.txn_room.id,
            'business_date': cls.today,
            'qty': 1,
            'unit_price': 150.0,
        })

        cls.KpiDaily._materialize_for_date(cls.property.id, cls.yesterday)
        cls.KpiDaily._materialize_for_date(cls.property.id, cls.today)

    def test_manager_flash_loads(self):
        data = self.KpiDaily.get_manager_flash_data(self.property.id)

        self.assertTrue(data['has_data'])
        self.assertEqual(data['property_id'], self.property.id)
        self.assertEqual(data['property_name'], self.property.name)
        self.assertEqual(str(data['business_date']), str(self.today))

        # Headline KPI (today's snapshot) + day-over-day delta.
        self.assertAlmostEqual(data['kpis']['room_revenue'], 150.0, places=2)
        self.assertAlmostEqual(
            data['kpis']['room_revenue_delta'], 50.0, places=2,
            msg="Today's room_revenue (150) minus yesterday's (100) "
                "should be +50")

        # Flow counters read from today's snapshot: reservation
        # arrival is 'today', so today's arrivals count is 1.
        self.assertEqual(data['flow']['arrivals'], 1)

        # Live in-house figures: 1 checked-in reservation for this
        # property regardless of which business_date snapshot is
        # latest.
        self.assertEqual(data['in_house']['count'], 1)
        self.assertIsInstance(data['in_house']['balance'], float)

        # Channel/source mix present and well-formed (list of
        # {label, value} dicts), even though no market_segment_id/
        # source_code_id was set on the fixture reservation.
        self.assertIn('channel_mix', data)
        self.assertIn('source_mix', data)
        for mix in (data['channel_mix'], data['source_mix']):
            self.assertTrue(mix)
            self.assertIn('label', mix[0])
            self.assertIn('value', mix[0])

    def test_manager_flash_no_snapshot_yet(self):
        """A property with no hospitality.kpi.daily rows yet should
        return has_data=False rather than raising."""
        empty_property = self.env['hospitality.property'].create({
            'name': 'REP-03 Empty Property',
            'code': 'REP03EMPTY',
            'company_id': self.env.company.id,
        })
        data = self.KpiDaily.get_manager_flash_data(empty_property.id)
        self.assertFalse(data['has_data'])
        self.assertEqual(data['property_id'], empty_property.id)
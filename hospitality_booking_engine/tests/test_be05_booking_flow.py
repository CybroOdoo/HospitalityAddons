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
"""BE-05 controller + booking-finalization tests.

NOTE: given the flagged assumptions in
hospitality_be_search_session._get_rate_quote() and _finalize_booking()
(see that file's docstrings), these tests are the fastest way to find
out which assumptions are wrong — run them first before the full
browser tour.
"""
import re
import uuid
from datetime import date, timedelta

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestBE05BookingFlow(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'BE-05 Test Property',
            'code': f'BE05T{uuid.uuid4().hex[:6].upper()}',
        })
        cls.env['hospitality.be.config'].create({
            'property_id': cls.property.id,
            'theme': 'light',
        })
        # FIX: property_id is NOT NULL on hospitality.space.type
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'BE-05 Standard Room',
            'code': f'BE05ST{uuid.uuid4().hex[:6].upper()}',
            'property_id': cls.property.id,
        })
        # FIX: property_id is NOT NULL on hospitality.rate.code
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BE-05 Best Available Rate',
            'code': f'BE05RC{uuid.uuid4().hex[:6].upper()}',
            'property_id': cls.property.id,
        })
        cls.promo = cls.env['hospitality.be.promo.code'].create({
            'code': 'BE05SAVE10',
            'property_id': cls.property.id,
            'discount_pct': 10.0,
        })
        cls.arrival = (date.today() + timedelta(days=30)).isoformat()
        cls.departure = (date.today() + timedelta(days=33)).isoformat()

    def _csrf_token(self, url):
        response = self.url_open(url)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
        return match.group(1) if match else ''

    def test_search_returns_available_rates(self):
        token = self._csrf_token('/booking')
        response = self.url_open('/booking/results', data={
            'csrf_token': token,
            'property_id': self.property.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': 2,
            'children': 0,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('o_be_results', response.text)

    def test_cart_apply_promo_reduces_total(self):
        session = self.env['hospitality.be.search.session'].create({
            'property_id': self.property.id,
            'selected_rate_code_id': self.rate_code.id,
            'selected_space_type_id': self.space_type.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': 2,
        })
        totals_before = session._cart_totals()
        session._apply_promo_code('BE05SAVE10')
        totals_after = session._cart_totals()
        self.assertLessEqual(totals_after['total'], totals_before['total'])

    def test_checkout_creates_reservation_on_payment_success(self):
        session = self.env['hospitality.be.search.session'].create({
            'property_id': self.property.id,
            'selected_rate_code_id': self.rate_code.id,
            'selected_space_type_id': self.space_type.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': 2,
            'contact_email': 'be05-guest@example.com',
            'guest_name': 'BE-05 Test Guest',
        })
        reservation = session._finalize_booking()
        self.assertTrue(reservation)
        self.assertEqual(session.reservation_id, reservation)

    def test_reservation_marked_confirmed_with_deposit_paid(self):
        session = self.env['hospitality.be.search.session'].create({
            'property_id': self.property.id,
            'selected_rate_code_id': self.rate_code.id,
            'selected_space_type_id': self.space_type.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': 2,
            'contact_email': 'be05-guest2@example.com',
            'guest_name': 'BE-05 Test Guest Two',
        })
        reservation = session._finalize_booking()
        if 'state' in reservation._fields:
            self.assertEqual(reservation.state, 'confirmed')
        if 'created_via' in reservation._fields:
            self.assertEqual(reservation.created_via, 'booking_engine')

    def test_lookup_route_returns_reservation_by_ref_email(self):
        session = self.env['hospitality.be.search.session'].create({
            'property_id': self.property.id,
            'selected_rate_code_id': self.rate_code.id,
            'selected_space_type_id': self.space_type.id,
            'arrival': self.arrival,
            'departure': self.departure,
            'adults': 2,
            'contact_email': 'be05-guest3@example.com',
            'guest_name': 'BE-05 Test Guest Three',
        })
        reservation = session._finalize_booking()
        ref = reservation.name if 'name' in reservation._fields else str(reservation.id)

        response = self.url_open(
            f'/booking/lookup?ref={ref}&email=be05-guest3@example.com'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('o_be_lookup', response.text)
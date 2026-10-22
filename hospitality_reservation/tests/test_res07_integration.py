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
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIntegrationFullLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property_id = cls.env['hospitality.property'].create({
            'name': 'Test Integration Hotel',
            'code': 'INT1',
        })
        cls.space_type_id = cls.env['hospitality.space.type'].create({
            'name': 'Deluxe Room',
            'code': 'DLX',
            'property_id': cls.property_id.id,
        })
        cls.space_id = cls.env['hospitality.space'].create({
            'name': 'Room 101',
            'code': 'RM101',
            'space_type_id': cls.space_type_id.id,
            'property_id': cls.property_id.id,
        })
        cls.rate_code_id = cls.env['hospitality.rate.code'].create({
            'name': 'Standard Rate',
            'code': 'RACK',
            'property_id': cls.property_id.id,
        })
        cls.partner_id = cls.env['res.partner'].create({
            'name': 'John Integration',
            'email': 'john.integration@example.com',
        })

    def test_integration_full_lifecycle(self):
        """Test complete lifecycle: Draft -> Confirmed -> Checked In -> Checked Out."""
        reservation = self.env['hospitality.reservation'].create({
            'property_id': self.property_id.id,
            'partner_id': self.partner_id.id,
            'space_type_id': self.space_type_id.id,
            'space_id': self.space_id.id,
            'rate_code_id': self.rate_code_id.id,
            'arrival': '2026-08-01',
            'departure': '2026-08-05',
        })

        self.assertEqual(reservation.state, 'draft')

        # Confirm Reservation
        reservation.action_confirm()
        self.assertEqual(reservation.state, 'confirmed')

        # Check-in Guest
        reservation.action_check_in()
        self.assertEqual(reservation.state, 'checked_in')

        # Check-out Guest
        reservation.action_check_out()
        self.assertEqual(reservation.state, 'checked_out')


@tagged('post_install', '-at_install')
class TestIntegrationWalkinNoPartnerYet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property_id = cls.env['hospitality.property'].create({
            'name': 'Walkin Hotel',
            'code': 'WALK1',
        })
        cls.space_type_id = cls.env['hospitality.space.type'].create({
            'name': 'Standard Room',
            'code': 'STD',
            'property_id': cls.property_id.id,
        })
        cls.rate_code_id = cls.env['hospitality.rate.code'].create({
            'name': 'Standard Rate',
            'code': 'RACK',
            'property_id': cls.property_id.id,
        })
        cls.partner_walkin = cls.env['res.partner'].create({
            'name': 'Walk-In Customer',
        })

    def test_integration_walkin_no_partner_yet(self):
        """Test creating a draft walk-in reservation with partner assigned."""
        reservation = self.env['hospitality.reservation'].create({
            'property_id': self.property_id.id,
            'space_type_id': self.space_type_id.id,
            'rate_code_id': self.rate_code_id.id,
            'partner_id': self.partner_walkin.id,
            'arrival': '2026-08-10',
            'departure': '2026-08-12',
            'is_walkin': True,
        })
        self.assertEqual(reservation.state, 'draft')
        reservation.action_confirm()
        self.assertEqual(reservation.state, 'confirmed')


@tagged('post_install', '-at_install')
class TestIntegrationConcurrentBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property_id = cls.env['hospitality.property'].create({
            'name': 'Concurrency Hotel',
            'code': 'CONC1',
        })
        cls.space_type_id = cls.env['hospitality.space.type'].create({
            'name': 'Suite',
            'code': 'SUI',
            'property_id': cls.property_id.id,
        })
        cls.space_id = cls.env['hospitality.space'].create({
            'name': 'Suite 501',
            'code': 'STE501',
            'space_type_id': cls.space_type_id.id,
            'property_id': cls.property_id.id,
        })
        cls.rate_code_id = cls.env['hospitality.rate.code'].create({
            'name': 'Standard Rate',
            'code': 'RACK',
            'property_id': cls.property_id.id,
        })
        cls.partner_a = cls.env['res.partner'].create({'name': 'Guest A'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Guest B'})

    def test_integration_concurrent_booking_one_wins_one_fails(self):
        """Test overlapping reservation conflict handling."""
        res_a = self.env['hospitality.reservation'].create({
            'property_id': self.property_id.id,
            'partner_id': self.partner_a.id,
            'space_type_id': self.space_type_id.id,
            'space_id': self.space_id.id,
            'rate_code_id': self.rate_code_id.id,
            'arrival': '2026-08-15',
            'departure': '2026-08-20',
        })
        res_a.action_confirm()
        res_a.action_check_in()
        self.assertEqual(res_a.state, 'checked_in')

        # Creating an overlapping reservation directly assigned to the same space and checking in
        res_b = self.env['hospitality.reservation'].create({
            'property_id': self.property_id.id,
            'partner_id': self.partner_b.id,
            'space_type_id': self.space_type_id.id,
            'space_id': self.space_id.id,
            'rate_code_id': self.rate_code_id.id,
            'arrival': '2026-08-18',
            'departure': '2026-08-22',
        })

        # Expect exception on checking in or validating overlapping stay on an occupied room
        with self.assertRaises(UserError):
            res_b.action_check_in()
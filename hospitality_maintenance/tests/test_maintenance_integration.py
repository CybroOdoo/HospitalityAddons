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

from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHospitalityMaintenanceIntegration(TransactionCase):
    """MAINT-05: cross-module integration between hospitality.work.order
    and hospitality.space's own OOO status — a guest-blocking work order
    with set_ooo=True must remove its room from bookable inventory the
    moment it starts, and hand the room back once the work is done.

    Self-contained (own property/room), matching the setUpClass pattern
    already used by every other MAINT-0x test file, rather than relying
    on the module's demo data being loaded.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'MAINT-05 Test Property',
            'code': 'MT05',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'MAINT-05 Test Room Type',
            'code': 'MT05STD',
            'property_id': cls.property.id,
        })
        cls.room = cls.env['hospitality.space'].create({
            'name': 'MAINT-05 Test Room 501',
            'code': 'MT501',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

    def _bookable_room_ids(self):
        """Domain mirroring how front-desk/reservation availability
        excludes rooms that are out of service — anything not currently
        'ooo' or 'oos' is still part of bookable inventory."""
        return self.env['hospitality.space'].search([
            ('property_id', '=', self.property.id),
            ('status', 'not in', ('ooo', 'oos')),
        ]).ids

    def test_integration_guest_blocking_wo_takes_room_out_of_inventory(self):
        """Starting a guest-blocking, set_ooo=True work order must pull
        its room out of bookable inventory; completing it must hand the
        room back."""
        self.assertIn(
            self.room.id, self._bookable_room_ids(),
            "Sanity check: the room must start out bookable.")

        order = self.env['hospitality.work.order'].create({
            'property_id': self.property.id,
            'space_id': self.room.id,
            'category': 'hvac',
            'priority': 'guest_blocking',
            'source': 'guest',
            'description': 'AC unit not cooling, guest reported.',
            'set_ooo': True,
            'ooo_from': Date.today() + timedelta(days=1),
            'ooo_to': Date.today() + timedelta(days=3),
        })
        order.action_open()
        order.action_start()

        self.assertEqual(order.state, 'in_progress')
        self.assertEqual(self.room.status, 'ooo')
        self.assertNotIn(
            self.room.id, self._bookable_room_ids(),
            "Room must drop out of bookable inventory once a "
            "guest-blocking work order takes it OOO.")

        order.action_done()

        self.assertEqual(order.state, 'done')
        self.assertEqual(self.room.status, 'vacant_dirty')
        self.assertIn(
            self.room.id, self._bookable_room_ids(),
            "Room must return to bookable inventory once the work "
            "order that blocked it is completed.")
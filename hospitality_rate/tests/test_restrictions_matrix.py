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
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestRestrictionsMatrix(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test Property
        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'THTL',
        })

        # Create a test Rate Code
        cls.rate_code = cls.env['hospitality.rate.code'].create({
            'name': 'BAR',
            'code': 'BAR',
            'property_id': cls.property.id,
        })

        # Create a test Space Type
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'Deluxe Room',
            'code': 'DLX',
            'property_id': cls.property.id,
        })

    def test_restrictions_matrix_renders(self):
        """Run the tour to verify the UI renders without crashing."""
        self.start_tour("/web", 'test_restrictions_matrix_renders', login="admin")

    def test_restrictions_matrix_set_closed(self):
        """Run the tour to verify the drag-to-close functionality."""
        # Directly load the matrix action URL to skip navigation steps
        action = self.env.ref('hospitality_rate.action_restrictions_matrix')  # Ensure this xml_id matches yours
        url = f"/web#action={action.id}"

        self.start_tour(url, 'test_restrictions_matrix_set_closed', login="admin")
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
"""BE-04: website QWeb template tour test.

Exercises navigation across the BE-04 preview routes only (see
controllers/booking_engine_preview_controller.py) — not real
search/cart/checkout business logic, which lands with BE-05. Extend or
supersede this tour once BE-05's controllers replace the preview
scaffold.

NOTE: like other HttpCase tour tests in this codebase, this requires
--workers 0 to run.
"""
import uuid

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestBE04WebsiteTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'BE-04 Tour Property',
            'code': f'BE04T{uuid.uuid4().hex[:6].upper()}',
        })
        cls.env['hospitality.be.config'].create({
            'property_id': cls.property.id,
            'theme': 'brand',
            'primary_color': '#1F7A5C',
        })

    def test_booking_flow_tour(self):
        self.start_tour(
            "/booking",
            "hospitality_be04_booking_flow_tour",
            login=None,
        )
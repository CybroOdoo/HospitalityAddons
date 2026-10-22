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
"""BE-06: full integration tour — search through confirmation, against
real demo data (NYC01 property, BAR rate code with its RATE-10 rate
plans, and this module's own promo/upsell demo records).

Requires demo data to be loaded (do not run with --without-demo) and
at least one bookable payment.provider (Odoo's built-in Demo provider,
from the base `payment` module, normally satisfies this).
"""
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestBE06Integration(HttpCase):

    def test_integration_full_booking_flow(self):
        nyc01 = self.env.ref(
            'hospitality_base.demo_property_nyc01', raise_if_not_found=False
        )
        if not nyc01:
            self.skipTest(
                "hospitality_base.demo_property_nyc01 not found — "
                "demo data not loaded for this database."
            )
        bar = self.env.ref(
            'hospitality_rate.rate_code_bar_nyc01', raise_if_not_found=False
        )
        if not bar:
            self.skipTest(
                "hospitality_rate.rate_code_bar_nyc01 not found — "
                "RATE-10 demo data not loaded."
            )
        self.start_tour(
            "/booking",
            "hospitality_be06_full_booking_flow_tour",
            login=None,
        )
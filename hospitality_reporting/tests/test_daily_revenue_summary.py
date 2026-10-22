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
class TestDailyRevenueSummary(TransactionCase):
    """REP-03: Daily Revenue Summary pivot (business_date rows,
    revenue-category measures) and the QWeb PDF report.

    Fixture: two hospitality.kpi.daily rows created directly (the
    pivot/report only read already-materialized Monetary fields, so
    no reservation/folio fixtures are needed here — that path is
    already covered by test_kpi_daily.py / test_manager_flash.py).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KpiDaily = cls.env['hospitality.kpi.daily']
        cls.day1 = fields.Date.today() - timedelta(days=1)
        cls.day2 = fields.Date.today()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'REP-03 Revenue Test Property',
            'code': 'REP03REV',
            'company_id': cls.env.company.id,
        })

        cls.kpi_day1 = cls.KpiDaily.create({
            'property_id': cls.property.id,
            'business_date': cls.day1,
            'rooms_available': 10,
            'rooms_sold': 4,
            'rooms_ooo': 0,
            'room_revenue': 400.0,
            'fnb_revenue': 80.0,
            'other_revenue': 20.0,
        })
        cls.kpi_day2 = cls.KpiDaily.create({
            'property_id': cls.property.id,
            'business_date': cls.day2,
            'rooms_available': 10,
            'rooms_sold': 6,
            'rooms_ooo': 0,
            'room_revenue': 600.0,
            'fnb_revenue': 100.0,
            'other_revenue': 30.0,
        })

    def test_daily_revenue_pivot_groups_correctly(self):
        """Grouping by business_date (the pivot's row axis) must keep
        the two snapshot days separate, and each day's total_revenue
        must equal room + fnb + other for that day."""
        rows = self.KpiDaily._read_group(
            domain=[('property_id', '=', self.property.id)],
            groupby=['business_date:day'],
            aggregates=['room_revenue:sum', 'fnb_revenue:sum',
                        'other_revenue:sum', 'total_revenue:sum'],
        )
        self.assertEqual(
            len(rows), 2,
            "Grouping by business_date should keep the two snapshot "
            "days separate, matching the pivot's row axis.")

        totals = sorted(
            round(total_revenue)
            for _date, _room, _fnb, _other, total_revenue in rows
        )
        self.assertEqual(
            totals, [500, 730],
            "day1 total (400+80+20=500) and day2 total "
            "(600+100+30=730) should each appear as their own row.")

    def test_daily_revenue_pdf_renders(self):
        docs = self.kpi_day1 + self.kpi_day2
        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            'hospitality_reporting.report_daily_revenue_summary', docs.ids)
        html_str = html.decode() if isinstance(html, bytes) else html

        # Header: property + period.
        self.assertIn(self.property.name, html_str)
        self.assertIn(str(self.day1), html_str)
        self.assertIn(str(self.day2), html_str)

        # Both days' room revenue rendered somewhere in the table.
        self.assertIn('400.00', html_str)
        self.assertIn('600.00', html_str)
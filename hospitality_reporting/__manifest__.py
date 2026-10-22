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
{
    'name': "Hospitality Management - Reporting",
    'version': '19.0.1.0.0',
    'category': 'Hospitality/Reporting',
    'summary': "Hotel reporting and dashboards for Odoo: manager flash, daily KPIs, occupancy, ADR, RevPAR and revenue summary.",
    'description': """
Hospitality Management - Reporting
==================================
Reporting and dashboards for the Hospitality Management suite. A manager flash shows occupancy, ADR, RevPAR and revenue with day-over-day movement, backed by a stored daily KPI table available as list, pivot and graph, plus a daily revenue summary and segment and source mix. Every hotel report is sourced from the night audit rather than recalculated ad hoc, so the numbers match the books.

Key Features
------------
* Manager flash with day-over-day deltas
* Daily KPI table with pivot and graph views
* Daily revenue summary by day
* Occupancy, ADR and RevPAR
* Market segment and booking source mix
* Figures sourced from the night audit
    """,
    'author': "Cybrosys Techno Solutions",
    'company': "Cybrosys Techno Solutions",
    'maintainer': "Cybrosys Techno Solutions",
    'website': "https://www.cybrosys.com",
    'depends': [
        'hospitality_base',
        'hospitality_reservation',
        'hospitality_folio',
        'hospitality_night_audit',
    ],
    'data': [
        'security/security_groups.xml',
        # 'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/reporting_menus.xml',
        'views/hospitality_kpi_daily_views.xml',
        'views/manager_flash_views.xml',
        'views/daily_revenue_summary_views.xml',
        'reports/daily_revenue_summary_templates.xml',
        'reports/daily_revenue_summary_reports.xml',
            # LAST in the list on purpose: this calls a helper that
        # refuses to hide a stock menu unless the replacement
        # menu already exists, and the replacement is created by
        # the view files above.
        'data/hide_core_menus.xml',
    ],
    'demo': [
        'demo/hospitality_kpi_daily_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_reporting/static/src/scss/manager_flash.scss',
            'hospitality_reporting/static/src/js/manager_flash.js',
            'hospitality_reporting/static/src/xml/manager_flash.xml',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}

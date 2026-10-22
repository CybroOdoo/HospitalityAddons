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
    'name': "Hospitality Management - Rate",
    'version': '19.0.1.0.0',
    'category': 'Hospitality',
    'summary': "Hotel rate management for Odoo: rate codes, occupancy pricing, rate calendar, restrictions matrix and packages.",
    'description': """
Hospitality Management - Rate
=============================
Rate management and room pricing for the Hospitality Management suite. Rate codes carry per-occupancy pricing, date ranges and weekday masks, derived rates follow a base code, restriction rules such as minimum stay and closed to arrival are evaluated when a stay is quoted, and packages bundle inclusions into the room rate. A rate calendar shows what each room type sells for on any date, giving revenue management a single place to set and audit hotel tariffs.

Key Features
------------
* Rate codes with single, double and extra-person pricing
* Derived rates from a base rate code
* Date ranges and weekday masks per rate plan
* Restrictions: minimum stay, closed to arrival, closed to departure
* Rate calendar showing what each room type sells for
* Packages with inclusions
* Rate change audit trail
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'hospitality_base',
        'hospitality_property',
    ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/hospitality_package_seed.xml',
        'views/hospitality_rate_plan_views.xml',
        'views/hospitality_rate_restriction_views.xml',
        'views/hospitality_package_views.xml',
        'views/hospitality_rate_code_views.xml',
        'views/hospitality_rate_audit_views.xml',
        'views/hospitality_rate_menus.xml',
    ],
    'demo': [
        'data/demo_rate_nyc01.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_rate/static/src/js/weekday_mask_field.js',
            'hospitality_rate/static/src/js/rate_calendar.js',
            'hospitality_rate/static/src/xml/weekday_mask_field.xml',
            'hospitality_rate/static/src/xml/rate_calendar.xml',
            'hospitality_rate/static/src/scss/rate_calendar.scss',
            'hospitality_rate/static/src/scss/weekday_mask_field.scss',
            'hospitality_rate/static/src/js/restrictions_matrix.js',
            'hospitality_rate/static/src/xml/restrictions_matrix.xml',
            'hospitality_rate/static/src/scss/restrictions_matrix.scss',
        ],
        'web.assets_tests': [
            'hospitality_rate/static/tests/tours/restrictions_matrix_tour.js',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,

}

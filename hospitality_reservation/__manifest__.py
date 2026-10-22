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
    'name': "Hospitality Management - Reservation",
    'version': '19.0.1.0.0',
    'category': 'Hospitality',
    'summary': "Hotel reservation management for Odoo: tape chart, booking lifecycle, arrivals, in-house, departures and trace pickup.",
    'description': """
Hospitality Management - Reservation
====================================
Reservation and booking management for the Hospitality Management suite. Takes a hotel reservation from option through confirmation, check-in and check-out, with a colour-coded tape chart, dedicated arrivals, in-house and departure work lists, trace pickup for follow-ups, and source and market segment on every booking. The tape chart makes room availability and the shape of the month readable at a glance.

Key Features
------------
* Tape chart by room or room type, colour-coded by reservation state
* Reservation lifecycle: option, confirmed, checked in, checked out, no-show, cancelled
* Arrivals, in-house and departure work lists
* Trace pickup so follow-ups are not missed
* Source and market segment captured on every booking
* Rate plan and occupancy priced per stay
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'hospitality_base',
        'hospitality_property',
        'hospitality_guest_profile',
        'hospitality_company_profile',
        'hospitality_rate',
    ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/hospitality_activity_trace_views.xml',
        'views/hospitality_reservation_views.xml',
        'views/hospitality_reservation_tape_chart.xml',
        'views/hospitality_reservation_front_office_views.xml',
        'wizards/hospitality_reservation_share_wizard_views.xml',
    ],
    'demo': [
        'demo/hospitality_reservations_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_reservation/static/src/scss/tape_chart_view.scss',
            'hospitality_reservation/static/src/js/tape_chart_view.js',
            'hospitality_reservation/static/src/xml/tape_chart_view.xml',
        ],
        'web.assets_tests': [
            'hospitality_reservation/static/tests/tours/tape_chart_tours.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
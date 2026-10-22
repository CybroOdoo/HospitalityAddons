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
    'name': "Hospitality Management - Front Desk",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'summary': "Hotel front desk operations for Odoo: check-in, check-out, walk-ins, room moves, arrival queue and shift dashboard.",
    'description': """
Hospitality Management - Front Desk
===================================
Front office and reception operations for the Hospitality Management suite. Gives the hotel front desk a shift dashboard with arrivals, in-house, departures, availability by room type and outstanding receivables, plus guided check-in, check-out, walk-in registration and room-move flows that move the reservation, the room status and the folio together. Everything a receptionist needs for the day sits on one screen, scoped to the property they are working in.

Key Features
------------
* Front desk dashboard scoped to one property
* Guided check-in and check-out
* Walk-in registration for unbooked guests
* Room moves mid-stay with folio and housekeeping following
* Arrival queue for the day
* Front desk shift open and close
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'mail',
        'hospitality_reservation',
        'hospitality_folio',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/hospitality_queue_entry_views.xml',
        'views/hospitality_front_desk_shift_views.xml',
        'report/report_registration_card.xml',
        'wizards/hospitality_front_desk_check_in_wizard_views.xml',
        'wizards/hospitality_front_desk_check_out_wizard_views.xml',
        'wizards/hospitality_front_desk_walk_in_wizard_views.xml',
        'wizards/hospitality_room_move_wizard_views.xml',
    ],
    'demo': [
        'demo/hospitality_front_desk_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_front_desk/static/src/js/fd_dashboard.js',
            'hospitality_front_desk/static/src/xml/fd_dashboard.xml',
            'hospitality_front_desk/static/src/scss/fd_dashboard.scss',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}

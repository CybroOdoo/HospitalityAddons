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
    'name': "Hospitality Management - Guest Profile",
    'version': '19.0.1.0.0',
    'category': 'Hospitality',
    'summary': "Hotel guest profiles for Odoo: loyalty tiers, stay history, preferences, dietary notes and PII access control.",
    'description': """
Hospitality Management - Guest Profile
======================================
Guest profiles and hotel CRM for the Hospitality Management suite. Each guest card carries loyalty tier, stay history, preferences and dietary notes that follow the guest between stays, while identity documents sit behind a dedicated PII group with every read logged for GDPR accountability, and a blacklist flag is surfaced across every booking screen. Duplicate guest records can be merged without losing history.

Key Features
------------
* Guest cards with loyalty tier and stay history
* Preference and dietary registers carried between stays
* Identity documents behind a dedicated PII group
* Read logging on sensitive fields
* Blacklist flag surfaced across the suite
* Duplicate guest merging
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'hospitality_base',
        'contacts',
    ],
    'assets': {
        'web.assets_backend': [
            'hospitality_guest_profile/static/src/scss/guest_kanban.scss',
        ],
    },
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/hospitality_guest_data.xml',
        'views/guest_preference_views.xml',
        'views/hospitality_dietary_views.xml',
        'views/res_partner_views.xml',
        'views/guest_id_document_views.xml',
        'views/menus.xml',
        'views/guest_history_line_views.xml',
        'wizard/guest_rtbf_wizard_views.xml',
    ],
    'demo': [
        'demo/demo_guests.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
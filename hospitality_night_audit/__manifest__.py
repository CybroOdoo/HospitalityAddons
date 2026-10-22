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
    'name': "Hospitality Management - Night Audit",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'summary': "Hotel night audit for Odoo: room charge posting, business date roll-forward, pre-audit checks and daily KPI snapshot.",
    'description': """
Hospitality Management - Night Audit
====================================
The nightly close and end-of-day run for the Hospitality Management suite. Posts the night's room charges, runs pre-audit validation that blocks the roll-forward when something is unresolved, moves the property's business date forward, and writes the day's occupancy, ADR, RevPAR and revenue snapshot for reporting. The hotel day close can run automatically on a schedule or be triggered by the night auditor, with a full history of every run.

Key Features
------------
* Night audit run per property
* Room charge posting for the night
* Pre-audit validation checks
* Business date roll-forward
* Daily KPI snapshot written for reporting
* Automatic or manual triggering
* Full run history with results
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'hospitality_base',
        'hospitality_reservation',
        'hospitality_folio',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/ir_cron.xml',
        'views/hospitality_night_audit_run_views.xml',
        'views/hospitality_property_auto_audit_views.xml',
        'views/hospitality_night_audit_menus.xml',
    ],
    'demo': [
        'data/demo_night_audit.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
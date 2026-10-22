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
    'name': "Hospitality Management - Housekeeping",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'summary': "Hotel housekeeping for Odoo: task board, attendant assignment, inspection workflow, DND and lost and found.",
    'description': """
Hospitality Management - Housekeeping
=====================================
Housekeeping and room cleaning management for the Hospitality Management suite. A task board grouped by room status with rush flags and attendant assignment, a supervisor room inspection workflow that releases rooms back to sellable, do-not-disturb handling, lost and found, linen counts and discrepancy resolution between the desk and the floor. Keeps the floor and the front desk working from the same live room status.

Key Features
------------
* Task board grouped by housekeeping state
* Attendant assignment and rush flags
* Supervisor inspection and room release
* Do-not-disturb register
* Lost and found linked to rooms and guests
* Linen counts and discrepancy handling
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': [
        'hospitality_base', 'hospitality_property',
        'hospitality_reservation', 'hr', 'mail'
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/hk_task_record_rules.xml',
        'security/hk_support_record_rules.xml',
        'views/hospitality_housekeeping_task_views.xml',
        'views/hospitality_housekeeper_views.xml',
        'views/hospitality_dnd_entry_views.xml',
        'views/hospitality_lost_found_views.xml',
        'views/hospitality_linen_count_views.xml',
        'views/hk_discrepancy_views.xml',
        'views/housekeeping_menus.xml',
        'report/hk_attendant_sheet_templates.xml',
        'report/hk_attendant_sheet_report.xml',
        'data/hk_cron_data.xml',
    ],
    'demo': [
        'data/hk_demo_data.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
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
    'name': "Hospitality Management - Maintenance",
    'version': '19.0.1.0.0',
    'category': 'Industries/Hospitality',
    'summary': 'Hotel maintenance for Odoo: work orders, asset register, preventive maintenance templates and work order aging.',
    'description': """
Hospitality Management - Maintenance
====================================
Engineering, maintenance and hotel asset management for the Hospitality Management suite. Raise work orders by category and priority, assign them to staff or a vendor with photographs attached, track equipment, fixtures, furniture and vehicles against the rooms they live in, and schedule preventive maintenance (PPM) from reusable templates. Guest-blocking priorities keep rooms that cannot be sold visible to the desk, and a work order aging report shows what is slipping.

Key Features
------------
* Work orders by category, priority and state
* Guest-blocking priority for rooms that cannot be sold
* Asset register linked to rooms
* Preventive maintenance (PPM) templates on a schedule
* Work order aging report
* Photographs attached to each job
    """,
    'author': "Cybrosys Techno Solutions",
    'company': "Cybrosys Techno Solutions",
    'maintainer': "Cybrosys Techno Solutions",
    'website': "https://www.cybrosys.com",
    'depends': [
        'hospitality_base',
        'hospitality_property',
        'maintenance',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/hospitality_work_order_sequence.xml',
        'data/hospitality_ppm_cron.xml',
        'data/hospitality_wo_aging_cron.xml',
        'views/hospitality_work_order_views.xml',
        'views/hospitality_work_order_aging_views.xml',
        'views/hospitality_asset_views.xml',
        'views/hospitality_ppm_template_views.xml',
        'views/maintenance_menus.xml',
            # LAST in the list on purpose: this calls a helper that
        # refuses to hide a stock menu unless the replacement
        # menu already exists, and the replacement is created by
        # the view files above.
        'data/hide_core_menus.xml',
    ],
    'demo': [
        'demo/hospitality_maintenance_demo.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
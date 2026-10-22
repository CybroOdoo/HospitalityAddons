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
    'name': "Hospitality Management - Cashiering",
    'version': '19.0.1.0.0',
    'category': 'Industries',
    'summary': "Hotel cashiering for Odoo: cashier shifts, cash drawer, payment posting and supervisor-approved void requests.",
    'description': """
Hospitality Management - Cashiering
===================================
Cashiering and cash drawer management for the Hospitality Management suite. Hotel cashiers open and close a drawer with an opening float, takings and variance, post guest payments against folios, and raise void requests that a supervisor must approve, keeping approval separate from the person posting. Shift handling and void approval give front office cash a clean audit trail at every handover.

Key Features
------------
* Cashier shift open and close
* Opening float and closing count with variance
* Payment posting against folios
* Void requests with supervisor approval
* Supervisor void inbox
* Separate cashier and cashier-supervisor security groups
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['hospitality_folio'],
     'data': [
        'security/cashier_security.xml',
        'security/ir.model.access.csv',
        'data/cashier_shift_sequence.xml',
        'views/cashier_shift_views.xml',
        'views/hospitality_void_request_views.xml',
        'views/hospitality_cashier_menus.xml',
        'report/report_cashier_shift_closeout.xml',
    ],
    'demo': [
        'demo/hospitalitily_cashiering_demo.xml',
    ],
    'post_init_hook': '_post_init_hook_cash04_demo',
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
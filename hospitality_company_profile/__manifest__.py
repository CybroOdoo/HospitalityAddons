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
    'name': "Hospitality Management - Company Profile",
    'version': '19.0.1.0.0',
    'category': 'Hospitality',
    'summary': "Corporate, travel agent and OTA accounts for Odoo hotels: contracts, negotiated rates and city ledger billing.",
    'description': """
Hospitality Management - Company Profile
========================================
Business and B2B accounts for the Hospitality Management suite. Keeps corporate clients, travel agents and online travel agencies as distinct partner types, records negotiated contract terms and agreed rates against each account, tracks agent commission, and settles after the stay through the city ledger. Gives a hotel one place to manage corporate accounts, OTA relationships and travel agent contracts.

Key Features
------------
* Corporate, travel agent and OTA partner types
* Contract records per account
* Negotiated rates linked to the account
* City ledger and credit handling
* Account-level booking history
* Commission handling for agents
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': [
        'hospitality_base',
        'hospitality_guest_profile',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/res_partner_views.xml',
        'views/hospitality_contract_views.xml',
        'wizards/hospitality_contract_terminate_wizard_views.xml',
    ],
    'demo': [
        'demo/demo_partners_contracts.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
